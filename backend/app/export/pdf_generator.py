import asyncio
import io
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # backend sem GUI — obrigatório antes de importar pyplot
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from app.core.logging import get_logger
from app.export.chart_generator import ChartSpec
from app.export.formatting import ColumnFormat, build_column_format_map, format_cell
from app.export.storage import export_filename

logger = get_logger(__name__)

_MAX_TABLE_ROWS = 100
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_CHART_COLORS = ["#4F46E5", "#059669", "#D97706", "#DC2626", "#7C3AED", "#0891B2"]
_NUMERIC_FORMATS = {ColumnFormat.CURRENCY, ColumnFormat.DECIMAL_NUMBER, ColumnFormat.INTEGER}

_env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=select_autoescape(["html"]))


def _plot_bar(ax: Any, chart_spec: ChartSpec, horizontal: bool) -> None:
    n_series = max(len(chart_spec.series), 1)
    x_positions = list(range(len(chart_spec.x_data)))
    bar_width = 0.8 / n_series

    for index, series in enumerate(chart_spec.series):
        offset = (index - (n_series - 1) / 2) * bar_width
        positions = [p + offset for p in x_positions]
        color = _CHART_COLORS[index % len(_CHART_COLORS)]
        if horizontal:
            ax.barh(positions, series.values, height=bar_width, label=series.name, color=color)
        else:
            ax.bar(positions, series.values, width=bar_width, label=series.name, color=color)

    if horizontal:
        ax.set_yticks(x_positions)
        ax.set_yticklabels(chart_spec.x_data)
        ax.set_xlabel(chart_spec.y_label)
    else:
        ax.set_xticks(x_positions)
        ax.set_xticklabels(chart_spec.x_data, rotation=45, ha="right")
        ax.set_ylabel(chart_spec.y_label)

    if n_series > 1:
        ax.legend()


def chart_to_svg(chart_spec: ChartSpec) -> str:
    """Converte ChartSpec em string SVG usando matplotlib.

    Só usado para PDF: o frontend renderiza o mesmo ChartSpec com Recharts
    (interativo), mas o WeasyPrint não tem browser pra rodar JS — precisa de uma
    imagem/SVG estático gerado no backend.
    """
    fig, ax = plt.subplots(figsize=(8, 4))

    if chart_spec.chart_type == "pie" and chart_spec.series:
        series = chart_spec.series[0]
        ax.pie(series.values, labels=chart_spec.x_data, autopct="%1.1f%%", colors=_CHART_COLORS)
    elif chart_spec.chart_type == "line":
        for index, series in enumerate(chart_spec.series):
            ax.plot(
                chart_spec.x_data,
                series.values,
                marker="o",
                label=series.name,
                color=_CHART_COLORS[index % len(_CHART_COLORS)],
            )
        ax.set_xlabel(chart_spec.x_label)
        ax.set_ylabel(chart_spec.y_label)
        plt.xticks(rotation=45, ha="right")
        if len(chart_spec.series) > 1:
            ax.legend()
    else:
        _plot_bar(ax, chart_spec, horizontal=chart_spec.chart_type == "horizontal_bar")

    ax.set_title(chart_spec.title)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue().decode("utf-8")


def _prepare_columns(columns: list[str], column_formats: dict[str, ColumnFormat]) -> list[dict[str, Any]]:
    return [
        {"key": column, "name": column, "is_numeric": column_formats.get(column) in _NUMERIC_FORMATS}
        for column in columns
    ]


def _prepare_rows(
    columns: list[str], rows: list[dict], column_formats: dict[str, ColumnFormat]
) -> list[dict[str, str]]:
    return [
        {column: format_cell(row.get(column), column_formats.get(column, ColumnFormat.TEXT)) for column in columns}
        for row in rows[:_MAX_TABLE_ROWS]
    ]


def _generate_pdf_sync(
    question: str,
    response_text: str,
    sql: str,
    columns: list[str],
    rows: list[dict],
    metadata: dict[str, Any],
    column_formats: dict[str, ColumnFormat],
    chart_spec: ChartSpec | None,
) -> Path:
    chart_svg = chart_to_svg(chart_spec) if chart_spec else None

    template = _env.get_template("report.html")
    html_content = template.render(
        generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
        question=question,
        sql=sql,
        response_text=response_text,
        chart_svg=chart_svg,
        columns=_prepare_columns(columns, column_formats),
        rows=_prepare_rows(columns, rows, column_formats),
        row_count=len(rows),
        truncated=len(rows) > _MAX_TABLE_ROWS,
    )

    output_path = export_filename("pdf")
    HTML(string=html_content).write_pdf(output_path)
    return output_path


async def generate_pdf(
    question: str,
    response_text: str,
    sql: str,
    columns: list[str],
    rows: list[dict],
    metadata: dict[str, Any],
    column_formats: dict[str, ColumnFormat] | None = None,
    chart_spec: ChartSpec | None = None,
) -> Path:
    """Gera um relatório .pdf: renderiza o template Jinja2 (com o gráfico como SVG via
    matplotlib, se houver) e converte com WeasyPrint. Tudo síncrono — roda em thread
    separada."""
    resolved_formats = column_formats or build_column_format_map(columns, rows)
    return await asyncio.to_thread(
        _generate_pdf_sync,
        question,
        response_text,
        sql,
        columns,
        rows,
        metadata,
        resolved_formats,
        chart_spec,
    )
