from collections.abc import Iterable
from typing import Any


def _first_value(row: Any) -> Any:
    """Primeira coluna de uma linha, seja ela dict (DictCursor) ou tupla."""
    return next(iter(row.values())) if isinstance(row, dict) else row[0]

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

# No MySQL o "schema" É o database — todas as queries filtram por TABLE_SCHEMA = database.
_TABLES_QUERY = """
    SELECT TABLE_NAME, TABLE_ROWS
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
    ORDER BY TABLE_NAME
"""

_COLUMNS_QUERY = """
    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = %s
    ORDER BY TABLE_NAME, ORDINAL_POSITION
"""

_FOREIGN_KEYS_QUERY = """
    SELECT
        CONSTRAINT_NAME AS constraint_name,
        TABLE_NAME AS source_table,
        COLUMN_NAME AS source_column,
        REFERENCED_TABLE_NAME AS target_table,
        REFERENCED_COLUMN_NAME AS target_column
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL
"""

_DISTINCT_COUNT_QUERY_TEMPLATE = "SELECT COUNT(DISTINCT `{column}`) FROM `{schema}`.`{table}`"
_SAMPLE_VALUES_QUERY_TEMPLATE = (
    "SELECT DISTINCT `{column}` FROM `{schema}`.`{table}` "
    "WHERE `{column}` IS NOT NULL LIMIT {limit}"
)

_NUMERIC_TYPES = {"int", "bigint", "smallint", "tinyint", "mediumint", "decimal", "float", "double"}
_SKIP_SAMPLE_VALUES_TYPES = _NUMERIC_TYPES | {"text", "mediumtext", "longtext", "tinytext", "json"}


def build_relationships(
    fk_rows: Iterable[dict[str, Any]],
) -> tuple[dict[str, list[RelationshipMetadata]], dict[str, set[str]]]:
    """Rows de KEY_COLUMN_USAGE -> (relationships por tabela, colunas FK por tabela)."""
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
    """Rows de information_schema.COLUMNS -> colunas por tabela."""
    samples = sample_values or {}
    columns_by_table: dict[str, list[ColumnMetadata]] = {}
    for row in column_rows:
        table = row["TABLE_NAME"]
        column = row["COLUMN_NAME"]
        columns_by_table.setdefault(table, []).append(
            ColumnMetadata(
                column_name=column,
                data_type=row["DATA_TYPE"],
                is_nullable=row["IS_NULLABLE"] == "YES",
                is_primary_key=row["COLUMN_KEY"] == "PRI",
                is_foreign_key=column in fk_columns_by_table.get(table, set()),
                sample_values=samples.get((table, column), []),
            )
        )
    return columns_by_table


def should_sample(data_type: str) -> bool:
    return data_type.lower() not in _SKIP_SAMPLE_VALUES_TYPES


class MySQLIntrospector(BaseIntrospector):
    """Introspecta MySQL/MariaDB via information_schema (aiomysql)."""

    async def _connect(self):
        import aiomysql

        return await aiomysql.connect(
            host=self._config.host,
            port=self._config.port,
            db=self._config.database_name,
            user=self._config.username,
            password=self._config.password,
            ssl=True if self._config.ssl_enabled else None,
        )

    @property
    def _database(self) -> str:
        return self._config.database_name

    async def test_connection(self) -> ConnectionTestResult:
        async def probe() -> str | None:
            connection = await self._connect()
            try:
                async with connection.cursor() as cursor:
                    await cursor.execute("SELECT VERSION()")
                    row = await cursor.fetchone()
                    return f"MySQL {row[0]}" if row else None
            finally:
                connection.close()

        return await timed_test_connection(probe)

    async def introspect(self) -> list[TableMetadata]:
        import aiomysql

        connection = await self._connect()
        try:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(_TABLES_QUERY, (self._database,))
                table_rows = await cursor.fetchall()
                await cursor.execute(_COLUMNS_QUERY, (self._database,))
                column_rows = await cursor.fetchall()
                await cursor.execute(_FOREIGN_KEYS_QUERY, (self._database,))
                fk_rows = await cursor.fetchall()

                relationships_by_table, fk_columns_by_table = build_relationships(fk_rows)
                columns_by_table = build_columns(column_rows, fk_columns_by_table)
                sample_values = await self._collect_sample_values(cursor, column_rows)

            columns_by_table = build_columns(column_rows, fk_columns_by_table, sample_values)
        finally:
            connection.close()

        tables: list[TableMetadata] = []
        for row in table_rows:
            name = row["TABLE_NAME"]
            tables.append(
                TableMetadata(
                    table_name=name,
                    schema_name=self._database,
                    row_count=int(row["TABLE_ROWS"] or 0),
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
            if not should_sample(row["DATA_TYPE"]):
                continue
            table, column = row["TABLE_NAME"], row["COLUMN_NAME"]
            count_sql = _DISTINCT_COUNT_QUERY_TEMPLATE.format(
                schema=self._database, table=table, column=column
            )
            await cursor.execute(count_sql)
            distinct = _first_value(await cursor.fetchone())
            if distinct is None or distinct > LOW_CARDINALITY_THRESHOLD:
                continue
            sample_sql = _SAMPLE_VALUES_QUERY_TEMPLATE.format(
                schema=self._database, table=table, column=column, limit=SAMPLE_VALUES_LIMIT
            )
            await cursor.execute(sample_sql)
            rows = await cursor.fetchall()
            result[(table, column)] = [str(_first_value(r)) for r in rows]
        return result
