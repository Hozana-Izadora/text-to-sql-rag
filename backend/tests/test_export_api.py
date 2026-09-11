import httpx
import pytest
from httpx import ASGITransport

from app.main import app

_BASE_BODY = {
    "question": "Quantos clientes ativos temos?",
    "responseText": "Temos 20 clientes ativos.",
    "sql": "SELECT COUNT(*) FROM clients",
    "columns": ["total"],
    "rows": [{"total": 20}],
    "metadata": {},
}


@pytest.mark.asyncio
async def test_export_docx_returns_file_with_correct_content_type() -> None:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/export", json={**_BASE_BODY, "format": "docx"})

    assert response.status_code == 200
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert "attachment" in response.headers["content-disposition"]
    assert response.content[:2] == b"PK"  # docx é um arquivo zip


@pytest.mark.asyncio
async def test_export_pdf_returns_file_with_correct_content_type() -> None:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/export", json={**_BASE_BODY, "format": "pdf"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_export_rejects_invalid_format() -> None:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/export", json={**_BASE_BODY, "format": "xlsx"})

    assert response.status_code == 422
