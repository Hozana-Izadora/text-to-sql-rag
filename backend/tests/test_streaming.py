import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.agents.state import create_initial_state
from app.api.streaming import _status_message_for_update, stream_pipeline


class _FakeGraph:
    def __init__(self, events: list[tuple[str, Any]]) -> None:
        self._events = events

    async def astream(self, state: dict, *, stream_mode: list[str]):
        for event in self._events:
            yield event


class _FailingGraph:
    async def astream(self, state: dict, *, stream_mode: list[str]):
        raise RuntimeError("boom")
        yield  # pragma: no cover — inalcançável, só faz esta função ser um async generator


def _chunk(text: str, node: str) -> tuple[Any, dict]:
    return SimpleNamespace(content=[{"type": "text", "text": text}]), {"langgraph_node": node}


@pytest.mark.asyncio
async def test_stream_pipeline_emits_events_in_order() -> None:
    events = [
        ("updates", {"schema_linker": {"relevant_tables": ["clients"]}}),
        ("updates", {"sql_generator": {"generated_sql": "SELECT 1"}}),
        (
            "updates",
            {
                "sql_executor": {
                    "execution_result": [{"total": 20}],
                    "execution_error": None,
                    "row_count": 1,
                    "was_truncated": False,
                }
            },
        ),
        ("messages", _chunk("Olá", "response_synthesizer")),
        ("messages", _chunk("!", "response_synthesizer")),
    ]

    chunks = [line async for line in stream_pipeline("pergunta válida", _FakeGraph(events))]
    joined = "".join(chunks)

    assert all(line.endswith("\n\n") for line in chunks)
    sql_index = joined.index('"event": "sql"')
    columns_index = joined.index('"event": "columns"')
    rows_index = joined.index('"event": "rows"')
    metadata_index = joined.index('"event": "metadata"')
    answer_index = joined.index('"event": "answer"')
    done_index = joined.index('"event": "done"')

    assert sql_index < columns_index < rows_index < metadata_index < answer_index < done_index


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "node_name",
    [
        "schema_linker",
        "subproblem_agent",
        "query_planner",
        "sql_generator",
        "sql_validator",
        "sql_executor",
        "correction_planner",
        "correction_sql",
    ],
)
async def test_stream_pipeline_never_leaks_messages_from_non_response_synthesizer_nodes(node_name: str) -> None:
    events = [("messages", _chunk("não deveria vazar pro usuário", node_name))]

    chunks = [line async for line in stream_pipeline("pergunta válida", _FakeGraph(events))]
    joined = "".join(chunks)

    assert "não deveria vazar pro usuário" not in joined


@pytest.mark.asyncio
async def test_stream_pipeline_serializes_decimal_and_date() -> None:
    events = [
        (
            "updates",
            {
                "sql_executor": {
                    "execution_result": [
                        {"premium_amount": Decimal("1234.56"), "start_date": datetime.date(2025, 1, 1)}
                    ],
                    "execution_error": None,
                    "row_count": 1,
                    "was_truncated": False,
                }
            },
        ),
    ]

    chunks = [line async for line in stream_pipeline("pergunta válida", _FakeGraph(events))]
    rows_line = next(line for line in chunks if '"event": "rows"' in line)

    assert "1234.56" in rows_line
    assert "2025-01-01" in rows_line


@pytest.mark.asyncio
async def test_stream_pipeline_emits_error_event_on_exception() -> None:
    chunks = [line async for line in stream_pipeline("pergunta válida", _FailingGraph())]
    joined = "".join(chunks)

    assert '"event": "error"' in joined
    assert '"event": "done"' not in joined


def test_status_message_schema_linker_lists_tables() -> None:
    state = create_initial_state("pergunta")
    message = _status_message_for_update("schema_linker", {"relevant_tables": ["clients", "policies"]}, state)
    assert message == "Tabelas identificadas: clients, policies"


def test_status_message_sql_validator_invalid_includes_reason() -> None:
    state = create_initial_state("pergunta")
    message = _status_message_for_update(
        "sql_validator", {"sql_is_valid": False, "execution_error": "[validation] tabela x não existe"}, state
    )
    assert message == "SQL inválido: tabela x não existe"


def test_status_message_sql_validator_valid_announces_execution() -> None:
    state = create_initial_state("pergunta")
    assert _status_message_for_update("sql_validator", {"sql_is_valid": True}, state) == "Executando SQL..."


def test_status_message_correction_planner_shows_attempt_count() -> None:
    state = create_initial_state("pergunta")
    message = _status_message_for_update("correction_planner", {"correction_count": 1}, state)
    assert message == "Corrigindo query (tentativa 1/3)..."


def test_status_message_nodes_without_visible_status_return_none() -> None:
    state = create_initial_state("pergunta")
    assert _status_message_for_update("sql_generator", {}, state) is None
    assert _status_message_for_update("sql_executor", {}, state) is None
    assert _status_message_for_update("correction_sql", {}, state) is None
    assert _status_message_for_update("response_synthesizer", {}, state) is None
