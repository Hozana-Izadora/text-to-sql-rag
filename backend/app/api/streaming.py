import datetime
import json
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any

from app.agents.llm_utils import extract_text_content
from app.agents.state import AgentState, create_initial_state
from app.core.config import settings
from app.core.logging import get_logger
from app.export.chart_generator import generate_chart_spec
from app.export.classifier import OutputType, classify_output
from app.export.formatting import ColumnFormat, build_column_format_map

logger = get_logger(__name__)

_RESPONSE_SYNTHESIZER_NODE = "response_synthesizer"
_SQL_PRODUCING_NODES = ("sql_generator", "correction_sql")


def _json_default(value: Any) -> Any:
    """default= para json.dumps: cobre Decimal/date/datetime vindos do asyncpg
    (ex.: policies.premium_amount é DECIMAL, policies.start_date é DATE) — json.dumps
    padrão não sabe serializar nenhum dos dois."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return str(value)


def _format_sse(event: str, data: Any) -> str:
    """Cada evento SSE precisa ser uma única linha após 'data: ' — sem indent=,
    e ensure_ascii=False para não transformar acentos em \\uXXXX à toa."""
    payload = json.dumps({"event": event, "data": data}, default=_json_default, ensure_ascii=False)
    return f"data: {payload}\n\n"


def _status_message_for_update(node_name: str, node_output: dict, accumulated_state: AgentState) -> str | None:
    """Função pura: decide o texto do evento 'status' para um nó que acabou de
    completar, ou None se aquele nó não deve gerar status visível (ex.: sql_generator
    tem seu próprio evento 'sql' dedicado; sql_executor tem columns/rows/metadata)."""
    if node_name == "schema_linker":
        tables = node_output.get("relevant_tables") or []
        if tables:
            return f"Tabelas identificadas: {', '.join(tables)}"
        return "Identificando tabelas relevantes..."

    if node_name == "subproblem_agent":
        return "Decompondo a consulta..."

    if node_name == "query_planner":
        return "Gerando plano de consulta..."

    if node_name == "sql_validator":
        if node_output.get("sql_is_valid") is False:
            reason = (node_output.get("execution_error") or "").removeprefix("[validation] ")
            return f"SQL inválido: {reason}" if reason else "SQL inválido, revisando..."
        return "Executando SQL..."

    if node_name == "correction_planner":
        attempt = node_output.get("correction_count", accumulated_state["correction_count"])
        return f"Corrigindo query (tentativa {attempt}/{settings.correction_max_retries})..."

    return None


async def stream_pipeline(
    question: str,
    graph: Any,
    *,
    connection_id: str = "",
    dialect: str = "postgresql",
) -> AsyncGenerator[str, None]:
    """Roda o grafo LangGraph e yield eventos SSE formatados conforme cada nó progride.

    Usa stream_mode=["updates", "messages"] num único iterador: "updates" dá o delta de
    cada nó completado (para status/sql/columns/rows/metadata), "messages" dá os chunks
    de streaming de qualquer chamada LLM dentro do grafo — filtrado para só repassar
    chunks do nó response_synthesizer (os demais nós usam ainvoke() puro e também
    emitem chunks reais em "messages"; sem esse filtro, SQL/plano bruto vazariam no
    evento "answer").

    Espelha o try/except amplo do Pipeline.run() da Fase 2: uma exceção não tratada
    depois que o StreamingResponse já mandou 200 pro navegador não pode virar um crash
    silencioso do generator — precisa virar um evento "error" visível.
    """
    accumulated_state: AgentState = create_initial_state(question, connection_id, dialect)
    columns: list[str] = []
    column_formats: dict[str, ColumnFormat] = {}

    try:
        async for stream_mode, payload in graph.astream(accumulated_state, stream_mode=["updates", "messages"]):
            if stream_mode == "updates":
                for node_name, node_output in payload.items():
                    accumulated_state.update(node_output)  # type: ignore[typeddict-item]

                    if node_name in _SQL_PRODUCING_NODES:
                        yield _format_sse("sql", accumulated_state.get("generated_sql", ""))

                    if node_name == "sql_executor" and accumulated_state.get("execution_error") is None:
                        rows = accumulated_state.get("execution_result") or []
                        columns = list(rows[0].keys()) if rows else []
                        # Computado uma única vez aqui, enquanto `rows` ainda tem os
                        # tipos Python originais do asyncpg (Decimal/date) — depois do
                        # round-trip JSON do SSE essa distinção se perde.
                        column_formats = build_column_format_map(columns, rows)
                        yield _format_sse("columns", columns)
                        yield _format_sse("rows", rows)
                        yield _format_sse(
                            "metadata",
                            {
                                "row_count": accumulated_state.get("row_count", 0),
                                "truncated": accumulated_state.get("was_truncated", False),
                                "tables_used": accumulated_state.get("relevant_tables", []),
                                "column_formats": column_formats,
                            },
                        )

                    status = _status_message_for_update(node_name, node_output, accumulated_state)
                    if status is not None:
                        yield _format_sse("status", status)

            elif stream_mode == "messages":
                message_chunk, chunk_metadata = payload
                if chunk_metadata.get("langgraph_node") != _RESPONSE_SYNTHESIZER_NODE:
                    continue
                # extract_text_content: alguns modelos (Gemini com extended thinking)
                # emitem chunks com content=[{"type": "thinking"/"text", ...}] em vez de
                # string simples — nunca trocar por str(chunk.content) "pra debugar
                # rápido", isso vazaria blobs de milhares de caracteres (thought
                # signatures) no evento SSE.
                text_piece = extract_text_content(message_chunk.content)
                if text_piece:
                    yield _format_sse("answer", text_piece)

        # Classificação de output roda depois do grafo terminar (não é um nó do
        # LangGraph). Guard explícito: só gera gráfico/oferece export automático
        # quando a execução teve dados de verdade — senão dispara pra uma pergunta
        # que falhou ou não retornou nada.
        has_data = bool(accumulated_state.get("execution_result")) and accumulated_state.get(
            "execution_error"
        ) is None
        if has_data:
            output_type = classify_output(question)

            if output_type == OutputType.CHART:
                chart_spec = await generate_chart_spec(
                    question=question,
                    columns=columns,
                    rows=accumulated_state["execution_result"],
                    response_text=accumulated_state.get("response_text", ""),
                    column_formats=column_formats,
                )
                yield _format_sse("chart", chart_spec.model_dump(by_alias=True))

            elif output_type in (OutputType.DOCX, OutputType.PDF):
                yield _format_sse("export_ready", {"format": output_type.value, "auto": True})

        yield _format_sse("done", None)

    except Exception as exc:
        logger.error("stream_pipeline_failed", question=question, error=str(exc))
        yield _format_sse("error", "Não foi possível processar essa pergunta agora. Tente novamente.")
