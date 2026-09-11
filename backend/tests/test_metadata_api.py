import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.metadata.models import Connection, MetadataEmbedding
from app.metadata.repository import MetadataRepository
from app.metadata.schemas import ColumnCreate, TableCreate

pytestmark = pytest.mark.asyncio


async def _seed_connection_with_table(session: AsyncSession) -> tuple[Connection, object, object]:
    connection = Connection(
        name="Seed",
        db_type="postgresql",
        host="h",
        port=5432,
        database_name="d",
        username="u",
        password_encrypted="x",
    )
    session.add(connection)
    await session.flush()

    repository = MetadataRepository(session)
    table = await repository.upsert_table(connection.id, TableCreate(table_name="policies"))
    column = await repository.upsert_column(
        table.id, ColumnCreate(column_name="premium_amount", data_type="numeric")
    )
    await session.commit()
    return connection, table, column


async def test_update_column_description_regenerates_embedding(
    app_client, metadata_session: AsyncSession
) -> None:
    connection, _table, column = await _seed_connection_with_table(metadata_session)

    response = await app_client.put(
        f"/api/connections/{connection.id}/metadata/columns/{column.id}",
        json={"description": "Valor total do prêmio da apólice"},
    )
    assert response.status_code == 204

    row = await metadata_session.scalar(
        select(MetadataEmbedding).where(
            MetadataEmbedding.source_type == "column", MetadataEmbedding.source_id == column.id
        )
    )
    assert row is not None
    assert "Valor total do prêmio" in row.content_text
    assert row.connection_id == connection.id


async def test_create_and_list_business_rule(app_client, metadata_session: AsyncSession) -> None:
    connection, table, _column = await _seed_connection_with_table(metadata_session)

    created = await app_client.post(
        f"/api/connections/{connection.id}/metadata/business-rules",
        json={"table_id": str(table.id), "rule_text": "Apólices vigentes: status = 'active'", "rule_type": "filter"},
    )
    assert created.status_code == 201

    listed = await app_client.get(f"/api/connections/{connection.id}/metadata/business-rules")
    assert listed.status_code == 200
    assert listed.json()[0]["rule_text"] == "Apólices vigentes: status = 'active'"

    rule_embedding = await metadata_session.scalar(
        select(MetadataEmbedding).where(MetadataEmbedding.source_type == "rule")
    )
    assert rule_embedding is not None


async def test_add_and_remove_column_synonym(app_client, metadata_session: AsyncSession) -> None:
    connection, _table, column = await _seed_connection_with_table(metadata_session)

    created = await app_client.post(
        f"/api/connections/{connection.id}/metadata/tables/{_table.id}/synonyms",
        json={"entity_type": "column", "entity_id": str(column.id), "synonym": "prêmio"},
    )
    assert created.status_code == 201
    synonym_id = created.json()["id"]

    tables = await app_client.get(f"/api/connections/{connection.id}/metadata/tables")
    column_payload = tables.json()[0]["columns"][0]
    assert any(s["synonym"] == "prêmio" for s in column_payload["synonyms"])

    removed = await app_client.delete(
        f"/api/connections/{connection.id}/metadata/synonyms/{synonym_id}"
    )
    assert removed.status_code == 204
