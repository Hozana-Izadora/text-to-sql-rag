from app.agents.config import AGENT_LLM_CONFIG
from app.agents.llm_utils import extract_text_content
from app.agents.state import AgentState
from app.core.llm_provider import get_llm
from app.core.logging import get_logger

logger = get_logger(__name__)

_RESPONSE_PROMPT = """Você é um assistente de uma corretora de seguros. O usuário fez a pergunta abaixo{outcome}.

Pergunta: {question}
{details}

Gere uma resposta em linguagem natural que:
1. Responda diretamente à pergunta
2. Destaque os números mais relevantes
3. Use formatação brasileira (R$ para valores, dd/mm/aaaa para datas)
4. Seja conciso e executivo (máximo 3 parágrafos)
5. Se os dados estiverem vazios, informe que não há resultados

Se a consulta falhou após todas as tentativas, explique que não foi possível processar a pergunta e sugira \
reformulação."""

_MAX_PREVIEW_ROWS = 50


def _format_result_table(rows: list[dict]) -> str:
    if not rows:
        return "(nenhuma linha retornada)"

    columns = list(rows[0].keys())
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body_rows = [
        "| " + " | ".join(str(row.get(col, "")) for col in columns) + " |" for row in rows[:_MAX_PREVIEW_ROWS]
    ]
    table = "\n".join([header, separator, *body_rows])
    if len(rows) > _MAX_PREVIEW_ROWS:
        table += f"\n... ({len(rows) - _MAX_PREVIEW_ROWS} linhas adicionais não exibidas)"
    return table


async def response_synthesizer_node(state: AgentState) -> dict:
    """Nó 9: transforma os dados retornados (ou o erro final) em resposta executiva em PT-BR."""
    llm = get_llm(**AGENT_LLM_CONFIG["response_synthesizer"])
    question = state["question"]

    if state["execution_error"] is not None:
        outcome = " mas o sistema não conseguiu executar uma consulta SQL válida"
        details = (
            f"SQL tentado: {state['generated_sql']}\n"
            f"Erro final após {state['correction_count']} tentativa(s) de correção: {state['execution_error']}"
        )
    else:
        rows = state["execution_result"] or []
        truncated_note = " (truncado)" if state["was_truncated"] else ""
        outcome = " e o sistema executou uma consulta SQL que retornou dados"
        details = (
            f"SQL executado: {state['generated_sql']}\n"
            f"Dados retornados ({state['row_count']} linhas{truncated_note}):\n"
            f"{_format_result_table(rows)}"
        )

    prompt = _RESPONSE_PROMPT.format(question=question, outcome=outcome, details=details)
    response = await llm.ainvoke(prompt)
    response_text = extract_text_content(response.content)

    logger.info("response_synthesizer_done", question=question)

    return {
        "response_text": response_text,
        "response_data": state["execution_result"],
    }
