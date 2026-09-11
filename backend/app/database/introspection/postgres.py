from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from app.core.logging import get_logger
from app.database.introspection.base import (
    LOW_CARDINALITY_THRESHOLD,
    SAMPLE_VALUES_LIMIT,
    BaseIntrospector,
    timed_test_connection,
)
from app.database.introspection.types import (
    ColumnMetadata,
    ConnectionTestResult,
    RelationshipMetadata,
    TableMetadata,
)

logger = get_logger(__name__)

_TABLES_QUERY = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = $1 AND table_type = 'BASE TABLE'
    ORDER BY table_name
"""

_COLUMNS_QUERY = """
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema = $1 AND table_name = $2
    ORDER BY ordinal_position
"""

# Usa pg_catalog em vez de information_schema.table_constraints /
# constraint_column_usage: essas views só listam FK/PK para o usuário quando ele tem
# privilégio REFERENCES (ou é dono) na tabela — um usuário só-leitura com apenas
# GRANT SELECT não enxerga nada nelas. pg_catalog é legível independente de privilégios.
_PRIMARY_KEYS_QUERY = """
    SELECT a.attname AS column_name
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    JOIN LATERAL unnest(c.conkey) AS ck(attnum) ON true
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ck.attnum
    WHERE c.contype = 'p' AND n.nspname = $1 AND t.relname = $2
"""

_RELATIONSHIPS_QUERY = """
    SELECT
        c.conname AS constraint_name,
        t.relname AS source_table,
        sa.attname AS source_column,
        rt.relname AS target_table,
        ra.attname AS target_column
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    JOIN pg_class rt ON rt.oid = c.confrelid
    JOIN LATERAL unnest(c.conkey, c.confkey) AS cols(sattnum, rattnum) ON true
    JOIN pg_attribute sa ON sa.attrelid = t.oid AND sa.attnum = cols.sattnum
    JOIN pg_attribute ra ON ra.attrelid = rt.oid AND ra.attnum = cols.rattnum
    WHERE c.contype = 'f' AND n.nspname = $1
"""

_ROW_COUNT_QUERY = """
    SELECT c.reltuples::BIGINT AS row_count
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = $1 AND c.relname = $2
"""

_EXACT_ROW_COUNT_QUERY_TEMPLATE = 'SELECT COUNT(*) FROM "{schema}"."{table}"'
_DISTINCT_COUNT_QUERY_TEMPLATE = 'SELECT COUNT(DISTINCT "{column}") FROM "{schema}"."{table}"'
_SAMPLE_VALUES_QUERY_TEMPLATE = (
    'SELECT DISTINCT "{column}" FROM "{schema}"."{table}" WHERE "{column}" IS NOT NULL LIMIT {limit}'
)

_NUMERIC_TYPE_PREFIXES = ("integer", "bigint", "numeric", "double precision", "real", "smallint")

# "text" (sem limite) é convenção de schema para texto livre — nunca é enum, mesmo com
# baixa cardinalidade em bases pequenas. "character varying" (status, tipo etc.) é o
# candidato real a enum.
_SKIP_SAMPLE_VALUES_TYPES = _NUMERIC_TYPE_PREFIXES + ("text",)


class PostgresIntrospector(BaseIntrospector):
    """Introspecta PostgreSQL via information_schema + pg_catalog (asyncpg)."""

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[asyncpg.Connection]:
        connection = await asyncpg.connect(
            host=self._config.host,
            port=self._config.port,
            database=self._config.database_name,
            user=self._config.username,
            password=self._config.password,
            ssl="require" if self._config.ssl_enabled else None,
        )
        try:
            yield connection
        finally:
            await connection.close()

    @property
    def _schema(self) -> str:
        return self._config.schema_name or "public"

    async def test_connection(self) -> ConnectionTestResult:
        async def probe() -> str | None:
            async with self._connect() as connection:
                return await connection.fetchval("SELECT version()")

        return await timed_test_connection(probe)

    async def introspect(self) -> list[TableMetadata]:
        async with self._connect() as connection:
            table_names = [row["table_name"] for row in await connection.fetch(_TABLES_QUERY, self._schema)]
            relationships_by_table = await self._list_relationships(connection)

            tables: list[TableMetadata] = []
            for table_name in table_names:
                columns = await self._list_columns(connection, table_name)
                row_count = await self._get_row_count(connection, table_name)
                tables.append(
                    TableMetadata(
                        table_name=table_name,
                        schema_name=self._schema,
                        row_count=row_count,
                        columns=columns,
                        relationships=relationships_by_table.get(table_name, []),
                    )
                )
            return tables

    async def _list_columns(
        self, connection: asyncpg.Connection, table_name: str
    ) -> list[ColumnMetadata]:
        rows = await connection.fetch(_COLUMNS_QUERY, self._schema, table_name)
        pk_rows = await connection.fetch(_PRIMARY_KEYS_QUERY, self._schema, table_name)
        primary_keys = {row["column_name"] for row in pk_rows}
        fk_columns = await self._foreign_key_columns(connection, table_name)

        columns: list[ColumnMetadata] = []
        for row in rows:
            column_name = row["column_name"]
            data_type = row["data_type"]
            sample_values: list[str] = []
            if not data_type.startswith(_SKIP_SAMPLE_VALUES_TYPES):
                sample_values = await self._sample_values_if_low_cardinality(
                    connection, table_name, column_name
                )
            columns.append(
                ColumnMetadata(
                    column_name=column_name,
                    data_type=data_type,
                    is_nullable=row["is_nullable"] == "YES",
                    is_primary_key=column_name in primary_keys,
                    is_foreign_key=column_name in fk_columns,
                    sample_values=sample_values,
                )
            )
        return columns

    async def _foreign_key_columns(
        self, connection: asyncpg.Connection, table_name: str
    ) -> set[str]:
        rows = await connection.fetch(_RELATIONSHIPS_QUERY, self._schema)
        return {row["source_column"] for row in rows if row["source_table"] == table_name}

    async def _sample_values_if_low_cardinality(
        self, connection: asyncpg.Connection, table_name: str, column_name: str
    ) -> list[str]:
        count_query = _DISTINCT_COUNT_QUERY_TEMPLATE.format(
            schema=self._schema, table=table_name, column=column_name
        )
        distinct_count = await connection.fetchval(count_query)
        if distinct_count is None or distinct_count > LOW_CARDINALITY_THRESHOLD:
            return []
        sample_query = _SAMPLE_VALUES_QUERY_TEMPLATE.format(
            schema=self._schema, table=table_name, column=column_name, limit=SAMPLE_VALUES_LIMIT
        )
        rows = await connection.fetch(sample_query)
        return [str(row[column_name]) for row in rows]

    async def _get_row_count(self, connection: asyncpg.Connection, table_name: str) -> int:
        value = await connection.fetchval(_ROW_COUNT_QUERY, self._schema, table_name)
        if value is not None and value >= 0:
            return int(value)
        # reltuples é -1 até a tabela passar por ANALYZE (ex.: logo após o seed).
        count_query = _EXACT_ROW_COUNT_QUERY_TEMPLATE.format(schema=self._schema, table=table_name)
        exact_count = await connection.fetchval(count_query)
        return int(exact_count) if exact_count is not None else 0

    async def _list_relationships(
        self, connection: asyncpg.Connection
    ) -> dict[str, list[RelationshipMetadata]]:
        rows = await connection.fetch(_RELATIONSHIPS_QUERY, self._schema)
        relationships_by_table: dict[str, list[RelationshipMetadata]] = {}
        for row in rows:
            relationship = RelationshipMetadata(
                source_table=row["source_table"],
                source_column=row["source_column"],
                target_table=row["target_table"],
                target_column=row["target_column"],
                constraint_name=row["constraint_name"],
            )
            relationships_by_table.setdefault(row["source_table"], []).append(relationship)
        return relationships_by_table
