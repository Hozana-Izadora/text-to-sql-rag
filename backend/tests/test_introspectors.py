import pytest
from testcontainers.postgres import PostgresContainer

from app.database.introspection import get_introspector
from app.database.introspection.factory import _INTROSPECTORS
from app.database.introspection.mysql import MySQLIntrospector, build_columns, build_relationships
from app.database.introspection.postgres import PostgresIntrospector
from app.database.introspection.sqlserver import (
    SQLServerIntrospector,
    build_odbc_connection_string,
)
from app.database.introspection.types import ConnectionConfig
from tests.conftest import PRODUCTION_TEST_SCHEMA


def _pg_config(container: PostgresContainer) -> ConnectionConfig:
    return ConnectionConfig(
        db_type="postgresql",
        host=container.get_container_host_ip(),
        port=int(container.get_exposed_port(5432)),
        database_name=container.dbname,
        username=container.username,
        password=container.password,
        schema_name=PRODUCTION_TEST_SCHEMA,
    )


# ------------------------------------------------------------------- factory


@pytest.mark.parametrize(
    ("db_type", "expected"),
    [
        ("postgresql", PostgresIntrospector),
        ("mysql", MySQLIntrospector),
        ("sqlserver", SQLServerIntrospector),
    ],
)
def test_factory_returns_correct_introspector(db_type: str, expected: type) -> None:
    config = ConnectionConfig(
        db_type=db_type, host="h", port=1, database_name="d", username="u", password="p"
    )
    assert isinstance(get_introspector(config), expected)


@pytest.mark.parametrize("db_type", ["oracle", "sqlite"])
def test_factory_rejects_unsupported_dialects(db_type: str) -> None:
    config = ConnectionConfig(
        db_type=db_type, host="h", port=1, database_name="d", username="u", password="p"
    )
    with pytest.raises(NotImplementedError):
        get_introspector(config)


def test_factory_rejects_unknown_db_type() -> None:
    config = ConnectionConfig(
        db_type="nope", host="h", port=1, database_name="d", username="u", password="p"
    )
    with pytest.raises(ValueError, match="db_type desconhecido"):
        get_introspector(config)


def test_all_registered_introspectors_are_base_subclasses() -> None:
    from app.database.introspection.base import BaseIntrospector

    assert all(issubclass(cls, BaseIntrospector) for cls in _INTROSPECTORS.values())


# ---------------------------------------------------------------- postgres (container)


@pytest.mark.asyncio
async def test_postgres_introspect_returns_tables_columns_and_relationships(
    postgres_container: PostgresContainer, production_connection
) -> None:
    introspector = PostgresIntrospector(_pg_config(postgres_container))

    tables = await introspector.introspect()
    tables_by_name = {t.table_name: t for t in tables}
    assert set(tables_by_name) == {"brokers", "clients", "policies"}

    brokers = tables_by_name["brokers"]
    broker_columns = {c.column_name: c for c in brokers.columns}
    assert broker_columns["id"].is_primary_key is True
    assert broker_columns["status"].is_nullable is False
    assert set(broker_columns["status"].sample_values) == {"active"}

    clients = tables_by_name["clients"]
    client_columns = {c.column_name: c for c in clients.columns}
    assert client_columns["broker_id"].is_foreign_key is True

    policies = tables_by_name["policies"]
    relationships_by_column = {r.source_column: r for r in policies.relationships}
    assert relationships_by_column["client_id"].target_table == "clients"
    assert relationships_by_column["broker_id"].target_table == "brokers"


@pytest.mark.asyncio
async def test_postgres_test_connection_reports_version(
    postgres_container: PostgresContainer,
) -> None:
    result = await PostgresIntrospector(_pg_config(postgres_container)).test_connection()
    assert result.success is True
    assert result.db_version and "PostgreSQL" in result.db_version
    assert result.latency_ms is not None


@pytest.mark.asyncio
async def test_postgres_test_connection_fails_gracefully() -> None:
    config = ConnectionConfig(
        db_type="postgresql",
        host="127.0.0.1",
        port=1,
        database_name="x",
        username="x",
        password="x",
    )
    result = await PostgresIntrospector(config).test_connection()
    assert result.success is False
    assert result.db_version is None


# ---------------------------------------------------------- mysql / sqlserver (unit)


def test_mysql_build_relationships_and_columns_from_information_schema_rows() -> None:
    fk_rows = [
        {
            "constraint_name": "fk_orders_customer",
            "source_table": "orders",
            "source_column": "customer_id",
            "target_table": "customers",
            "target_column": "id",
        }
    ]
    column_rows = [
        {"TABLE_NAME": "orders", "COLUMN_NAME": "id", "DATA_TYPE": "int", "IS_NULLABLE": "NO", "COLUMN_KEY": "PRI"},
        {"TABLE_NAME": "orders", "COLUMN_NAME": "customer_id", "DATA_TYPE": "int", "IS_NULLABLE": "YES", "COLUMN_KEY": "MUL"},
    ]
    relationships, fk_columns = build_relationships(fk_rows)
    assert relationships["orders"][0].target_table == "customers"
    assert fk_columns["orders"] == {"customer_id"}

    columns = build_columns(column_rows, fk_columns)
    by_name = {c.column_name: c for c in columns["orders"]}
    assert by_name["id"].is_primary_key is True
    assert by_name["customer_id"].is_foreign_key is True
    assert by_name["customer_id"].is_nullable is True


def test_sqlserver_odbc_connection_string_includes_driver_and_credentials() -> None:
    config = ConnectionConfig(
        db_type="sqlserver",
        host="db.example.com",
        port=1433,
        database_name="sales",
        username="reader",
        password="s3cr3t",
        ssl_enabled=True,
    )
    dsn = build_odbc_connection_string(config)
    assert "ODBC Driver 18 for SQL Server" in dsn
    assert "SERVER=db.example.com,1433" in dsn
    assert "DATABASE=sales" in dsn
    assert "UID=reader" in dsn
    assert "Encrypt=yes" in dsn
