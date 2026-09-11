import uuid

from app.agents.state import AgentState
from app.core.config import settings
from app.core.logging import get_logger
from app.database.connection import get_metadata_session
from app.database.executor import execute_readonly_sql
from app.metadata.connections import ConnectionNotFoundError, config_from_row, get_connection

logger = get_logger(__name__)


async def sql_executor_node(state: AgentState) -> dict:
    connection_id = state.get("connection_id")
    if not connection_id:
        return {
            "execution_result": None,
            "execution_error": "Nenhuma conexão selecionada para executar a consulta.",
            "row_count": 0,
            "was_truncated": False,
        }

    try:
        async with get_metadata_session() as session:
            connection = await get_connection(session, uuid.UUID(connection_id))
            config = config_from_row(connection)
    except ConnectionNotFoundError as exc:
        return {
            "execution_result": None,
            "execution_error": str(exc),
            "row_count": 0,
            "was_truncated": False,
        }

    rows, was_truncated, error = await execute_readonly_sql(
        config, state["generated_sql"], settings.sql_timeout_seconds, settings.sql_max_rows
    )

    if error is not None:
        return {
            "execution_result": None,
            "execution_error": error,
            "row_count": 0,
            "was_truncated": False,
        }

    return {
        "execution_result": rows,
        "execution_error": None,
        "row_count": len(rows),
        "was_truncated": was_truncated,
    }
