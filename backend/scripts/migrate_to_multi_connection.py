"""Migração: instalação de conexão única (SeguraPro) -> plataforma multi-conexão.

Idempotente. Passos:
  1. Cria a tabela `connections` (+ colunas `connection_id` nas tabelas de metadados).
  2. Cria a linha `connections` "Produção SeguraPro" a partir de PRODUCTION_DB_* do .env.
  3. Backfill: aponta todos os metadados existentes para essa conexão.
  4. Aplica NOT NULL, FKs ON DELETE CASCADE e o unique composto (connection_id, table_name).

Uso:
    uv run python -m scripts.migrate_to_multi_connection
"""

import asyncio

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.encryption import get_encryptor
from app.core.logging import configure_logging, get_logger
from app.database.connection import _metadata_engine, get_metadata_session
from app.metadata.models import Base, Connection

logger = get_logger(__name__)

CONNECTION_NAME = "Produção SeguraPro"

# Tabelas de metadados que ganham connection_id. NOT NULL em todas menos synthetic_examples.
_SCOPED_TABLES = [
    "tables",
    "synonyms",
    "enum_values",
    "business_rules",
    "relationships",
    "metadata_embeddings",
    "synthetic_examples",
]
_NULLABLE_SCOPED = {"synthetic_examples"}

# FKs internas que passam a ter ON DELETE CASCADE (nome default do Postgres).
_CASCADE_FKS = [
    ("columns", "columns_table_id_fkey", "table_id", "tables"),
    ("relationships", "relationships_source_table_id_fkey", "source_table_id", "tables"),
    ("relationships", "relationships_target_table_id_fkey", "target_table_id", "tables"),
    ("business_rules", "business_rules_table_id_fkey", "table_id", "tables"),
    ("enum_values", "enum_values_column_id_fkey", "column_id", "columns"),
]


async def _ddl(sql: str, *, ignore: bool = False) -> None:
    """Roda um statement DDL em transação própria (autocommit).

    Cada passo é isolado — um passo que falha (já aplicado) não aborta os demais.
    """
    engine = _metadata_engine.execution_options(isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(sql))
    except Exception as exc:  # DDL idempotente — alguns passos já podem estar feitos
        if not ignore:
            raise
        logger.info("migration_step_skipped", sql=sql.split("\n")[0].strip(), reason=str(exc))


async def _ensure_connections_table() -> None:
    async with _metadata_engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.create_all)


async def _add_columns() -> None:
    for table in _SCOPED_TABLES:
        await _ddl(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS connection_id UUID", ignore=True)
        await _ddl(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_connection_id ON {table} (connection_id)",
            ignore=True,
        )


async def _get_or_create_connection(session: AsyncSession) -> Connection:
    existing = await session.execute(select(Connection).where(Connection.name == CONNECTION_NAME))
    connection = existing.scalar_one_or_none()
    if connection is not None:
        return connection

    connection = Connection(
        name=CONNECTION_NAME,
        db_type="postgresql",
        host=settings.production_db_host,
        port=settings.production_db_port,
        database_name=settings.production_db_name,
        username=settings.production_db_user,
        password_encrypted=get_encryptor().encrypt(settings.production_db_password),
        ssl_enabled=False,
        schema_name="public",
    )
    session.add(connection)
    await session.flush()
    logger.info("bootstrap_connection_created", connection_id=str(connection.id))
    return connection


async def _backfill(session: AsyncSession, connection_id) -> None:
    for table in _SCOPED_TABLES:
        result = await session.execute(
            text(f"UPDATE {table} SET connection_id = :cid WHERE connection_id IS NULL"),
            {"cid": connection_id},
        )
        await session.flush()
        logger.info("backfilled", table=table, rows=result.rowcount)


async def _apply_constraints() -> None:
    for table in _SCOPED_TABLES:
        if table not in _NULLABLE_SCOPED:
            await _ddl(f"ALTER TABLE {table} ALTER COLUMN connection_id SET NOT NULL", ignore=True)
        ondelete = "SET NULL" if table in _NULLABLE_SCOPED else "CASCADE"
        await _ddl(
            f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_connection "
            f"FOREIGN KEY (connection_id) REFERENCES connections(id) ON DELETE {ondelete}",
            ignore=True,
        )

    for table, fk_name, column, target in _CASCADE_FKS:
        await _ddl(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {fk_name}", ignore=True)
        await _ddl(
            f"ALTER TABLE {table} ADD CONSTRAINT {fk_name} "
            f"FOREIGN KEY ({column}) REFERENCES {target}(id) ON DELETE CASCADE",
            ignore=True,
        )

    # table_name deixa de ser único globalmente e passa a ser único por conexão.
    await _ddl("ALTER TABLE tables DROP CONSTRAINT IF EXISTS tables_table_name_key", ignore=True)
    await _ddl(
        "ALTER TABLE tables ADD CONSTRAINT uq_tables_connection_table_name "
        "UNIQUE (connection_id, table_name)",
        ignore=True,
    )


async def _update_connection_stats(session: AsyncSession, connection: Connection) -> None:
    count = await session.scalar(
        text("SELECT COUNT(*) FROM tables WHERE connection_id = :cid"), {"cid": connection.id}
    )
    connection.table_count = count or 0
    await session.execute(
        text("UPDATE connections SET last_introspected_at = NOW() WHERE id = :cid"),
        {"cid": connection.id},
    )


async def migrate() -> None:
    configure_logging()
    await _ensure_connections_table()

    await _add_columns()

    async with get_metadata_session() as session:
        connection = await _get_or_create_connection(session)
        await _backfill(session, connection.id)
        await session.commit()

    await _apply_constraints()

    async with get_metadata_session() as session:
        connection = await _get_or_create_connection(session)
        await _update_connection_stats(session, connection)
        await session.commit()

    logger.info("migration_complete", connection=CONNECTION_NAME)


def main() -> None:
    asyncio.run(migrate())


if __name__ == "__main__":
    main()
