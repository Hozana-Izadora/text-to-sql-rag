"""Acesso à tabela `connections` e conversão para `ConnectionConfig`.

Camada fina entre o modelo ORM `Connection` (senha criptografada) e o resto do
sistema, que trabalha com `ConnectionConfig` (senha em texto plano, pronta para abrir
a conexão).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import get_encryptor
from app.database.introspection.types import ConnectionConfig
from app.metadata.models import Connection


class ConnectionNotFoundError(Exception):
    def __init__(self, connection_id: uuid.UUID | str) -> None:
        super().__init__(f"Conexão não encontrada: {connection_id}")


async def get_connection(session: AsyncSession, connection_id: uuid.UUID | str) -> Connection:
    result = await session.execute(select(Connection).where(Connection.id == connection_id))
    connection = result.scalar_one_or_none()
    if connection is None:
        raise ConnectionNotFoundError(connection_id)
    return connection


async def list_connections(session: AsyncSession, *, active_only: bool = False) -> list[Connection]:
    stmt = select(Connection).order_by(Connection.created_at)
    if active_only:
        stmt = stmt.where(Connection.is_active.is_(True))
    result = await session.execute(stmt)
    return list(result.scalars().all())


def config_from_row(connection: Connection) -> ConnectionConfig:
    """Descriptografa a senha e monta o `ConnectionConfig` da conexão."""
    return ConnectionConfig(
        db_type=connection.db_type,
        host=connection.host,
        port=connection.port,
        database_name=connection.database_name,
        username=connection.username,
        password=get_encryptor().decrypt(connection.password_encrypted),
        ssl_enabled=connection.ssl_enabled,
        schema_name=connection.schema_name,
    )
