import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.export.chart_generator import ChartSpec
from app.export.formatting import ColumnFormat


class ChatRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    question: str = Field(..., min_length=3, max_length=1000)
    connection_id: uuid.UUID


class ChatEvent(BaseModel):
    event: str
    data: Any


class ExportRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    format: Literal["docx", "pdf"]
    question: str
    response_text: str
    sql: str
    columns: list[str]
    rows: list[dict]
    metadata: dict
    # Computado uma única vez em app/api/streaming.py (logo após sql_executor, quando
    # execution_result ainda tem os tipos Python originais do asyncpg) e repassado pelo
    # frontend — nunca re-inferido aqui a partir de `rows`, que já perdeu Decimal/date
    # no round-trip JSON do SSE.
    column_formats: dict[str, ColumnFormat] | None = None
    chart_spec: ChartSpec | None = None
