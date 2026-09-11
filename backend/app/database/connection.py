from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_metadata_engine: AsyncEngine = create_async_engine(settings.metadata_db_url, pool_pre_ping=True)
_metadata_session_factory = async_sessionmaker(_metadata_engine, expire_on_commit=False)


@asynccontextmanager
async def get_metadata_session() -> AsyncIterator[AsyncSession]:
    """Sessão SQLAlchemy assíncrona para o banco de metadados (pgvector)."""
    async with _metadata_session_factory() as session:
        yield session


async def db_session_dependency() -> AsyncIterator[AsyncSession]:
    """Versão para `fastapi.Depends` (async generator, não context manager)."""
    async with _metadata_session_factory() as session:
        yield session
