from app.agents.config import AGENT_LLM_CONFIG
from app.agents.llm_utils import extract_text_content
from app.agents.sql_generator import dialect_label, dialect_notes
from app.agents.sql_utils import clean_generated_sql
from app.agents.state import AgentState
from app.core.llm_provider import get_llm
from app.core.logging import get_logger

logger = get_logger(__name__)

_CORRECTION_SQL_PROMPT = """Você é um gerador de SQL {dialect}. A query anterior falhou. Use o plano de \
correção abaixo para gerar uma query corrigida.

Query anterior (COM ERRO — não repita o mesmo erro):
{generated_sql}

Erro: {execution_error}
Categoria: {error_category}
Plano de correção: {correction_plan}

Particularidades do dialeto {dialect}:
{dialect_notes}

Schema:
{schema_context}

Pergunta original: {question}

Retorne APENAS o SQL corrigido, sem explicações."""


async def correction_sql_node(state: AgentState) -> dict:
    """Nó 8: regenera o SQL baseado no plano de correção, evitando o erro anterior."""
    llm = get_llm(**AGENT_LLM_CONFIG["correction_sql"])
    dialect = state.get("dialect") or "postgresql"
    prompt = _CORRECTION_SQL_PROMPT.format(
        dialect=dialect_label(dialect),
        dialect_notes=dialect_notes(dialect),
        generated_sql=state["generated_sql"],
        execution_error=state["execution_error"],
        error_category=state["error_category"],
        correction_plan=state["correction_plan"],
        schema_context=state["schema_context"],
        question=state["question"],
    )
    response = await llm.ainvoke(prompt)
    raw_sql = extract_text_content(response.content)
    generated_sql = clean_generated_sql(raw_sql)

    logger.info("correction_sql_done", generated_sql=generated_sql)
    return {"generated_sql": generated_sql}
