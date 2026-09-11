from enum import Enum


class OutputType(str, Enum):
    TEXT = "text"
    CHART = "chart"
    DOCX = "docx"
    PDF = "pdf"


_DOCX_KEYWORDS = ("word", "docx", "documento word", "relatório word", "relatorio word")
_PDF_KEYWORDS = ("pdf", "relatório pdf", "relatorio pdf")
# "mostre"/"mostra" propositalmente NÃO entram aqui: são verbos genéricos demais
# ("Mostre os clientes ativos" não é um pedido de gráfico) — o exemplo do spec ("Mostre
# um gráfico...") continua funcionando porque "gráfico" já é keyword própria.
_CHART_KEYWORDS = (
    "gráfico",
    "grafico",
    "chart",
    "visualize",
    "visualizar",
    "plotar",
    "plot",
    "barras",
    "pizza",
    "linha",
    "histograma",
)


def classify_output(question: str) -> OutputType:
    """Classifica o tipo de output desejado a partir de keywords (sem LLM).

    Prioridade quando múltiplos matcham: DOCX > PDF > CHART > TEXT.
    """
    normalized = question.lower()

    if any(keyword in normalized for keyword in _DOCX_KEYWORDS):
        return OutputType.DOCX
    if any(keyword in normalized for keyword in _PDF_KEYWORDS):
        return OutputType.PDF
    if any(keyword in normalized for keyword in _CHART_KEYWORDS):
        return OutputType.CHART
    return OutputType.TEXT
