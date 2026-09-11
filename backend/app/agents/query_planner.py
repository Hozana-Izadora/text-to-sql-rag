from app.agents.config import AGENT_LLM_CONFIG
from app.agents.llm_utils import extract_text_content
from app.agents.state import AgentState
from app.core.llm_provider import get_llm
from app.core.logging import get_logger

logger = get_logger(__name__)

_QUERY_PLAN_PROMPT = """Você é um planejador de consultas SQL. Dado o schema, os subproblemas identificados e a \
pergunta original, gere um plano passo-a-passo para construir a query.

NÃO gere SQL. Descreva cada passo em linguagem natural.

Schema:
{schema_context}

Pergunta: {question}

Subproblemas identificados:
{subproblems}

Exemplos similares (referência):
{few_shot_examples}

Gere o plano como uma lista numerada."""


def _format_subproblems(subproblems: dict[str, str]) -> str:
    if not subproblems:
        return "Nenhum."
    return "\n".join(f"- {clause}: {description}" for clause, description in subproblems.items())


def _format_few_shot_examples(examples: list[dict]) -> str:
    if not examples:
        return "Nenhum exemplo disponível."
    return "\n\n".join(f"Pergunta: {e['question_nl']}\nSQL: {e['query_sql']}" for e in examples)


async def query_planner_node(state: AgentState) -> dict:
    """Nó 3 (Chain-of-Thought): gera um plano procedural passo-a-passo, sem SQL."""
    llm = get_llm(**AGENT_LLM_CONFIG["query_planner"])
    prompt = _QUERY_PLAN_PROMPT.format(
        schema_context=state["schema_context"],
        question=state["question"],
        subproblems=_format_subproblems(state["subproblems"]),
        few_shot_examples=_format_few_shot_examples(state["few_shot_examples"]),
    )
    response = await llm.ainvoke(prompt)
    query_plan = extract_text_content(response.content)

    logger.info("query_planner_done", query_plan=query_plan)
    return {"query_plan": query_plan}
