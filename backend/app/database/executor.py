"""Execução read-only de SQL no banco do usuário, um caminho por dialeto.

O SQL já passou pelo `sql_validator` (só SELECT/WITH, sem comandos perigosos) antes
de chegar aqui. Esta camada cuida de timeout e limite de linhas por dialeto.
"""

import asyncio

from app.core.logging import get_logger
from app.database.introspection.sqlserver import build_odbc_connection_string
from app.database.introspection.types import ConnectionConfig

logger = get_logger(__name__)

ExecutionOutcome = tuple[list[dict], bool, str | None]


def _clean_error(exc: Exception) -> str:
    return str(exc).strip() or exc.__class__.__name__


async def _execute_postgres(
    config: ConnectionConfig, sql: str, timeout: int, max_rows: int
) -> ExecutionOutcome:
    import asyncpg

    connection = await asyncpg.connect(
        host=config.host,
        port=config.port,
        database=config.database_name,
        user=config.username,
        password=config.password,
        ssl="require" if config.ssl_enabled else None,
    )
    try:
        # `timeout` vem de settings, não de input do usuário — SET não aceita bind
        # parameters no protocolo do Postgres, então formatar aqui é seguro.
        await connection.execute(f"SET statement_timeout = '{timeout}s'")
        async with connection.transaction():
            cursor = await connection.cursor(sql)
            records = await cursor.fetch(max_rows + 1)
    finally:
        await connection.close()

    was_truncated = len(records) > max_rows
    return [dict(record) for record in records[:max_rows]], was_truncated, None


async def _execute_mysql(
    config: ConnectionConfig, sql: str, timeout: int, max_rows: int
) -> ExecutionOutcome:
    import aiomysql

    connection = await aiomysql.connect(
        host=config.host,
        port=config.port,
        db=config.database_name,
        user=config.username,
        password=config.password,
        ssl=True if config.ssl_enabled else None,
    )
    try:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            await asyncio.wait_for(cursor.execute(sql), timeout=timeout)
            records = await cursor.fetchmany(max_rows + 1)
    finally:
        connection.close()

    was_truncated = len(records) > max_rows
    return [dict(record) for record in records[:max_rows]], was_truncated, None


async def _execute_sqlserver(
    config: ConnectionConfig, sql: str, timeout: int, max_rows: int
) -> ExecutionOutcome:
    import aioodbc

    connection = await aioodbc.connect(dsn=build_odbc_connection_string(config), autocommit=True)
    try:
        async with connection.cursor() as cursor:
            await asyncio.wait_for(cursor.execute(sql), timeout=timeout)
            columns = [desc[0] for desc in cursor.description]
            records = await cursor.fetchmany(max_rows + 1)
    finally:
        await connection.close()

    was_truncated = len(records) > max_rows
    rows = [dict(zip(columns, record, strict=True)) for record in records[:max_rows]]
    return rows, was_truncated, None


_EXECUTORS = {
    "postgresql": _execute_postgres,
    "mysql": _execute_mysql,
    "sqlserver": _execute_sqlserver,
}


async def execute_readonly_sql(
    config: ConnectionConfig, sql: str, timeout: int, max_rows: int
) -> ExecutionOutcome:
    """Executa `sql` no banco de `config`. Em erro: ([], False, mensagem amigável)."""
    executor = _EXECUTORS.get(config.db_type)
    if executor is None:
        return [], False, f"Execução para '{config.db_type}' não é suportada."

    try:
        return await executor(config, sql, timeout, max_rows)
    except TimeoutError:
        logger.warning("sql_execution_timeout", db_type=config.db_type, timeout=timeout)
        return [], False, f"A consulta excedeu o tempo limite de {timeout}s."
    except Exception as exc:
        logger.warning("sql_execution_failed", db_type=config.db_type, error=str(exc))
        return [], False, _clean_error(exc)
