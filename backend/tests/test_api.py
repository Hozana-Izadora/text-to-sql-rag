import uuid
from typing import Any

import httpx
import pytest
from httpx import ASGITransport

from app.api import routes
from app.api.dependencies import check_metadata_db, get_pipeline_graph
from app.main import app

_CONNECTION_ID = str(uuid.uuid4())


class _FakeGraph:
    def __init__(self, events: list[tuple[str, Any]]) -> None:
        self._events = events

    async def astream(self, state: dict, *, stream_mode: list[str]):
        for event in self._events:
            yield event


_FAKE_EVENTS: list[tuple[str, Any]] = [
    ("updates", {"schema_linker": {"relevant_tables": ["clients"]}}),
    ("updates", {"sql_generator": {"generated_sql": "SELECT COUNT(*) FROM clients"}}),
    (
        "updates",
        {
            "sql_executor": {
                "execution_result": [{"count": 20}],
                "execution_error": None,
                "row_count": 1,
                "was_truncated": False,
            }
        },
    ),
    ("updates", {"response_synthesizer": {"response_text": "Temos 20 clientes.", "response_data": [{"count": 20}]}}),
]


@pytest.fixture(autouse=True)
def _override_dependencies(monkeypatch):
    app.dependency_overrides[get_pipeline_graph] = lambda: _FakeGraph(_FAKE_EVENTS)
    app.dependency_overrides[check_metadata_db] = lambda: True

    async def _fake_dialect(_connection_id):
        return "postgresql"

    monkeypatch.setattr(routes, "resolve_connection_dialect", _fake_dialect)
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_with_valid_question_returns_sse_stream() -> None:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream(
            "POST",
            "/api/chat",
            json={"question": "Quantos clientes ativos temos?", "connection_id": _CONNECTION_ID},
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            body = "".join([chunk async for chunk in response.aiter_text()])

    assert '"event": "sql"' in body
    assert '"event": "done"' in body


@pytest.mark.asyncio
async def test_chat_with_short_question_returns_422() -> None:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat", json={"question": "oi", "connection_id": _CONNECTION_ID}
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_with_empty_question_returns_422() -> None:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat", json={"question": "", "connection_id": _CONNECTION_ID}
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_health_returns_200_with_service_statuses() -> None:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"backend": True, "metadata_db": True}
