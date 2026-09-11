import pytest

from app.api import connections as connections_module
from app.database.introspection.types import (
    ColumnMetadata,
    ConnectionTestResult,
    TableMetadata,
)

pytestmark = pytest.mark.asyncio

_CREATE_PAYLOAD = {
    "name": "Analytics",
    "db_type": "postgresql",
    "host": "db.internal",
    "port": 5432,
    "database_name": "analytics",
    "username": "reader",
    "password": "top-secret",
    "schema_name": "public",
}


class _FakeIntrospector:
    def __init__(self, *, ok: bool = True) -> None:
        self._ok = ok

    async def test_connection(self) -> ConnectionTestResult:
        if self._ok:
            return ConnectionTestResult(success=True, message="Conexão OK", db_version="PostgreSQL 16")
        return ConnectionTestResult(success=False, message="connection refused")

    async def introspect(self) -> list[TableMetadata]:
        return [
            TableMetadata(
                table_name="events",
                schema_name="public",
                row_count=10,
                columns=[
                    ColumnMetadata(
                        column_name="id",
                        data_type="integer",
                        is_nullable=False,
                        is_primary_key=True,
                        is_foreign_key=False,
                    )
                ],
                relationships=[],
            )
        ]


@pytest.fixture
def fake_introspector(monkeypatch: pytest.MonkeyPatch):
    holder = {"ok": True}
    monkeypatch.setattr(
        connections_module, "get_introspector", lambda _config: _FakeIntrospector(ok=holder["ok"])
    )
    return holder


async def _create(app_client) -> str:
    response = await app_client.post("/api/connections/", json=_CREATE_PAYLOAD)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_create_connection_persists_and_hides_password(app_client, fake_introspector) -> None:
    response = await app_client.post("/api/connections/", json=_CREATE_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Analytics"
    assert "password" not in body
    assert "password_encrypted" not in body

    listed = await app_client.get("/api/connections/")
    assert [c["name"] for c in listed.json()] == ["Analytics"]


async def test_create_connection_rejects_unreachable_db(app_client, fake_introspector) -> None:
    fake_introspector["ok"] = False

    response = await app_client.post("/api/connections/", json=_CREATE_PAYLOAD)

    assert response.status_code == 400
    assert "connection refused" in response.json()["detail"]


async def test_test_endpoint_reports_result(app_client, fake_introspector) -> None:
    connection_id = await _create(app_client)

    result = await app_client.post(f"/api/connections/{connection_id}/test")

    assert result.status_code == 200
    assert result.json()["success"] is True


async def test_test_new_connection_does_not_persist(app_client, fake_introspector) -> None:
    payload = {k: v for k, v in _CREATE_PAYLOAD.items() if k != "name"}

    ok = await app_client.post("/api/connections/test", json=payload)
    assert ok.status_code == 200
    assert ok.json()["success"] is True

    fake_introspector["ok"] = False
    failed = await app_client.post("/api/connections/test", json=payload)
    assert failed.status_code == 200
    assert failed.json()["success"] is False

    listed = await app_client.get("/api/connections/")
    assert listed.json() == []


async def test_introspect_persists_schema(app_client, fake_introspector) -> None:
    connection_id = await _create(app_client)

    result = await app_client.post(f"/api/connections/{connection_id}/introspect")

    assert result.status_code == 200
    assert result.json()["tables"] == 1

    tables = await app_client.get(f"/api/connections/{connection_id}/metadata/tables")
    assert [t["table_name"] for t in tables.json()] == ["events"]


async def test_delete_connection_removes_metadata(app_client, fake_introspector) -> None:
    connection_id = await _create(app_client)
    await app_client.post(f"/api/connections/{connection_id}/introspect")

    deleted = await app_client.delete(f"/api/connections/{connection_id}")
    assert deleted.status_code == 204

    tables = await app_client.get(f"/api/connections/{connection_id}/metadata/tables")
    assert tables.status_code == 404
