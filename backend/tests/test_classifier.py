import pytest

from app.export.classifier import OutputType, classify_output


@pytest.mark.parametrize(
    "question,expected",
    [
        ("Mostre um gráfico dos prêmios por corretor", OutputType.CHART),
        ("Quantos sinistros por status? faça um gráfico de pizza", OutputType.CHART),
        ("Plote as vendas em barras", OutputType.CHART),
        ("Gere um relatório em Word dos sinistros abertos", OutputType.DOCX),
        ("Quero um documento word com os dados", OutputType.DOCX),
        ("Quero um PDF com o resumo de produção mensal", OutputType.PDF),
        ("Gera um relatorio pdf", OutputType.PDF),
        ("Quantos clientes ativos temos?", OutputType.TEXT),
        ("Mostre os clientes ativos", OutputType.TEXT),
        ("Mostre quais corretores estão ativos", OutputType.TEXT),
    ],
)
def test_classify_output(question: str, expected: OutputType) -> None:
    assert classify_output(question) == expected


def test_classify_output_prioritizes_docx_over_pdf_and_chart() -> None:
    question = "Gere um gráfico e também um relatório word em pdf"
    assert classify_output(question) == OutputType.DOCX


def test_classify_output_prioritizes_pdf_over_chart() -> None:
    question = "Quero um gráfico de barras em pdf"
    assert classify_output(question) == OutputType.PDF
