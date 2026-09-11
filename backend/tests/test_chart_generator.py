from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.export.chart_generator import (
    MAX_CHART_CATEGORIES,
    ChartSpec,
    _cap_categories,
    _heuristic_chart_spec,
    generate_chart_spec,
)
from app.export.formatting import ColumnFormat, build_column_format_map


def test_heuristic_picks_bar_chart_for_categorical_and_numeric() -> None:
    columns = ["broker_name", "total_premium"]
    rows = [
        {"broker_name": "Ana", "total_premium": Decimal("1200.50")},
        {"broker_name": "Bruno", "total_premium": Decimal("800.00")},
    ]

    spec = _heuristic_chart_spec(columns, rows)

    assert spec.chart_type == "bar"
    assert spec.x_data == ["Ana", "Bruno"]
    assert spec.series[0].values == [1200.5, 800.0]
    assert spec.series[0].source_column == "total_premium"


def test_heuristic_picks_line_chart_for_temporal_data() -> None:
    columns = ["occurrence_date", "estimated_loss"]
    rows = [
        {"occurrence_date": date(2025, 1, 1), "estimated_loss": Decimal("100.0")},
        {"occurrence_date": date(2025, 2, 1), "estimated_loss": Decimal("200.0")},
    ]

    spec = _heuristic_chart_spec(columns, rows)

    assert spec.chart_type == "line"


def test_heuristic_picks_horizontal_bar_for_many_categories() -> None:
    columns = ["client_name", "policy_count"]
    rows = [{"client_name": f"Cliente {i}", "policy_count": i} for i in range(10)]

    spec = _heuristic_chart_spec(columns, rows)

    assert spec.chart_type == "horizontal_bar"


def test_chart_spec_serializes_to_camel_case() -> None:
    spec = _heuristic_chart_spec(
        ["broker_name", "total"], [{"broker_name": "Ana", "total": 100}]
    )

    payload = spec.model_dump(by_alias=True)

    assert "chartType" in payload
    assert "xLabel" in payload
    assert "xData" in payload
    assert payload["series"][0]["sourceColumn"] == "total"


def test_pie_chart_keeps_only_first_series() -> None:
    spec = ChartSpec.model_validate(
        {
            "chartType": "pie",
            "title": "t",
            "xLabel": "x",
            "yLabel": "y",
            "xData": ["A", "B"],
            "series": [
                {"name": "s1", "values": [1, 2]},
                {"name": "s2", "values": [3, 4]},
            ],
        }
    )

    assert len(spec.series) == 1
    assert spec.series[0].name == "s1"


def test_cap_categories_truncates_and_aggregates_others() -> None:
    columns = [f"cat{i}" for i in range(MAX_CHART_CATEGORIES + 5)]
    rows = [{col: 1.0 for col in columns}]
    spec = ChartSpec(
        chart_type="bar",
        title="t",
        x_label="x",
        y_label="y",
        x_data=columns,
        series=[{"name": "s", "values": [float(i) for i in range(len(columns))]}],
    )

    capped = _cap_categories(spec)

    assert len(capped.x_data) == MAX_CHART_CATEGORIES
    assert capped.x_data[-1] == "Outros"
    assert len(capped.series[0].values) == MAX_CHART_CATEGORIES


@pytest.mark.asyncio
async def test_generate_chart_spec_falls_back_to_heuristic_when_llm_fails() -> None:
    columns = ["broker_name", "total_premium"]
    rows = [{"broker_name": "Ana", "total_premium": Decimal("1200.50")}]
    column_formats = build_column_format_map(columns, rows)

    with patch(
        "app.export.chart_generator._generate_chart_spec_llm", new=AsyncMock(side_effect=RuntimeError("boom"))
    ):
        spec = await generate_chart_spec(
            question="Mostre um gráfico dos prêmios por corretor",
            columns=columns,
            rows=rows,
            response_text="...",
            column_formats=column_formats,
        )

    assert spec.chart_type == "bar"
    assert spec.series[0].value_format == "currency"


@pytest.mark.asyncio
async def test_generate_chart_spec_marks_rate_columns_as_plain_number() -> None:
    columns = ["broker_name", "commission_rate"]
    rows = [{"broker_name": "Ana", "commission_rate": Decimal("12.50")}]
    column_formats = build_column_format_map(columns, rows)
    assert column_formats["commission_rate"] == ColumnFormat.DECIMAL_NUMBER

    with patch(
        "app.export.chart_generator._generate_chart_spec_llm", new=AsyncMock(side_effect=RuntimeError("boom"))
    ):
        spec = await generate_chart_spec(
            question="gráfico de taxa de comissão por corretor",
            columns=columns,
            rows=rows,
            response_text="...",
            column_formats=column_formats,
        )

    assert spec.series[0].value_format is None
