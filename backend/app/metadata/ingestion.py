"""Persistência de um schema introspectado no banco de metadados + embeddings.

Compartilhado entre o endpoint `POST /api/connections/{id}/introspect` e o script
`scripts/ingest_metadata.py`. Escopa tudo por `connection_id` e preserva descrições
já existentes (o usuário pode tê-las editado pela API) numa re-introspecção.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database.introspection.types import TableMetadata
from app.metadata.embeddings import EmbeddingService
from app.metadata.models import Connection
from app.metadata.repository import MetadataRepository
from app.metadata.schemas import ColumnCreate, RelationshipCreate, TableCreate

logger = get_logger(__name__)


@dataclass
class IngestionStats:
    tables: int = 0
    columns: int = 0
    relationships: int = 0
    embeddings: int = 0
    synonyms: int = 0
    business_rules: int = 0
    enum_values: int = 0
    warnings: list[str] = field(default_factory=list)


def table_embedding_text(table_name: str, description: str | None, columns: list[ColumnCreate]) -> str:
    columns_text = ", ".join(f"{c.column_name} ({c.data_type})" for c in columns)
    return f"Tabela {table_name}: {description or ''}. Colunas: {columns_text}"


def column_embedding_text(
    table_name: str, column: ColumnCreate, synonyms: list[str] | None = None
) -> str:
    synonyms_text = ", ".join(synonyms or [])
    values_text = ", ".join(column.sample_values)
    return (
        f"Coluna {table_name}.{column.column_name} ({column.data_type}): {column.description or ''}. "
        f"Sinônimos: {synonyms_text}. Valores possíveis: {values_text}"
    )


def rule_embedding_text(table_name: str | None, rule_text: str) -> str:
    return f"Regra para {table_name or 'geral'}: {rule_text}"


async def _existing_descriptions(
    repository: MetadataRepository, connection_id: uuid.UUID, table_name: str
) -> tuple[str | None, dict[str, str | None]]:
    existing = await repository.get_table_by_name(table_name, connection_id=connection_id)
    if existing is None:
        return None, {}
    return existing.description, {c.column_name: c.description for c in existing.columns}


async def persist_introspection(
    session: AsyncSession,
    connection: Connection,
    introspected: list[TableMetadata],
    embedding_service: EmbeddingService,
) -> IngestionStats:
    """Upsert de tabelas/colunas/relationships + embeddings para uma conexão.

    Não commita — quem chama controla a transação.
    """
    repository = MetadataRepository(session)
    stats = IngestionStats()
    table_id_by_name: dict[str, uuid.UUID] = {}

    # Relationships são recriadas do zero (não têm chave natural para upsert).
    await repository.delete_relationships_for_connection(connection.id)
    await session.flush()

    for meta in introspected:
        table_description, column_descriptions = await _existing_descriptions(
            repository, connection.id, meta.table_name
        )
        columns = [
            ColumnCreate(
                column_name=c.column_name,
                data_type=c.data_type,
                is_nullable=c.is_nullable,
                is_primary_key=c.is_primary_key,
                is_foreign_key=c.is_foreign_key,
                description=column_descriptions.get(c.column_name),
                sample_values=c.sample_values,
            )
            for c in meta.columns
        ]
        db_table = await repository.upsert_table(
            connection.id,
            TableCreate(
                table_name=meta.table_name,
                schema_name=meta.schema_name,
                description=table_description,
                row_count=meta.row_count,
            ),
        )
        table_id_by_name[meta.table_name] = db_table.id
        stats.tables += 1

        embedding = embedding_service.generate([table_embedding_text(meta.table_name, table_description, columns)])[0]
        await repository.refresh_embedding(
            connection.id, "table", db_table.id, table_embedding_text(meta.table_name, table_description, columns), embedding
        )
        stats.embeddings += 1

        for column in columns:
            db_column = await repository.upsert_column(db_table.id, column)
            stats.columns += 1
            text = column_embedding_text(meta.table_name, column)
            column_embedding = embedding_service.generate([text])[0]
            await repository.refresh_embedding(
                connection.id, "column", db_column.id, text, column_embedding
            )
            stats.embeddings += 1

    # Relationships numa segunda passada (precisa de todos os table_ids resolvidos).
    for meta in introspected:
        source_id = table_id_by_name.get(meta.table_name)
        if source_id is None:
            continue
        for rel in meta.relationships:
            target_id = table_id_by_name.get(rel.target_table)
            if target_id is None:
                stats.warnings.append(
                    f"FK {meta.table_name}.{rel.source_column} aponta para tabela fora do schema: {rel.target_table}"
                )
                continue
            await repository.add_relationship(
                connection.id,
                source_id,
                target_id,
                RelationshipCreate(
                    source_table=rel.source_table,
                    source_column=rel.source_column,
                    target_table=rel.target_table,
                    target_column=rel.target_column,
                    constraint_name=rel.constraint_name,
                ),
            )
            stats.relationships += 1

    return stats
