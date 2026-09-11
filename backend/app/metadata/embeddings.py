import asyncio
import uuid
from functools import lru_cache

from sentence_transformers import SentenceTransformer
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.metadata.models import MetadataEmbedding, SyntheticExample
from app.metadata.schemas import SearchResult, SyntheticExampleMatch

logger = get_logger(__name__)


class EmbeddingService:
    def __init__(self, model_name: str = settings.embedding_model):
        """Carrega modelo sentence-transformers. Roda em CPU."""
        self.model_name = model_name
        self._model = SentenceTransformer(model_name, device="cpu")

    def generate(self, texts: list[str], prefix: str = "passage: ") -> list[list[float]]:
        """Gera embeddings para uma lista de textos.

        O multilingual-e5-small exige prefixos para funcionar bem: "passage: "
        para conteúdo indexado (default) e "query: " para perguntas de busca.
        """
        prefixed_texts = [f"{prefix}{text}" for text in texts]
        vectors = self._model.encode(
            prefixed_texts, convert_to_numpy=True, show_progress_bar=False, normalize_embeddings=True
        )
        return [vector.tolist() for vector in vectors]

    async def search(
        self,
        session: AsyncSession,
        query: str,
        source_types: list[str] | None = None,
        top_k: int = 10,
        connection_id: uuid.UUID | None = None,
    ) -> list[SearchResult]:
        """Busca os top_k metadados mais similares à query.

        Usa pgvector com operador <=> (cosine distance).
        Filtra por source_type e/ou connection_id se especificados.
        """
        query_embedding = self.generate([query], prefix="query: ")[0]

        distance = MetadataEmbedding.embedding.cosine_distance(query_embedding).label("distance")
        stmt = select(MetadataEmbedding, distance).order_by(distance).limit(top_k)
        if source_types:
            stmt = stmt.where(MetadataEmbedding.source_type.in_(source_types))
        if connection_id is not None:
            stmt = stmt.where(MetadataEmbedding.connection_id == connection_id)

        result = await session.execute(stmt)
        rows = result.all()

        return [
            SearchResult(
                source_type=row.MetadataEmbedding.source_type,
                source_id=row.MetadataEmbedding.source_id,
                content_text=row.MetadataEmbedding.content_text,
                distance=row.distance,
            )
            for row in rows
        ]

    async def search_synthetic_examples(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 5,
        connection_id: uuid.UUID | None = None,
    ) -> list[SyntheticExampleMatch]:
        """Busca os top_k exemplos few-shot (question_nl, query_sql) mais similares à query.

        SyntheticExample tem sua própria coluna `embedding` (índice HNSW separado),
        fora de `metadata_embeddings` — por isso não é alcançada por `search()`.
        """
        query_embedding = self.generate([query], prefix="query: ")[0]

        distance = SyntheticExample.embedding.cosine_distance(query_embedding).label("distance")
        stmt = select(SyntheticExample, distance).order_by(distance).limit(top_k)
        if connection_id is not None:
            stmt = stmt.where(
                or_(
                    SyntheticExample.connection_id == connection_id,
                    SyntheticExample.connection_id.is_(None),
                )
            )

        result = await session.execute(stmt)
        return [
            SyntheticExampleMatch(
                id=row.SyntheticExample.id,
                question_nl=row.SyntheticExample.question_nl,
                query_sql=row.SyntheticExample.query_sql,
                tables_used=row.SyntheticExample.tables_used or [],
                distance=row.distance,
            )
            for row in result
        ]


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Singleton por processo — evita recarregar o SentenceTransformer a cada chamada.

    Síncrona de propósito: SentenceTransformer(...) faz I/O bloqueante (checagem de
    cache/download do Hugging Face Hub na primeira carga) — chamar isso direto de
    dentro de uma função async trava o event loop. Use get_embedding_service_async()
    a partir de código async (nós do grafo, lifespan do FastAPI, scripts async).
    """
    return EmbeddingService()


_embedding_service_lock = asyncio.Lock()


async def get_embedding_service_async() -> EmbeddingService:
    """Acesso async-safe ao singleton — roda a construção em thread separada
    (asyncio.to_thread) para não bloquear o event loop na primeira carga do modelo.
    Chamadas subsequentes só pagam o custo de um lookup no lru_cache."""
    async with _embedding_service_lock:
        return await asyncio.to_thread(get_embedding_service)
