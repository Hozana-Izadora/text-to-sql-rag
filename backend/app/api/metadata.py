import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.api.metadata_schemas import (
    BusinessRuleCreateRequest,
    BusinessRuleResponse,
    BusinessRuleUpdateRequest,
    ColumnDetail,
    ColumnUpdate,
    EnumValueCreateRequest,
    EnumValueResponse,
    SynonymCreateRequest,
    SynonymResponse,
    TableDetailResponse,
    TableUpdate,
)
from app.core.logging import get_logger
from app.metadata.embeddings import get_embedding_service_async
from app.metadata.ingestion import column_embedding_text, rule_embedding_text, table_embedding_text
from app.metadata.models import Connection
from app.metadata.repository import MetadataRepository
from app.metadata.schemas import BusinessRuleCreate, ColumnCreate, EnumValueCreate, SynonymCreate

logger = get_logger(__name__)

router = APIRouter(prefix="/api/connections/{connection_id}/metadata", tags=["metadata"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso não encontrado.")


async def _ensure_connection(session: AsyncSession, connection_id: uuid.UUID) -> None:
    if await session.get(Connection, connection_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conexão não encontrada.")


def _column_to_create(column) -> ColumnCreate:
    return ColumnCreate(
        column_name=column.column_name,
        data_type=column.data_type,
        is_nullable=column.is_nullable,
        is_primary_key=column.is_primary_key,
        is_foreign_key=column.is_foreign_key,
        description=column.description,
        sample_values=column.sample_values or [],
    )


async def _refresh_table_embedding(
    repository: MetadataRepository, connection_id: uuid.UUID, table
) -> None:
    embedding_service = await get_embedding_service_async()
    columns = [_column_to_create(c) for c in table.columns]
    text = table_embedding_text(table.table_name, table.description, columns)
    vector = embedding_service.generate([text])[0]
    await repository.refresh_embedding(connection_id, "table", table.id, text, vector)


async def _refresh_column_embedding(
    repository: MetadataRepository, connection_id: uuid.UUID, table, column
) -> None:
    embedding_service = await get_embedding_service_async()
    synonyms_by_entity = await repository.list_synonyms_for_entities([column.id])
    synonyms = [s.synonym for s in synonyms_by_entity.get(column.id, [])]
    text = column_embedding_text(table.table_name, _column_to_create(column), synonyms)
    vector = embedding_service.generate([text])[0]
    await repository.refresh_embedding(connection_id, "column", column.id, text, vector)


@router.get("/tables", response_model=list[TableDetailResponse])
async def list_tables(
    connection_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_db_session)]
) -> list[TableDetailResponse]:
    await _ensure_connection(session, connection_id)
    repository = MetadataRepository(session)
    tables = await repository.list_tables_detailed(connection_id)

    entity_ids = [t.id for t in tables] + [c.id for t in tables for c in t.columns]
    synonyms_by_entity = await repository.list_synonyms_for_entities(entity_ids)
    enums_by_column = await repository.list_enum_values_for_columns(
        [c.id for t in tables for c in t.columns]
    )

    def _syns(entity_id: uuid.UUID) -> list[SynonymResponse]:
        return [
            SynonymResponse(id=s.id, synonym=s.synonym, language=s.language)
            for s in synonyms_by_entity.get(entity_id, [])
        ]

    return [
        TableDetailResponse(
            id=table.id,
            table_name=table.table_name,
            schema_name=table.schema_name,
            description=table.description,
            row_count=table.row_count,
            synonyms=_syns(table.id),
            columns=[
                ColumnDetail(
                    id=column.id,
                    column_name=column.column_name,
                    data_type=column.data_type,
                    is_nullable=column.is_nullable,
                    is_primary_key=column.is_primary_key,
                    is_foreign_key=column.is_foreign_key,
                    description=column.description,
                    sample_values=column.sample_values or [],
                    synonyms=_syns(column.id),
                    enum_values=[
                        EnumValueResponse(
                            id=e.id,
                            stored_value=e.stored_value,
                            display_label=e.display_label,
                            description=e.description,
                        )
                        for e in enums_by_column.get(column.id, [])
                    ],
                )
                for column in sorted(table.columns, key=lambda c: c.column_name)
            ],
        )
        for table in tables
    ]


@router.put("/tables/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_table(
    connection_id: uuid.UUID,
    table_id: uuid.UUID,
    request: TableUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    repository = MetadataRepository(session)
    table = await repository.get_table(table_id)
    if table is None or table.connection_id != connection_id:
        raise _NOT_FOUND
    table.description = request.description
    await session.flush()
    await _refresh_table_embedding(repository, connection_id, table)
    await session.commit()


@router.put("/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_column(
    connection_id: uuid.UUID,
    column_id: uuid.UUID,
    request: ColumnUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    repository = MetadataRepository(session)
    column = await repository.get_column(column_id)
    if column is None:
        raise _NOT_FOUND
    table = await repository.get_table(column.table_id)
    if table is None or table.connection_id != connection_id:
        raise _NOT_FOUND
    column.description = request.description
    await session.flush()
    await _refresh_column_embedding(repository, connection_id, table, column)
    await session.commit()


@router.post("/tables/{table_id}/synonyms", response_model=SynonymResponse, status_code=status.HTTP_201_CREATED)
async def add_synonym(
    connection_id: uuid.UUID,
    table_id: uuid.UUID,
    request: SynonymCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SynonymResponse:
    repository = MetadataRepository(session)
    await _ensure_connection(session, connection_id)
    synonym = await repository.add_synonym(
        connection_id,
        SynonymCreate(
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            synonym=request.synonym,
            language=request.language,
        ),
    )
    if request.entity_type == "column":
        column = await repository.get_column(request.entity_id)
        if column is not None:
            table = await repository.get_table(column.table_id)
            if table is not None:
                await _refresh_column_embedding(repository, connection_id, table, column)
    await session.commit()
    return SynonymResponse(id=synonym.id, synonym=synonym.synonym, language=synonym.language)


@router.delete("/synonyms/{synonym_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_synonym(
    connection_id: uuid.UUID,
    synonym_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    repository = MetadataRepository(session)
    synonym = await repository.get_synonym(synonym_id)
    if synonym is None or synonym.connection_id != connection_id:
        raise _NOT_FOUND
    entity_type, entity_id = synonym.entity_type, synonym.entity_id
    await repository.delete_synonym(synonym_id)
    await session.flush()
    if entity_type == "column":
        column = await repository.get_column(entity_id)
        if column is not None:
            table = await repository.get_table(column.table_id)
            if table is not None:
                await _refresh_column_embedding(repository, connection_id, table, column)
    await session.commit()


@router.get("/business-rules", response_model=list[BusinessRuleResponse])
async def list_rules(
    connection_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_db_session)]
) -> list[BusinessRuleResponse]:
    await _ensure_connection(session, connection_id)
    repository = MetadataRepository(session)
    return [
        BusinessRuleResponse(
            id=rule.id, table_id=rule.table_id, rule_text=rule.rule_text, rule_type=rule.rule_type
        )
        for rule in await repository.list_business_rules(connection_id)
    ]


async def _refresh_rule_embedding(
    repository: MetadataRepository, connection_id: uuid.UUID, rule
) -> None:
    embedding_service = await get_embedding_service_async()
    table_name = (
        await repository.get_table_name_by_id(rule.table_id) if rule.table_id is not None else None
    )
    text = rule_embedding_text(table_name, rule.rule_text)
    vector = embedding_service.generate([text])[0]
    await repository.refresh_embedding(connection_id, "rule", rule.id, text, vector)


@router.post("/business-rules", response_model=BusinessRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    connection_id: uuid.UUID,
    request: BusinessRuleCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BusinessRuleResponse:
    await _ensure_connection(session, connection_id)
    repository = MetadataRepository(session)
    rule = await repository.add_business_rule(
        connection_id,
        request.table_id,
        BusinessRuleCreate(rule_text=request.rule_text, rule_type=request.rule_type),
    )
    await _refresh_rule_embedding(repository, connection_id, rule)
    await session.commit()
    return BusinessRuleResponse(
        id=rule.id, table_id=rule.table_id, rule_text=rule.rule_text, rule_type=rule.rule_type
    )


@router.put("/business-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_rule(
    connection_id: uuid.UUID,
    rule_id: uuid.UUID,
    request: BusinessRuleUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    repository = MetadataRepository(session)
    rule = await repository.get_business_rule(rule_id)
    if rule is None or rule.connection_id != connection_id:
        raise _NOT_FOUND
    if request.rule_text is not None:
        rule.rule_text = request.rule_text
    if request.rule_type is not None:
        rule.rule_type = request.rule_type
    await session.flush()
    await _refresh_rule_embedding(repository, connection_id, rule)
    await session.commit()


@router.delete("/business-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    connection_id: uuid.UUID,
    rule_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    repository = MetadataRepository(session)
    rule = await repository.get_business_rule(rule_id)
    if rule is None or rule.connection_id != connection_id:
        raise _NOT_FOUND
    await repository.delete_business_rule(rule_id)
    await session.commit()


@router.post("/enum-values", response_model=EnumValueResponse, status_code=status.HTTP_201_CREATED)
async def add_enum_value(
    connection_id: uuid.UUID,
    request: EnumValueCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EnumValueResponse:
    repository = MetadataRepository(session)
    column = await repository.get_column(request.column_id)
    if column is None:
        raise _NOT_FOUND
    table = await repository.get_table(column.table_id)
    if table is None or table.connection_id != connection_id:
        raise _NOT_FOUND
    enum_value = await repository.add_enum_value(
        connection_id,
        request.column_id,
        EnumValueCreate(
            stored_value=request.stored_value,
            display_label=request.display_label,
            description=request.description,
        ),
    )
    await session.commit()
    return EnumValueResponse(
        id=enum_value.id,
        stored_value=enum_value.stored_value,
        display_label=enum_value.display_label,
        description=enum_value.description,
    )


@router.delete("/enum-values/{enum_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_enum_value(
    connection_id: uuid.UUID,
    enum_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    repository = MetadataRepository(session)
    enum_value = await repository.get_enum_value(enum_id)
    if enum_value is None or enum_value.connection_id != connection_id:
        raise _NOT_FOUND
    await repository.delete_enum_value(enum_id)
    await session.commit()
