import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.metadata.embeddings import EmbeddingService
from app.metadata.models import MetadataEmbedding


@pytest.fixture(scope="session")
def embedding_service() -> EmbeddingService:
    return EmbeddingService()


def test_generate_returns_vectors_with_configured_dimension(embedding_service: EmbeddingService) -> None:
    vectors = embedding_service.generate(["tabela de clientes", "tabela de pedidos"])

    assert len(vectors) == 2
    assert all(len(vector) == settings.embedding_dimensions for vector in vectors)


@pytest.mark.asyncio
async def test_search_returns_results_ordered_by_similarity(
    embedding_service: EmbeddingService, metadata_session: AsyncSession, connection_row
) -> None:
    texts = {
        "table": "Tabela customers: cadastro de clientes ativos e inativos",
        "rule": "Regra para orders: valores monetários estão em BRL",
    }
    for source_type, content_text in texts.items():
        embedding = embedding_service.generate([content_text])[0]
        metadata_session.add(
            MetadataEmbedding(
                connection_id=connection_row.id,
                source_type=source_type,
                source_id=uuid.uuid4(),
                content_text=content_text,
                embedding=embedding,
            )
        )
    await metadata_session.commit()

    results = await embedding_service.search(metadata_session, "quem são os clientes cadastrados", top_k=2)

    assert len(results) == 2
    assert results[0].source_type == "table"
    assert results[0].distance <= results[1].distance
