import uuid
from dataclasses import dataclass

import sqlparse
from sqlparse.tokens import DDL, DML, Keyword

from app.agents.sql_utils import extract_referenced_tables
from app.agents.state import AgentState
from app.core.logging import get_logger
from app.database.connection import get_metadata_session
from app.metadata.repository import MetadataRepository

logger = get_logger(__name__)

_BLOCKED_COMMANDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
    "EXEC",
    "CALL",
    "SET",
    "COPY",
    "VACUUM",
    "REINDEX",
    "CLUSTER",
    "LOCK",
    "DISCARD",
    "LOAD",
    "COMMENT",
}

_DANGEROUS_FUNCTIONS = {
    "pg_sleep",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "lo_import",
    "lo_export",
    "dblink",
}

_ALLOWED_START_KEYWORDS = {"SELECT", "WITH"}


@dataclass
class ValidationResult:
    is_valid: bool
    rejection_reason: str | None = None

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(is_valid=True)

    @classmethod
    def reject(cls, reason: str) -> "ValidationResult":
        return cls(is_valid=False, rejection_reason=reason)


def validate_sql_syntax(sql: str) -> ValidationResult:
    """Validação síncrona e pura (sem DB): blocklist, must-start-with, multi-statement,
    funções perigosas. Usa sqlparse para tokenizar corretamente (respeita literais de
    string com `;` dentro, e detecta comandos DML escondidos em CTEs graváveis, ex.:
    `WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x`).
    """
    stripped = sql.strip()
    if not stripped:
        return ValidationResult.reject("SQL vazio")

    statements = [s for s in sqlparse.split(stripped) if s.strip()]
    if len(statements) != 1:
        return ValidationResult.reject("múltiplos statements SQL não são permitidos")

    parsed = sqlparse.parse(stripped)
    if not parsed:
        return ValidationResult.reject("não foi possível interpretar o SQL")
    statement = parsed[0]

    first_token = statement.token_first(skip_cm=True)
    if first_token is None or (first_token.normalized or "").upper() not in _ALLOWED_START_KEYWORDS:
        return ValidationResult.reject("query deve começar com SELECT ou WITH")

    for token in statement.flatten():
        value = (token.value or "").strip()
        if not value:
            continue
        if token.ttype in (DML, DDL, Keyword) and value.upper() in _BLOCKED_COMMANDS:
            return ValidationResult.reject(f"comando não permitido: {value.upper()}")
        if value.lower() in _DANGEROUS_FUNCTIONS:
            return ValidationResult.reject(f"função não permitida: {value}")

    return ValidationResult.ok()


async def validate_tables_exist(
    sql: str, session, connection_id: uuid.UUID | None = None
) -> ValidationResult:
    """Confere que toda tabela referenciada em FROM/JOIN existe na tabela `tables`
    do banco de metadados (CTEs já são excluídas por extract_referenced_tables)."""
    referenced = extract_referenced_tables(sql)
    if not referenced:
        return ValidationResult.ok()

    repository = MetadataRepository(session)
    known_tables = {table.table_name.lower() for table in await repository.list_tables(connection_id)}

    unknown = referenced - known_tables
    if unknown:
        return ValidationResult.reject(f"tabela(s) inexistente(s) no schema: {', '.join(sorted(unknown))}")

    return ValidationResult.ok()


async def sql_validator_node(state: AgentState) -> dict:
    sql = state["generated_sql"]

    syntax_result = validate_sql_syntax(sql)
    if not syntax_result.is_valid:
        logger.info("sql_validation_rejected", stage="syntax", reason=syntax_result.rejection_reason)
        return {"sql_is_valid": False, "execution_error": f"[validation] {syntax_result.rejection_reason}"}

    connection_id = uuid.UUID(state["connection_id"]) if state.get("connection_id") else None
    async with get_metadata_session() as session:
        tables_result = await validate_tables_exist(sql, session, connection_id)
    if not tables_result.is_valid:
        logger.info("sql_validation_rejected", stage="tables", reason=tables_result.rejection_reason)
        return {"sql_is_valid": False, "execution_error": f"[validation] {tables_result.rejection_reason}"}

    return {"sql_is_valid": True, "execution_error": None}
