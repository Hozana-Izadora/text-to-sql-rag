from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.connections import router as connections_router
from app.api.dependencies import get_pipeline_graph
from app.api.metadata import router as metadata_router
from app.api.routes import router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.metadata.embeddings import get_embedding_service_async

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Warm-up no boot (grafo compilado + modelo de embeddings carregado), não na
    primeira request — evita penalizar o primeiro usuário e expõe erros de config
    (ex.: chave de API mal formatada) nos logs de startup em vez de numa request real."""
    await get_embedding_service_async()
    get_pipeline_graph()
    logger.info("app_startup_complete")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Inquiro API",
        description="Da pergunta ao insight — API de Text-to-SQL inteligente",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.include_router(connections_router)
    app.include_router(metadata_router)

    return app


app = create_app()
