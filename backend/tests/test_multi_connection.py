import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.metadata.embeddings import EmbeddingService
from app.metadata.models import Connection
from app.metadata.repository import MetadataRepository
from app.metadata.schemas import SynonymCreate, TableCreate

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="session")
def embedding_service() -> EmbeddingService:
    return EmbeddingService()


async def _make_connection(session: AsyncSession, name: str) -> Connection:
    connection = Connection(
        name=name,
        db_type="postgresql",
        host="h",
        port=5432,
        database_name="d",
        username="u",
        password_encrypted="x",
    )
    session.add(connection)
    await session.flush()
    return connection


async def test_embedding_search_is_scoped_per_connection(
    metadata_session: AsyncSession, embedding_service: EmbeddingService
) -> None:
    conn_a = await _make_connection(metadata_session, "A")
    conn_b = await _make_connection(metadata_session, "B")
    repository = MetadataRepository(metadata_session)

    table_a = await repository.upsert_table(conn_a.id, TableCreate(table_name="apolices"))
    table_b = await repository.upsert_table(conn_b.id, TableCreate(table_name="pedidos"))

    text_a = "Tabela apolices: contratos de seguro vigentes"
    text_b = "Tabela pedidos: pedidos de compra da loja"
    await repository.add_embedding(
        conn_a.id, "table", table_a.id, text_a, embedding_service.generate([text_a])[0]
    )
    await repository.add_embedding(
        conn_b.id, "table", table_b.id, text_b, embedding_service.generate([text_b])[0]
    )
    await metadata_session.commit()

    results_a = await embedding_service.search(
        metadata_session, "quais seguros estão vigentes", connection_id=conn_a.id
    )
    assert results_a
    assert all(r.source_id == table_a.id for r in results_a)

    results_b = await embedding_service.search(
        metadata_session, "quais seguros estão vigentes", connection_id=conn_b.id
    )
    assert all(r.source_id == table_b.id for r in results_b)


async def test_synonym_search_is_scoped_per_connection(metadata_session: AsyncSession) -> None:
    conn_a = await _make_connection(metadata_session, "A")
    conn_b = await _make_connection(metadata_session, "B")
    repository = MetadataRepository(metadata_session)

    table_a = await repository.upsert_table(conn_a.id, TableCreate(table_name="clients"))
    table_b = await repository.upsert_table(conn_b.id, TableCreate(table_name="clients"))
    await repository.add_synonym(
        conn_a.id, SynonymCreate(entity_type="table", entity_id=table_a.id, synonym="segurados")
    )
    await repository.add_synonym(
        conn_b.id, SynonymCreate(entity_type="table", entity_id=table_b.id, synonym="segurados")
    )
    await metadata_session.commit()

    matches = await repository.search_synonyms("segurados", connection_id=conn_a.id)
    assert len(matches) == 1
    assert matches[0].table_name == "clients"


async def test_deleting_connection_cascades_metadata(metadata_session: AsyncSession) -> None:
    connection = await _make_connection(metadata_session, "Doomed")
    repository = MetadataRepository(metadata_session)
    table = await repository.upsert_table(connection.id, TableCreate(table_name="temp"))
    await repository.add_synonym(
        connection.id, SynonymCreate(entity_type="table", entity_id=table.id, synonym="tmp")
    )
    await metadata_session.commit()

    await metadata_session.delete(connection)
    await metadata_session.commit()

    assert await repository.list_tables(connection.id) == []
    assert await repository.search_synonyms("tmp", connection_id=connection.id) == []
