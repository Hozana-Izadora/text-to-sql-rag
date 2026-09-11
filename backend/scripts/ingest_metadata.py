"""Script CLI de ingestão de metadados para uma conexão cadastrada.

Introspecta o banco da conexão (via `get_introspector`), aplica o enriquecimento de
`data/dictionary.yaml` (descrições, sinônimos, enum values, regras de negócio) e
persiste tudo no banco de metadados (pgvector), escopado por `connection_id`.

Por padrão usa a conexão "Produção SeguraPro" criada pelo script de migração
(`scripts.migrate_to_multi_connection`). Rode aquele antes deste numa instalação nova.

Uso:
    uv run python -m scripts.ingest_metadata [--connection "Produção SeguraPro"]
"""

import argparse
import asyncio
import uuid
from pathlib import Path

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import configure_logging, get_logger
from app.database.connection import _metadata_engine, get_metadata_session
from app.database.introspection import get_introspector
from app.metadata.connections import config_from_row
from app.metadata.dictionary import DataDictionary, load_dictionary
from app.metadata.embeddings import EmbeddingService
from app.metadata.ingestion import column_embedding_text, persist_introspection, rule_embedding_text
from app.metadata.models import (
    Base,
    BusinessRule,
    Connection,
    EnumValue,
    MetadataEmbedding,
    Synonym,
)
from app.metadata.repository import MetadataRepository
from app.metadata.schemas import BusinessRuleCreate, ColumnCreate, EnumValueCreate, SynonymCreate

logger = get_logger(__name__)

DICTIONARY_PATH = Path(__file__).resolve().parents[2] / "data" / "dictionary.yaml"
DEFAULT_CONNECTION_NAME = "Produção SeguraPro"


async def _ensure_schema() -> None:
    async with _metadata_engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.create_all)


async def _resolve_connection(session: AsyncSession, name: str) -> Connection:
    result = await session.execute(select(Connection).where(Connection.name == name))
    connection = result.scalar_one_or_none()
    if connection is None:
        raise SystemExit(
            f"Conexão '{name}' não encontrada. Rode 'uv run python -m scripts.migrate_to_multi_connection' primeiro."
        )
    return connection


async def _clear_dictionary_derived(session: AsyncSession, connection_id: uuid.UUID) -> None:
    """Remove synonyms/enum_values/business_rules + rule embeddings da conexão para reaplicar do zero."""
    await session.execute(delete(Synonym).where(Synonym.connection_id == connection_id))
    await session.execute(delete(EnumValue).where(EnumValue.connection_id == connection_id))
    await session.execute(
        delete(MetadataEmbedding).where(
            MetadataEmbedding.connection_id == connection_id, MetadataEmbedding.source_type == "rule"
        )
    )
    await session.execute(delete(BusinessRule).where(BusinessRule.connection_id == connection_id))
    await session.flush()


async def _apply_dictionary(
    session: AsyncSession,
    connection: Connection,
    dictionary: DataDictionary,
    embedding_service: EmbeddingService,
) -> None:
    repository = MetadataRepository(session)
    tables = await repository.list_tables_detailed(connection.id)

    for table in tables:
        table_dict = dictionary.table(table.table_name)
        if table_dict is None:
            continue
        if table_dict.description:
            table.description = table_dict.description
        for synonym in table_dict.synonyms:
            await repository.add_synonym(
                connection.id,
                SynonymCreate(entity_type="table", entity_id=table.id, synonym=synonym),
            )

        for column in table.columns:
            column_dict = dictionary.column(table.table_name, column.column_name)
            if column_dict is None:
                continue
            if column_dict.description:
                column.description = column_dict.description
            column_synonyms = column_dict.synonyms
            for synonym in column_synonyms:
                await repository.add_synonym(
                    connection.id,
                    SynonymCreate(entity_type="column", entity_id=column.id, synonym=synonym),
                )
            for stored_value, enum_dict in column_dict.enum_values.items():
                await repository.add_enum_value(
                    connection.id,
                    column.id,
                    EnumValueCreate(
                        stored_value=stored_value,
                        display_label=enum_dict.label,
                        description=enum_dict.description,
                    ),
                )
            if column_dict.description or column_synonyms:
                payload = ColumnCreate(
                    column_name=column.column_name,
                    data_type=column.data_type,
                    is_nullable=column.is_nullable,
                    is_primary_key=column.is_primary_key,
                    is_foreign_key=column.is_foreign_key,
                    description=column.description,
                    sample_values=column.sample_values or [],
                )
                content = column_embedding_text(table.table_name, payload, column_synonyms)
                await repository.refresh_embedding(
                    connection.id, "column", column.id, content, embedding_service.generate([content])[0]
                )

    await session.flush()

    for rule in dictionary.business_rules:
        table_id = None
        if rule.table:
            match = next((t for t in tables if t.table_name == rule.table), None)
            table_id = match.id if match else None
        db_rule = await repository.add_business_rule(
            connection.id, table_id, BusinessRuleCreate(rule_text=rule.text, rule_type=rule.type)
        )
        content = rule_embedding_text(rule.table, rule.text)
        await repository.add_embedding(
            connection.id, "rule", db_rule.id, content, embedding_service.generate([content])[0]
        )


async def ingest(connection_name: str) -> None:
    configure_logging()
    await _ensure_schema()

    dictionary = load_dictionary(DICTIONARY_PATH)
    embedding_service = await asyncio.to_thread(EmbeddingService)

    async with get_metadata_session() as session:
        connection = await _resolve_connection(session, connection_name)
        config = config_from_row(connection)

        introspector = get_introspector(config)
        introspected = await introspector.introspect()

        await _clear_dictionary_derived(session, connection.id)
        stats = await persist_introspection(session, connection, introspected, embedding_service)
        await _apply_dictionary(session, connection, dictionary, embedding_service)

        await session.commit()

    logger.info(
        "ingestion_complete",
        connection=connection_name,
        tables=stats.tables,
        columns=stats.columns,
        relationships=stats.relationships,
        embeddings=stats.embeddings,
        warnings=stats.warnings,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestão de metadados de uma conexão.")
    parser.add_argument("--connection", default=DEFAULT_CONNECTION_NAME, help="Nome da conexão cadastrada.")
    args = parser.parse_args()
    asyncio.run(ingest(args.connection))


if __name__ == "__main__":
    main()
