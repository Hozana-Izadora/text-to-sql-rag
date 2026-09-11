from collections.abc import Iterable
from typing import Any

from app.core.logging import get_logger
from app.database.introspection.base import (
    LOW_CARDINALITY_THRESHOLD,
    SAMPLE_VALUES_LIMIT,
    BaseIntrospector,
    timed_test_connection,
)
from app.database.introspection.types import (
    ColumnMetadata,
    ConnectionConfig,
    ConnectionTestResult,
    RelationshipMetadata,
    TableMetadata,
)

logger = get_logger(__name__)

_TABLES_QUERY = """
    SELECT t.name AS table_name, SUM(p.rows) AS row_count
    FROM sys.tables t
    JOIN sys.schemas s ON s.schema_id = t.schema_id
    JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
    WHERE s.name = ?
    GROUP BY t.name
    ORDER BY t.name
"""

_COLUMNS_QUERY = """
    SELECT
        t.name AS table_name,
        c.name AS column_name,
        ty.name AS data_type,
        c.is_nullable AS is_nullable,
        CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key
    FROM sys.columns c
    JOIN sys.tables t ON t.object_id = c.object_id
    JOIN sys.schemas s ON s.schema_id = t.schema_id
    JOIN sys.types ty ON ty.user_type_id = c.user_type_id
    LEFT JOIN (
        SELECT ic.object_id, ic.column_id
        FROM sys.index_columns ic
        JOIN sys.indexes i ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        WHERE i.is_primary_key = 1
    ) pk ON pk.object_id = c.object_id AND pk.column_id = c.column_id
    WHERE s.name = ?
    ORDER BY t.name, c.column_id
"""

_FOREIGN_KEYS_QUERY = """
    SELECT
        fk.name AS constraint_name,
        tp.name AS source_table,
        cp.name AS source_column,
        tr.name AS target_table,
        cr.name AS target_column
    FROM sys.foreign_keys fk
    JOIN sys.schemas s ON s.schema_id = fk.schema_id
    JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
    JOIN sys.tables tp ON tp.object_id = fkc.parent_object_id
    JOIN sys.columns cp ON cp.object_id = fkc.parent_object_id AND cp.column_id = fkc.parent_column_id
    JOIN sys.tables tr ON tr.object_id = fkc.referenced_object_id
    JOIN sys.columns cr ON cr.object_id = fkc.referenced_object_id AND cr.column_id = fkc.referenced_column_id
    WHERE s.name = ?
"""

_DISTINCT_COUNT_QUERY_TEMPLATE = "SELECT COUNT(DISTINCT [{column}]) FROM [{schema}].[{table}]"
_SAMPLE_VALUES_QUERY_TEMPLATE = (
    "SELECT DISTINCT TOP {limit} [{column}] FROM [{schema}].[{table}] WHERE [{column}] IS NOT NULL"
)

_NUMERIC_TYPES = {
    "int", "bigint", "smallint", "tinyint", "decimal", "numeric", "money", "smallmoney",
    "float", "real",
}
_SKIP_SAMPLE_VALUES_TYPES = _NUMERIC_TYPES | {"text", "ntext", "xml"}


def build_odbc_connection_string(config: ConnectionConfig) -> str:
    """Monta a connection string ODBC para o SQL Server a partir do config."""
    encrypt = "yes" if config.ssl_enabled else "no"
    return (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={config.host},{config.port};"
        f"DATABASE={config.database_name};"
        f"UID={config.username};"
        f"PWD={config.password};"
        f"Encrypt={encrypt};"
        "TrustServerCertificate=yes"
    )


def build_relationships(
    fk_rows: Iterable[dict[str, Any]],
) -> tuple[dict[str, list[RelationshipMetadata]], dict[str, set[str]]]:
    relationships_by_table: dict[str, list[RelationshipMetadata]] = {}
    fk_columns_by_table: dict[str, set[str]] = {}
    for row in fk_rows:
        source_table = row["source_table"]
        relationships_by_table.setdefault(source_table, []).append(
            RelationshipMetadata(
                source_table=source_table,
                source_column=row["source_column"],
                target_table=row["target_table"],
                target_column=row["target_column"],
                constraint_name=row["constraint_name"] or "",
            )
        )
        fk_columns_by_table.setdefault(source_table, set()).add(row["source_column"])
    return relationships_by_table, fk_columns_by_table


def build_columns(
    column_rows: Iterable[dict[str, Any]],
    fk_columns_by_table: dict[str, set[str]],
    sample_values: dict[tuple[str, str], list[str]] | None = None,
) -> dict[str, list[ColumnMetadata]]:
    samples = sample_values or {}
    columns_by_table: dict[str, list[ColumnMetadata]] = {}
    for row in column_rows:
        table = row["table_name"]
        column = row["column_name"]
        columns_by_table.setdefault(table, []).append(
            ColumnMetadata(
                column_name=column,
                data_type=row["data_type"],
                is_nullable=bool(row["is_nullable"]),
                is_primary_key=bool(row["is_primary_key"]),
                is_foreign_key=column in fk_columns_by_table.get(table, set()),
                sample_values=samples.get((table, column), []),
            )
        )
    return columns_by_table


def should_sample(data_type: str) -> bool:
    return data_type.lower() not in _SKIP_SAMPLE_VALUES_TYPES


def _rows_as_dicts(cursor: Any) -> list[dict[str, Any]]:
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


class SQLServerIntrospector(BaseIntrospector):
    """Introspecta Microsoft SQL Server via catálogo sys.* (aioodbc)."""

    @property
    def _schema(self) -> str:
        return self._config.schema_name or "dbo"

    async def _connect(self):
        import aioodbc

        return await aioodbc.connect(dsn=build_odbc_connection_string(self._config), autocommit=True)

    async def test_connection(self) -> ConnectionTestResult:
        async def probe() -> str | None:
            connection = await self._connect()
            try:
                async with connection.cursor() as cursor:
                    await cursor.execute("SELECT @@VERSION")
                    row = await cursor.fetchone()
                    return row[0].splitlines()[0] if row else None
            finally:
                await connection.close()

        return await timed_test_connection(probe)

    async def introspect(self) -> list[TableMetadata]:
        connection = await self._connect()
        try:
            async with connection.cursor() as cursor:
                await cursor.execute(_TABLES_QUERY, self._schema)
                table_rows = _rows_as_dicts(cursor)
                await cursor.execute(_COLUMNS_QUERY, self._schema)
                column_rows = _rows_as_dicts(cursor)
                await cursor.execute(_FOREIGN_KEYS_QUERY, self._schema)
                fk_rows = _rows_as_dicts(cursor)

                relationships_by_table, fk_columns_by_table = build_relationships(fk_rows)
                sample_values = await self._collect_sample_values(cursor, column_rows)
        finally:
            await connection.close()

        columns_by_table = build_columns(column_rows, fk_columns_by_table, sample_values)
        tables: list[TableMetadata] = []
        for row in table_rows:
            name = row["table_name"]
            tables.append(
                TableMetadata(
                    table_name=name,
                    schema_name=self._schema,
                    row_count=int(row["row_count"] or 0),
                    columns=columns_by_table.get(name, []),
                    relationships=relationships_by_table.get(name, []),
                )
            )
        return tables

    async def _collect_sample_values(
        self, cursor: Any, column_rows: Iterable[dict[str, Any]]
    ) -> dict[tuple[str, str], list[str]]:
        result: dict[tuple[str, str], list[str]] = {}
        for row in column_rows:
            if not should_sample(row["data_type"]):
                continue
            table, column = row["table_name"], row["column_name"]
            await cursor.execute(
                _DISTINCT_COUNT_QUERY_TEMPLATE.format(schema=self._schema, table=table, column=column)
            )
            count_row = await cursor.fetchone()
            distinct = count_row[0] if count_row else None
            if distinct is None or distinct > LOW_CARDINALITY_THRESHOLD:
                continue
            await cursor.execute(
                _SAMPLE_VALUES_QUERY_TEMPLATE.format(
                    schema=self._schema, table=table, column=column, limit=SAMPLE_VALUES_LIMIT
                )
            )
            result[(table, column)] = [str(r[0]) for r in await cursor.fetchall()]
        return result
