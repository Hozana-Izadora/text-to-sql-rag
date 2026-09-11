from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

_RATE_SUFFIXES = ("_rate", "_pct", "_percent", "_percentage")


class ColumnFormat(str, Enum):
    CURRENCY = "currency"
    INTEGER = "integer"
    DECIMAL_NUMBER = "decimal_number"
    DATE = "date"
    DATETIME = "datetime"
    TEXT = "text"


def infer_column_format(column_name: str, sample_value: Any) -> ColumnFormat:
    """Infere o formato de uma coluna a partir do tipo Python original vindo do asyncpg.

    Só é confiável ANTES do round-trip JSON do SSE (que colapsa Decimal em float e
    date/datetime em string ISO) — por isso isso roda uma única vez em
    app/api/streaming.py, logo após sql_executor, nunca re-inferido a partir de dados
    já serializados.
    """
    if isinstance(sample_value, bool):
        return ColumnFormat.TEXT  # bool é subclasse de int em Python — checar antes de int
    if isinstance(sample_value, Decimal):
        # commission_rate etc. são DECIMAL mas são taxas percentuais, não dinheiro.
        if column_name.lower().endswith(_RATE_SUFFIXES):
            return ColumnFormat.DECIMAL_NUMBER
        return ColumnFormat.CURRENCY
    if isinstance(sample_value, datetime):
        return ColumnFormat.DATETIME
    if isinstance(sample_value, date):
        return ColumnFormat.DATE
    if isinstance(sample_value, int):
        return ColumnFormat.INTEGER
    if isinstance(sample_value, float):
        return ColumnFormat.DECIMAL_NUMBER
    return ColumnFormat.TEXT


def build_column_format_map(columns: list[str], rows: list[dict]) -> dict[str, ColumnFormat]:
    """Constrói o mapa coluna -> formato usando o primeiro valor não-nulo de cada coluna."""
    formats: dict[str, ColumnFormat] = {}
    for column in columns:
        sample_value = next((row[column] for row in rows if row.get(column) is not None), None)
        formats[column] = infer_column_format(column, sample_value)
    return formats


def format_cell(value: Any, column_format: ColumnFormat) -> str:
    """Formata um valor para exibição em docx/pdf conforme o ColumnFormat.

    `value` pode já ter passado pelo round-trip JSON do SSE (Decimal->float,
    date->string ISO) — por isso não confia no tipo Python de `value`, só no
    `column_format` já inferido antes da serialização.
    """
    if value is None or value == "":
        return ""
    if column_format == ColumnFormat.CURRENCY:
        return f"R$ {_format_brl_number(value)}"
    if column_format == ColumnFormat.DECIMAL_NUMBER:
        return _format_brl_number(value)
    if column_format == ColumnFormat.INTEGER:
        try:
            return f"{int(value):,}".replace(",", ".")
        except (TypeError, ValueError):
            return str(value)
    if column_format == ColumnFormat.DATE:
        return _format_date_value(value, "%d/%m/%Y")
    if column_format == ColumnFormat.DATETIME:
        return _format_date_value(value, "%d/%m/%Y %H:%M")
    return str(value)


def _format_brl_number(value: Any) -> str:
    """Formata um número no padrão BRL: milhar com ponto, decimal com vírgula."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    formatted = f"{number:,.2f}"
    # "1,234.56" (en-US) -> "1.234,56" (BRL), via placeholder pra não colidir os separadores
    formatted = formatted.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return formatted


def _format_date_value(value: Any, fmt: str) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime(fmt)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime(fmt)
        except ValueError:
            return value
    return str(value)
