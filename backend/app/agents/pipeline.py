from typing import cast

from app.agents.graph import build_graph
from app.agents.state import AgentState, create_initial_state
from app.core.logging import get_logger

logger = get_logger(__name__)


class Pipeline:
    """Wrapper fino sobre o grafo LangGraph compilado."""

    def __init__(self) -> None:
        self._graph = build_graph()

    async def run(
        self, question: str, connection_id: str = "", dialect: str = "postgresql"
    ) -> AgentState:
        """Roda o pipeline completo para uma pergunta numa conexão.

        Envolve graph.ainvoke() em try/except: uma falha em qualquer nó (chave de
        API ausente, rate limit, timeout, erro de parsing sem retry restante) não
        deve propagar e derrubar quem chamou (ex.: scripts/test_pipeline.py rodando
        várias perguntas em sequência) — degrada para uma resposta amigável.
        """
        initial_state = create_initial_state(question, connection_id, dialect)
        try:
            result = await self._graph.ainvoke(initial_state)
            return cast(AgentState, result)
        except Exception as exc:
            logger.error("pipeline_failed", question=question, error=str(exc))
            degraded_state = create_initial_state(question, connection_id, dialect)
            degraded_state["execution_error"] = str(exc)
            degraded_state["response_text"] = (
                "Não foi possível processar essa pergunta agora. "
                "Tente reformular ou tente novamente em instantes."
            )
            return degraded_state
