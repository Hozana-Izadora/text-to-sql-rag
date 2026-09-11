from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.metadata.models import Base, Connection

_PRODUCTION_SCHEMA_SQL = """
CREATE TABLE brokers (
    id SERIAL PRIMARY KEY,
    registration_number VARCHAR(20) UNIQUE NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    hire_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','inactive','on_leave')),
    commission_rate DECIMAL(5,2) NOT NULL DEFAULT 10.00
);

CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    client_type VARCHAR(2) NOT NULL CHECK (client_type IN ('PF','PJ')),
    full_name VARCHAR(300) NOT NULL,
    broker_id INTEGER REFERENCES brokers(id),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','inactive','prospect'))
);

CREATE TABLE policies (
    id SERIAL PRIMARY KEY,
    policy_number VARCHAR(30) UNIQUE NOT NULL,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    broker_id INTEGER NOT NULL REFERENCES brokers(id),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    premium_amount DECIMAL(12,2) NOT NULL,
    is_main BOOLEAN NOT NULL DEFAULT false,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','expired','cancelled'))
);

INSERT INTO brokers (registration_number, full_name, hire_date, status, commission_rate)
    VALUES ('SUSEP-001', 'Ana Costa', '2020-03-10', 'active', 12.50);
INSERT INTO clients (client_type, full_name, broker_id, status)
    VALUES ('PF', 'Carlos Souza', 1, 'active'), ('PJ', 'Comercial Ltda', NULL, 'prospect');
INSERT INTO policies (policy_number, client_id, broker_id, start_date, end_date, premium_amount, is_main, status)
    VALUES ('POL-0001', 1, 1, '2024-01-01', '2025-01-01', 1200.00, true, 'active'),
           ('POL-0002', 2, 1, '2024-06-01', '2025-06-01', 800.50, false, 'expired');
"""


@pytest.fixture(scope="session")
def postgres_container() -> AsyncIterator[PostgresContainer]:
    with PostgresContainer("pgvector/pgvector:pg16", driver="asyncpg") as container:
        yield container


@pytest.fixture(autouse=True)
def _test_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chave Fernet de teste — evita depender de ENCRYPTION_SECRET_KEY do ambiente."""
    from app.core import encryption

    monkeypatch.setattr(encryption.settings, "encryption_secret_key", Fernet.generate_key().decode())
    encryption.get_encryptor.cache_clear()
    yield
    encryption.get_encryptor.cache_clear()


@pytest_asyncio.fixture
async def app_client(metadata_session: AsyncSession):
    """httpx.AsyncClient contra o app FastAPI, com o banco de metadados dos testes.

    Sobrescreve get_db_session (Depends) e o get_metadata_session usado fora de Depends
    (background tasks, run_introspection) para apontar todos ao `metadata_session`.
    """
    import contextlib

    import httpx
    from httpx import ASGITransport

    from app.api import connections as connections_module
    from app.api.dependencies import get_db_session
    from app.main import app

    async def _override_session() -> AsyncIterator[AsyncSession]:
        yield metadata_session

    @contextlib.asynccontextmanager
    async def _fake_metadata_session() -> AsyncIterator[AsyncSession]:
        yield metadata_session

    original = connections_module.get_metadata_session
    connections_module.get_metadata_session = _fake_metadata_session
    app.dependency_overrides[get_db_session] = _override_session

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    connections_module.get_metadata_session = original


@pytest_asyncio.fixture
async def connection_row(metadata_session: AsyncSession) -> Connection:
    """Uma linha `connections` para escopar os metadados nos testes."""
    from app.core.encryption import get_encryptor

    connection = Connection(
        name="Test DB",
        db_type="postgresql",
        host="localhost",
        port=5432,
        database_name="testdb",
        username="tester",
        password_encrypted=get_encryptor().encrypt("secret"),
        schema_name="public",
    )
    metadata_session.add(connection)
    await metadata_session.commit()
    await metadata_session.refresh(connection)
    return connection


@pytest_asyncio.fixture
async def metadata_session(postgres_container: PostgresContainer) -> AsyncIterator[AsyncSession]:
    url = postgres_container.get_connection_url().replace("postgresql+psycopg2", "postgresql+asyncpg")
    engine = create_async_engine(url)

    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


PRODUCTION_TEST_SCHEMA = "introspector_test"


@pytest_asyncio.fixture
async def production_connection(postgres_container: PostgresContainer) -> AsyncIterator[asyncpg.Connection]:
    connection = await asyncpg.connect(
        host=postgres_container.get_container_host_ip(),
        port=int(postgres_container.get_exposed_port(5432)),
        user=postgres_container.username,
        password=postgres_container.password,
        database=postgres_container.dbname,
    )
    await connection.execute(f"CREATE SCHEMA IF NOT EXISTS {PRODUCTION_TEST_SCHEMA}")
    await connection.execute(f"SET search_path TO {PRODUCTION_TEST_SCHEMA}")
    await connection.execute(_PRODUCTION_SCHEMA_SQL)

    try:
        yield connection
    finally:
        await connection.execute(f"DROP SCHEMA {PRODUCTION_TEST_SCHEMA} CASCADE")
        await connection.close()
