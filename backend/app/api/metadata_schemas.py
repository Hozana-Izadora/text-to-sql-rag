import uuid
from typing import Literal

from pydantic import BaseModel, Field


class SynonymResponse(BaseModel):
    id: uuid.UUID
    synonym: str
    language: str


class EnumValueResponse(BaseModel):
    id: uuid.UUID
    stored_value: str
    display_label: str | None
    description: str | None


class ColumnDetail(BaseModel):
    id: uuid.UUID
    column_name: str
    data_type: str | None
    is_nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    description: str | None
    sample_values: list[str] = []
    synonyms: list[SynonymResponse] = []
    enum_values: list[EnumValueResponse] = []


class TableDetailResponse(BaseModel):
    id: uuid.UUID
    table_name: str
    schema_name: str
    description: str | None
    row_count: int | None
    synonyms: list[SynonymResponse] = []
    columns: list[ColumnDetail] = []


class TableUpdate(BaseModel):
    description: str | None = None


class ColumnUpdate(BaseModel):
    description: str | None = None


class SynonymCreateRequest(BaseModel):
    entity_type: Literal["table", "column"]
    entity_id: uuid.UUID
    synonym: str = Field(..., min_length=1, max_length=255)
    language: str = "pt-BR"


class BusinessRuleResponse(BaseModel):
    id: uuid.UUID
    table_id: uuid.UUID | None
    rule_text: str
    rule_type: str | None


class BusinessRuleCreateRequest(BaseModel):
    table_id: uuid.UUID | None = None
    rule_text: str = Field(..., min_length=1)
    rule_type: Literal["filter", "join", "aggregation", "format", "general"] = "general"


class BusinessRuleUpdateRequest(BaseModel):
    rule_text: str | None = Field(None, min_length=1)
    rule_type: Literal["filter", "join", "aggregation", "format", "general"] | None = None


class EnumValueCreateRequest(BaseModel):
    column_id: uuid.UUID
    stored_value: str = Field(..., min_length=1)
    display_label: str | None = None
    description: str | None = None
