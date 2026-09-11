from dataclasses import dataclass

from pydantic import BaseModel

_DEFAULT_PORTS = {
    "postgresql": 5432,
    "mysql": 3306,
    "sqlserver": 1433,
    "oracle": 1521,
}

# Schema padrão por dialeto quando o usuário não informa um.
_DEFAULT_SCHEMAS = {
    "postgresql": "public",
    "sqlserver": "dbo",
}


@dataclass(frozen=True)
class ConnectionConfig:
    """Parâmetros de conexão a um banco do usuário (senha em texto plano).

    Montado tanto a partir de um `ConnectionCreate` (fluxo "testar antes de salvar")
    quanto de uma linha `Connection` já persistida (senha descriptografada).
    """

    db_type: str
    host: str
    port: int
    database_name: str
    username: str
    password: str
    ssl_enabled: bool = False
    schema_name: str = "public"

    @staticmethod
    def default_port(db_type: str) -> int | None:
        return _DEFAULT_PORTS.get(db_type)

    @staticmethod
    def default_schema(db_type: str) -> str:
        return _DEFAULT_SCHEMAS.get(db_type, "public")


class ColumnMetadata(BaseModel):
    column_name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    sample_values: list[str] = []


class RelationshipMetadata(BaseModel):
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    constraint_name: str


class TableMetadata(BaseModel):
    table_name: str
    schema_name: str
    row_count: int
    columns: list[ColumnMetadata]
    relationships: list[RelationshipMetadata]


class ConnectionTestResult(BaseModel):
    success: bool
    message: str
    db_version: str | None = None
    latency_ms: int | None = None
