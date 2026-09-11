import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.connection_schemas import (
    ConnectionCreate,
    ConnectionDetailResponse,
    ConnectionResponse,
    ConnectionTestRequest,
    ConnectionTestResult,
    ConnectionUpdate,
    IntrospectionResult,
)
from app.api.dependencies import get_db_session
from app.core.encryption import get_encryptor
from app.core.logging import get_logger
from app.database.connection import get_metadata_session
from app.database.introspection import get_introspector
from app.database.introspection.types import ConnectionConfig
from app.metadata.connections import config_from_row, get_connection
from app.metadata.embeddings import get_embedding_service_async
from app.metadata.ingestion import persist_introspection
from app.metadata.models import Column, Connection, Table

logger = get_logger(__name__)

router = APIRouter(prefix="/api/connections", tags=["connections"])


async def _load_or_404(session: AsyncSession, connection_id: uuid.UUID) -> Connection:
    connection = await session.get(Connection, connection_id)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conexão não encontrada.")
    return connection


async def run_introspection(connection_id: uuid.UUID) -> IntrospectionResult:
    """Introspecta o banco da conexão e persiste no banco de metadados.

    Abre a própria sessão — usada tanto como BackgroundTask quanto direto no endpoint.
    """
    embedding_service = await get_embedding_service_async()
    async with get_metadata_session() as session:
        connection = await get_connection(session, connection_id)
        config = config_from_row(connection)
        introspector = get_introspector(config)
        tables = await introspector.introspect()

        stats = await persist_introspection(session, connection, tables, embedding_service)

        connection.last_introspected_at = datetime.now(UTC)
        connection.table_count = stats.tables
        await session.commit()

    logger.info(
        "connection_introspected",
        connection_id=str(connection_id),
        tables=stats.tables,
        columns=stats.columns,
        relationships=stats.relationships,
    )
    return IntrospectionResult(
        tables=stats.tables,
        columns=stats.columns,
        relationships=stats.relationships,
        embeddings=stats.embeddings,
        warnings=stats.warnings,
    )


async def _test_config(config: ConnectionConfig) -> ConnectionTestResult:
    try:
        return await get_introspector(config).test_connection()
    except NotImplementedError as exc:
        return ConnectionTestResult(success=False, message=str(exc))


@router.get("/", response_model=list[ConnectionResponse])
async def list_connections(session: Annotated[AsyncSession, Depends(get_db_session)]) -> list[Connection]:
    result = await session.execute(select(Connection).order_by(Connection.created_at))
    return list(result.scalars().all())


@router.post("/test", response_model=ConnectionTestResult)
async def test_new_connection(request: ConnectionTestRequest) -> ConnectionTestResult:
    """Testa credenciais sem persistir nada (botão "Testar conexão" do modal)."""
    return await _test_config(request.to_config())


@router.post("/", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(
    request: ConnectionCreate,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Connection:
    test_result = await _test_config(request.to_config())
    if not test_result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não foi possível conectar ao banco: {test_result.message}",
        )

    connection = Connection(
        name=request.name,
        db_type=request.db_type,
        host=request.host,
        port=request.port,
        database_name=request.database_name,
        username=request.username,
        password_encrypted=get_encryptor().encrypt(request.password),
        ssl_enabled=request.ssl_enabled,
        schema_name=request.schema_name,
    )
    session.add(connection)
    await session.commit()
    await session.refresh(connection)

    background_tasks.add_task(run_introspection, connection.id)
    return connection


@router.get("/{connection_id}", response_model=ConnectionDetailResponse)
async def get_connection_detail(
    connection_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_db_session)]
) -> ConnectionDetailResponse:
    connection = await _load_or_404(session, connection_id)
    column_count = await session.scalar(
        select(func.count(Column.id)).join(Table, Column.table_id == Table.id).where(
            Table.connection_id == connection_id
        )
    )
    return ConnectionDetailResponse(
        **ConnectionResponse.model_validate(connection).model_dump(),
        column_count=column_count or 0,
    )


@router.put("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: uuid.UUID,
    request: ConnectionUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Connection:
    connection = await _load_or_404(session, connection_id)

    for attr in ("name", "host", "port", "database_name", "username", "schema_name", "ssl_enabled", "is_active"):
        value = getattr(request, attr)
        if value is not None:
            setattr(connection, attr, value)
    if request.password is not None:
        connection.password_encrypted = get_encryptor().encrypt(request.password)

    if request.touches_credentials():
        test_result = await _test_config(config_from_row(connection))
        if not test_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Credenciais atualizadas não conectam: {test_result.message}",
            )

    await session.commit()
    await session.refresh(connection)
    return connection


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_db_session)]
) -> None:
    connection = await _load_or_404(session, connection_id)
    await session.delete(connection)  # ON DELETE CASCADE limpa todos os metadados
    await session.commit()


@router.post("/{connection_id}/test", response_model=ConnectionTestResult)
async def test_connection(
    connection_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_db_session)]
) -> ConnectionTestResult:
    connection = await _load_or_404(session, connection_id)
    return await _test_config(config_from_row(connection))


@router.post("/{connection_id}/introspect", response_model=IntrospectionResult)
async def introspect_connection(
    connection_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_db_session)]
) -> IntrospectionResult:
    await _load_or_404(session, connection_id)
    try:
        return await run_introspection(connection_id)
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
