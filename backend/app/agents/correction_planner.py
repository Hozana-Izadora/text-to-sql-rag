from pydantic import BaseModel

from app.agents.config import AGENT_LLM_CONFIG
from app.agents.llm_utils import invoke_structured
from app.agents.state import AgentState
from app.core.llm_provider import get_llm
from app.core.logging import get_logger

logger = get_logger(__name__)

ERROR_TAXONOMY = """Syntax: sql_syntax_error, invalid_alias
Schema Link: table_missing, col_missing, ambiguous_col, incorrect_foreign_key
Join: join_missing, join_wrong_type, extra_table, incorrect_col
Filter: where_missing, condition_wrong_col, condition_type_mismatch
Aggregation: agg_no_groupby, groupby_missing_col, having_without_groupby, having_incorrect, having_vs_where
Value: hardcoded_value, value_format_wrong
Subquery: unused_subquery, subquery_missing, subquery_correlation_error
Set Operations: union_missing, intersect_missing, except_missing
Other: order_by_missing, limit_missing, duplicate_select, unsupported_function, extra_values_selected"""


class ErrorDiagnosis(BaseModel):
    error_category: str
    diagnosis: str
    correction_plan: str


_CORRECTION_PLAN_PROMPT = """Você é um especialista em correção de SQL PostgreSQL.

A query abaixo falhou ao executar. Analise o erro, classifique-o usando a taxonomia fornecida, e produza um \
plano de correção.

Query com erro:
{generated_sql}

Erro de execução:
{execution_error}

Schema disponível:
{schema_context}

Pergunta original:
{question}

Taxonomia de erros SQL:
{error_taxonomy}

Classifique o erro em uma das categorias da taxonomia, diagnostique a causa, e produza um plano de correção \
passo-a-passo (sem gerar SQL)."""


async def correction_planner_node(state: AgentState) -> dict:
    """Nó 7: analisa o erro, classifica pela taxonomia de 31 tipos do SQL-of-Thought
    e produz um plano de correção (sem gerar SQL)."""
    llm = get_llm(**AGENT_LLM_CONFIG["correction_planner"])
    prompt = _CORRECTION_PLAN_PROMPT.format(
        generated_sql=state["generated_sql"],
        execution_error=state["execution_error"],
        schema_context=state["schema_context"],
        question=state["question"],
        error_taxonomy=ERROR_TAXONOMY,
    )
    diagnosis = await invoke_structured(llm, ErrorDiagnosis, prompt)

    next_count = state["correction_count"] + 1
    logger.info("correction_planner_done", error_category=diagnosis.error_category, correction_count=next_count)

    return {
        "correction_plan": diagnosis.correction_plan,
        "error_category": diagnosis.error_category,
        "correction_count": next_count,
    }
