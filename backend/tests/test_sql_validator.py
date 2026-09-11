import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.sql_utils import extract_referenced_tables
from app.agents.sql_validator import validate_sql_syntax, validate_tables_exist
from app.metadata.repository import MetadataRepository
from app.metadata.schemas import TableCreate


def test_accepts_simple_select() -> None:
    result = validate_sql_syntax("SELECT id, full_name FROM clients WHERE status = 'active'")
    assert result.is_valid is True


def test_accepts_cte_with() -> None:
    sql = "WITH ranking AS (SELECT broker_id, SUM(premium_amount) AS total FROM policies GROUP BY broker_id) " \
        "SELECT * FROM ranking JOIN brokers ON brokers.id = ranking.broker_id"
    result = validate_sql_syntax(sql)
    assert result.is_valid is True


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO clients (full_name) VALUES ('x')",
        "UPDATE clients SET status = 'inactive'",
        "DELETE FROM clients WHERE id = 1",
        "DROP TABLE clients",
        "ALTER TABLE clients ADD COLUMN x TEXT",
        "TRUNCATE clients",
        "CREATE TABLE x (id INT)",
        "GRANT SELECT ON clients TO someone",
        "REVOKE SELECT ON clients FROM someone",
        "CALL some_procedure()",
        "SET statement_timeout = '1s'",
        "COPY clients TO '/tmp/out.csv'",
        "VACUUM clients",
        "REINDEX TABLE clients",
        "LOCK TABLE clients",
    ],
)
def test_rejects_non_select_statements(sql: str) -> None:
    result = validate_sql_syntax(sql)
    assert result.is_valid is False


def test_rejects_writable_cte_smuggling_delete() -> None:
    """CTE gravável (WITH x AS (DELETE ... RETURNING *) SELECT ...) é sintaxe PostgreSQL
    válida — precisa ser bloqueada mesmo o statement começando com WITH/SELECT."""
    sql = "WITH deleted AS (DELETE FROM policies WHERE id = 1 RETURNING *) SELECT * FROM deleted"
    result = validate_sql_syntax(sql)
    assert result.is_valid is False


def test_rejects_multiple_statements() -> None:
    result = validate_sql_syntax("SELECT 1; DROP TABLE clients")
    assert result.is_valid is False


def test_accepts_semicolon_inside_string_literal() -> None:
    """Uma contagem ingênua de `;` erraria aqui — o `;` está dentro de um literal de string."""
    result = validate_sql_syntax("SELECT * FROM claims WHERE description = 'ok; done'")
    assert result.is_valid is True


def test_rejects_dangerous_function() -> None:
    result = validate_sql_syntax("SELECT pg_sleep(10)")
    assert result.is_valid is False


def test_rejects_empty_sql() -> None:
    result = validate_sql_syntax("   ")
    assert result.is_valid is False


def test_extract_referenced_tables_excludes_cte_names() -> None:
    sql = "WITH ranking AS (SELECT broker_id FROM policies) SELECT * FROM ranking JOIN brokers ON true"
    tables = extract_referenced_tables(sql)
    assert tables == {"policies", "brokers"}
    assert "ranking" not in tables


def test_extract_referenced_tables_simple_join() -> None:
    sql = "SELECT * FROM policies p JOIN brokers b ON b.id = p.broker_id"
    tables = extract_referenced_tables(sql)
    assert tables == {"policies", "brokers"}


@pytest.mark.asyncio
async def test_validate_tables_exist_accepts_known_table(
    metadata_session: AsyncSession, connection_row
) -> None:
    repository = MetadataRepository(metadata_session)
    await repository.upsert_table(connection_row.id, TableCreate(table_name="policies"))
    await metadata_session.commit()

    result = await validate_tables_exist("SELECT * FROM policies", metadata_session)

    assert result.is_valid is True


@pytest.mark.asyncio
async def test_validate_tables_exist_rejects_unknown_table(
    metadata_session: AsyncSession, connection_row
) -> None:
    repository = MetadataRepository(metadata_session)
    await repository.upsert_table(connection_row.id, TableCreate(table_name="policies"))
    await metadata_session.commit()

    result = await validate_tables_exist("SELECT * FROM does_not_exist", metadata_session)

    assert result.is_valid is False
