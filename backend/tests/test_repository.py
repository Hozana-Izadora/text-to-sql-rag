import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.metadata.models import Connection
from app.metadata.repository import MetadataRepository
from app.metadata.schemas import ColumnCreate, SynonymCreate, TableCreate

pytestmark = pytest.mark.asyncio


async def test_upsert_table_inserts_then_updates(
    metadata_session: AsyncSession, connection_row: Connection
) -> None:
    repository = MetadataRepository(metadata_session)

    created = await repository.upsert_table(
        connection_row.id, TableCreate(table_name="customers", description="v1")
    )
    updated = await repository.upsert_table(
        connection_row.id, TableCreate(table_name="customers", description="v2")
    )
    await metadata_session.commit()

    assert created.id == updated.id
    assert updated.description == "v2"

    tables = await repository.list_tables(connection_row.id)
    assert len(tables) == 1


async def test_upsert_column_and_add_synonym(
    metadata_session: AsyncSession, connection_row: Connection
) -> None:
    repository = MetadataRepository(metadata_session)
    table = await repository.upsert_table(connection_row.id, TableCreate(table_name="orders"))

    column = await repository.upsert_column(
        table.id, ColumnCreate(column_name="total_amount", data_type="numeric", description="valor do pedido")
    )
    synonym = await repository.add_synonym(
        connection_row.id,
        SynonymCreate(entity_type="column", entity_id=column.id, synonym="valor"),
    )
    await metadata_session.commit()

    fetched_table = await repository.get_table_by_name("orders", connection_id=connection_row.id)
    assert fetched_table is not None
    assert fetched_table.columns[0].column_name == "total_amount"
    assert synonym.synonym == "valor"


async def test_same_table_name_across_two_connections_is_isolated(
    metadata_session: AsyncSession, connection_row: Connection
) -> None:
    repository = MetadataRepository(metadata_session)
    other = Connection(
        name="Other",
        db_type="mysql",
        host="h",
        port=3306,
        database_name="d",
        username="u",
        password_encrypted="x",
    )
    metadata_session.add(other)
    await metadata_session.flush()

    await repository.upsert_table(connection_row.id, TableCreate(table_name="clients"))
    await repository.upsert_table(other.id, TableCreate(table_name="clients"))
    await metadata_session.commit()

    assert len(await repository.list_tables(connection_row.id)) == 1
    assert len(await repository.list_tables(other.id)) == 1
    assert len(await repository.list_tables()) == 2


async def test_get_table_by_name_returns_none_when_missing(metadata_session: AsyncSession) -> None:
    repository = MetadataRepository(metadata_session)

    result = await repository.get_table_by_name("does_not_exist")

    assert result is None
