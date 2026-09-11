from decimal import Decimal

import pytest
from pypdf import PdfReader

from app.export.chart_generator import _heuristic_chart_spec
from app.export.pdf_generator import generate_pdf


@pytest.mark.asyncio
async def test_generate_pdf_creates_valid_file_with_expected_content() -> None:
    columns = ["broker_name", "total_premium"]
    rows = [{"broker_name": "Ana", "total_premium": Decimal("1200.50")}]

    output_path = await generate_pdf(
        question="Qual o total de prêmios por corretor?",
        response_text="Ana teve o maior total de prêmios.",
        sql="SELECT broker_name, total_premium FROM x",
        columns=columns,
        rows=rows,
        metadata={"row_count": 1, "truncated": False},
    )

    try:
        assert output_path.exists()
        assert output_path.suffix == ".pdf"

        reader = PdfReader(str(output_path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

        assert "Ana teve o maior total de prêmios." in text
        assert "Qual o total de prêmios por corretor?" in text
    finally:
        output_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_generate_pdf_embeds_chart_svg_when_provided() -> None:
    columns = ["broker_name", "total_premium"]
    rows = [
        {"broker_name": "Ana", "total_premium": 1200.5},
        {"broker_name": "Bruno", "total_premium": 800.0},
    ]
    chart_spec = _heuristic_chart_spec(columns, rows)

    output_path = await generate_pdf(
        question="pergunta",
        response_text="resposta",
        sql="SELECT 1",
        columns=columns,
        rows=rows,
        metadata={},
        chart_spec=chart_spec,
    )

    try:
        assert output_path.exists()
        assert output_path.stat().st_size > 0
    finally:
        output_path.unlink(missing_ok=True)
