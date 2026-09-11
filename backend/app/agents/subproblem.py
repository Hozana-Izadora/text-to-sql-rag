from pydantic import BaseModel

from app.agents.config import AGENT_LLM_CONFIG
from app.agents.llm_utils import invoke_structured
from app.agents.state import AgentState
from app.core.llm_provider import get_llm
from app.core.logging import get_logger

logger = get_logger(__name__)

_CLAUSES = [
    "SELECT",
    "FROM",
    "JOIN",
    "WHERE",
    "GROUP BY",
    "HAVING",
    "ORDER BY",
    "LIMIT",
    "DISTINCT",
    "UNION",
    "EXCEPT",
    "INTERSECT",
    "subquery",
]


class SubproblemDecomposition(BaseModel):
    subproblems: dict[str, str]


_SUBPROBLEM_PROMPT = """Dada a pergunta e o schema abaixo, decomponha a consulta em subproblemas por cláusula SQL.

Schema:
{schema_context}

Pergunta: {question}

Cláusulas possíveis: {clauses}

Retorne apenas as cláusulas realmente necessárias para responder a pergunta, cada uma com uma descrição curta \
do que ela precisa fazer."""


async def subproblem_node(state: AgentState) -> dict:
    """Nó 2: decompõe a pergunta em subproblemas por cláusula SQL, guiando o Query Plan Agent."""
    llm = get_llm(**AGENT_LLM_CONFIG["subproblem_agent"])
    prompt = _SUBPROBLEM_PROMPT.format(
        schema_context=state["schema_context"],
        question=state["question"],
        clauses=", ".join(_CLAUSES),
    )
    result = await invoke_structured(llm, SubproblemDecomposition, prompt)

    logger.info("subproblem_done", subproblems=result.subproblems)
    return {"subproblems": result.subproblems}
