from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.alias_generators import to_camel

from app.agents.llm_utils import invoke_structured
from app.core.llm_provider import get_llm
from app.core.logging import get_logger
from app.export.formatting import ColumnFormat

logger = get_logger(__name__)

MAX_CHART_CATEGORIES = 20
_OTHERS_LABEL = "Outros"


class ChartSeries(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str
    values: list[float]
    color: str | None = None
    value_format: Literal["currency", "number"] | None = None
    # Rastreia qual coluna original virou esta série, pra aplicar value_format de forma
    # determinística depois (não depender do LLM "lembrar" de preencher isso certo).
    source_column: str | None = None


class ChartSpec(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    chart_type: Literal["bar", "line", "pie", "horizontal_bar"]
    title: str
    x_label: str
    y_label: str
    x_data: list[str]
    series: list[ChartSeries]

    @model_validator(mode="after")
    def _pie_single_series(self) -> "ChartSpec":
        if self.chart_type == "pie" and len(self.series) > 1:
            self.series = self.series[:1]
        return self


_CHART_SPEC_PROMPT = """Você é um especialista em visualização de dados. Dados os dados abaixo e a \
pergunta do usuário, defina a melhor visualização.

Pergunta: {question}

Resposta gerada: {response_text}

Colunas disponíveis: {columns}

Amostra dos dados (até 20 linhas):
{sample_rows}

Escolha:
1. O tipo de gráfico mais adequado: "bar", "horizontal_bar", "line" ou "pie"
2. Qual coluna é o eixo X (categórica ou temporal) e qual é o eixo Y (numérica)
3. Um título curto e labels para os eixos

Se os dados tiverem mais de {max_categories} categorias, selecione/agrupe as mais relevantes."""


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _pick_x_column(columns: list[str], first_row: dict) -> tuple[str, bool]:
    """Retorna (nome_da_coluna, is_temporal). Prioriza coluna de data (line chart),
    depois a primeira coluna string, senão a primeira coluna disponível."""
    for column in columns:
        if isinstance(first_row.get(column), (date, datetime)):
            return column, True
    for column in columns:
        if isinstance(first_row.get(column), str):
            return column, False
    return columns[0], False


def _pick_y_column(columns: list[str], first_row: dict, exclude: str) -> str:
    for column in columns:
        if column == exclude:
            continue
        value = first_row.get(column)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float, Decimal)):
            return column
    return next((c for c in columns if c != exclude), columns[0])


def _heuristic_chart_spec(columns: list[str], rows: list[dict]) -> ChartSpec:
    """Fallback puro, sem I/O — usado quando a LLM falha, e testável direto."""
    if not rows or not columns:
        return ChartSpec(chart_type="bar", title="Dados", x_label="", y_label="", x_data=[], series=[])

    first_row = rows[0]
    x_column, is_temporal = _pick_x_column(columns, first_row)
    y_column = _pick_y_column(columns, first_row, exclude=x_column)

    x_data = [str(row.get(x_column, "")) for row in rows]
    values = [_to_float(row.get(y_column)) for row in rows]

    if is_temporal:
        chart_type: Literal["bar", "line", "pie", "horizontal_bar"] = "line"
    elif len(x_data) > 8:
        chart_type = "horizontal_bar"
    else:
        chart_type = "bar"

    return ChartSpec(
        chart_type=chart_type,
        title=f"{y_column} por {x_column}",
        x_label=x_column,
        y_label=y_column,
        x_data=x_data,
        series=[ChartSeries(name=y_column, values=values, source_column=y_column)],
    )


async def _generate_chart_spec_llm(
    question: str, columns: list[str], rows: list[dict], response_text: str
) -> ChartSpec:
    # generate_chart_spec não é um nó do grafo LangGraph (é chamado direto de
    # app/api/streaming.py, depois do pipeline terminar) — por isso não entra em
    # AGENT_LLM_CONFIG, que é escopado aos 9 nós do grafo.
    llm = get_llm(provider="gemini")
    sample_rows = "\n".join(str({key: row.get(key) for key in columns}) for row in rows[:20])
    prompt = _CHART_SPEC_PROMPT.format(
        question=question,
        response_text=response_text,
        columns=", ".join(columns),
        sample_rows=sample_rows,
        max_categories=MAX_CHART_CATEGORIES,
    )
    return await invoke_structured(llm, ChartSpec, prompt)


def _match_series_to_column(series_name: str, columns: list[str]) -> str | None:
    normalized = series_name.strip().lower()
    for column in columns:
        if column.lower() == normalized or column.lower().replace("_", " ") == normalized:
            return column
    return None


def _apply_value_formats(
    spec: ChartSpec, column_formats: dict[str, ColumnFormat], columns: list[str]
) -> ChartSpec:
    """Determinístico: sempre roda por cima do resultado da LLM ou da heurística."""
    numeric_formats = (ColumnFormat.CURRENCY, ColumnFormat.DECIMAL_NUMBER, ColumnFormat.INTEGER)
    numeric_columns = [col for col, fmt in column_formats.items() if fmt in numeric_formats]

    for series in spec.series:
        source_column = series.source_column or _match_series_to_column(series.name, columns)
        if source_column is None and len(spec.series) == 1 and len(numeric_columns) == 1:
            source_column = numeric_columns[0]

        series.source_column = source_column
        column_format = column_formats.get(source_column) if source_column else None
        series.value_format = "currency" if column_format == ColumnFormat.CURRENCY else None

    return spec


def _cap_categories(spec: ChartSpec) -> ChartSpec:
    """Trunca com agregação 'Outros' se exceder MAX_CHART_CATEGORIES — evita gráfico
    ilegível/payload gigante, independente do LLM/heurística terem respeitado o pedido."""
    if len(spec.x_data) <= MAX_CHART_CATEGORIES:
        return spec

    kept = MAX_CHART_CATEGORIES - 1
    new_x_data = [*spec.x_data[:kept], _OTHERS_LABEL]
    new_series = []
    for series in spec.series:
        kept_values = series.values[:kept]
        remainder = sum(series.values[kept:])
        new_series.append(series.model_copy(update={"values": [*kept_values, remainder]}))

    return spec.model_copy(update={"x_data": new_x_data, "series": new_series})


async def generate_chart_spec(
    question: str,
    columns: list[str],
    rows: list[dict],
    response_text: str,
    column_formats: dict[str, ColumnFormat] | None = None,
) -> ChartSpec:
    """Usa LLM pra decidir a melhor visualização, com fallback heurístico se a LLM falhar."""
    try:
        spec = await _generate_chart_spec_llm(question, columns, rows, response_text)
    except Exception as exc:
        logger.warning("chart_spec_llm_failed", error=str(exc))
        spec = _heuristic_chart_spec(columns, rows)

    spec = _cap_categories(spec)
    spec = _apply_value_formats(spec, column_formats or {}, columns)
    return spec
