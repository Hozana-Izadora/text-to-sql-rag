import asyncio
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import build_graph
from app.core.logging import get_logger
from app.database.connection import db_session_dependency, get_metadata_session

logger = get_logger(__name__)

_HEALTH_CHECK_TIMEOUT_SECONDS = 3


@lru_cache
def get_pipeline_graph() -> Any:
    """Constrói o grafo LangGraph compilado uma vez por processo (mesmo padrão de
    get_embedding_service). Overridable em testes via app.dependency_overrides."""
    return build_graph()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Sessão do banco de metadados para `Depends`."""
    async for session in db_session_dependency():
        yield session


async def check_metadata_db() -> bool:
    """Ping simples no banco de metadados, com timeout próprio."""
    try:

        async def _ping() -> None:
            async with get_metadata_session() as session:
                await session.execute(text("SELECT 1"))

        await asyncio.wait_for(_ping(), timeout=_HEALTH_CHECK_TIMEOUT_SECONDS)
        return True
    except Exception as exc:
        logger.warning("metadata_db_health_check_failed", error=str(exc))
        return False
