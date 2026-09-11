from app.agents.config import AGENT_LLM_CONFIG
from app.agents.llm_utils import extract_text_content
from app.agents.sql_utils import clean_generated_sql
from app.agents.state import AgentState
from app.core.config import settings
from app.core.llm_provider import get_llm
from app.core.logging import get_logger

logger = get_logger(__name__)

_DIALECT_LABELS = {
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "sqlserver": "SQL Server",
}

# Particularidades por dialeto que o gerador precisa respeitar.
_DIALECT_NOTES = {
    "postgresql": (
        "- Limite de linhas: LIMIT N\n"
        "- Concatenação de strings: operador ||\n"
        "- Data de hoje: CURRENT_DATE\n"
        "- Booleanos: true / false\n"
        "- Identificadores com aspas duplas quando necessário: \"nome\"\n"
        "- Arredondar valores monetários: ROUND(valor, 2)"
    ),
    "mysql": (
        "- Limite de linhas: LIMIT N\n"
        "- Concatenação de strings: CONCAT(a, b) — o operador || não concatena\n"
        "- Data de hoje: CURDATE()\n"
        "- Booleanos: 1 / 0\n"
        "- Identificadores com crase quando necessário: `nome`\n"
        "- Arredondar valores monetários: ROUND(valor, 2)"
    ),
    "sqlserver": (
        "- Limite de linhas: SELECT TOP N ... (NÃO use LIMIT)\n"
        "- Concatenação de strings: operador + ou CONCAT(a, b)\n"
        "- Data de hoje: CAST(GETDATE() AS DATE)\n"
        "- Booleanos: 1 / 0\n"
        "- Identificadores entre colchetes quando necessário: [nome]\n"
        "- Arredondar valores monetários: ROUND(valor, 2)"
    ),
}


def dialect_label(dialect: str) -> str:
    return _DIALECT_LABELS.get(dialect, "PostgreSQL")


def dialect_notes(dialect: str) -> str:
    return _DIALECT_NOTES.get(dialect, _DIALECT_NOTES["postgresql"])


_SQL_GENERATION_PROMPT = """Você é um gerador de SQL {dialect}. Converta o plano abaixo em uma query SQL válida.

Regras obrigatórias:
- Apenas SELECT (nunca INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE)
- Use APENAS as tabelas e colunas listadas no schema
- Use aliases claros para tabelas (ex: p para policies, b para brokers)
- Não use SELECT * — liste as colunas necessárias
- Limite de {max_rows} linhas se não houver limite explícito no plano

Particularidades do dialeto {dialect}:
{dialect_notes}

Schema:
{schema_context}

Plano de execução:
{query_plan}

Keywords matchadas (valores no banco):
{matched_keywords}

Exemplos similares:
{few_shot_examples}

Retorne APENAS o SQL, sem explicações."""


def _format_matched_keywords(matched_keywords: list[dict]) -> str:
    if not matched_keywords:
        return "Nenhuma."
    lines = []
    for match in matched_keywords:
        target = (
            f"{match['table_name']}.{match['column_name']}"
            if match.get("column_name")
            else match["table_name"]
        )
        lines.append(f"- '{match['keyword']}' -> {target} = '{match['matched_value']}'")
    return "\n".join(lines)


def _format_few_shot_examples(examples: list[dict]) -> str:
    if not examples:
        return "Nenhum exemplo disponível."
    return "\n\n".join(f"Pergunta: {e['question_nl']}\nSQL: {e['query_sql']}" for e in examples)


async def sql_generator_node(state: AgentState) -> dict:
    """Nó 4: gera o SQL executável a partir do plano (não da pergunta original diretamente)."""
    llm = get_llm(**AGENT_LLM_CONFIG["sql_generator"])
    dialect = state.get("dialect") or "postgresql"
    prompt = _SQL_GENERATION_PROMPT.format(
        dialect=dialect_label(dialect),
        dialect_notes=dialect_notes(dialect),
        max_rows=settings.sql_max_rows,
        schema_context=state["schema_context"],
        query_plan=state["query_plan"],
        matched_keywords=_format_matched_keywords(state["matched_keywords"]),
        few_shot_examples=_format_few_shot_examples(state["few_shot_examples"]),
    )
    response = await llm.ainvoke(prompt)
    raw_sql = extract_text_content(response.content)
    generated_sql = clean_generated_sql(raw_sql)

    logger.info("sql_generator_done", generated_sql=generated_sql)
    return {"generated_sql": generated_sql}
