import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ColumnCreate(BaseModel):
    column_name: str
    data_type: str | None = None
    is_nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    description: str | None = None
    sample_values: list[str] = []


class TableCreate(BaseModel):
    table_name: str
    schema_name: str = "public"
    description: str | None = None
    row_count: int | None = None
    columns: list[ColumnCreate] = []


class RelationshipCreate(BaseModel):
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    constraint_name: str | None = None


class SynonymCreate(BaseModel):
    entity_type: str
    entity_id: uuid.UUID
    synonym: str
    language: str = "pt-BR"


class BusinessRuleCreate(BaseModel):
    table_name: str | None = None
    rule_text: str
    rule_type: str | None = None


class EnumValueCreate(BaseModel):
    stored_value: str
    display_label: str | None = None
    description: str | None = None


class SyntheticExampleCreate(BaseModel):
    question_nl: str
    query_sql: str
    tables_used: list[str] = []
    difficulty: str | None = None


class SearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_type: str
    source_id: uuid.UUID
    content_text: str
    distance: float


class SyntheticExampleMatch(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question_nl: str
    query_sql: str
    tables_used: list[str]
    distance: float


class MatchedKeyword(BaseModel):
    """Resultado de matching de uma keyword da pergunta contra o dicionário de dados."""

    keyword: str
    match_type: Literal["synonym", "enum_value"]
    table_name: str
    column_name: str | None = None
    matched_value: str


class EnumValueContext(BaseModel):
    """Valor de enum de uma coluna, resolvido para uso no schema_context."""

    table_name: str
    column_name: str
    stored_value: str
    display_label: str | None = None
    description: str | None = None


class RelationshipContext(BaseModel):
    """Relationship (FK) resolvida por nome de tabela, para uso no schema_context."""

    source_table: str
    source_column: str
    target_table: str
    target_column: str


class BusinessRuleContext(BaseModel):
    """Business rule resolvida por nome de tabela (ou global), para uso no schema_context."""

    table_name: str | None
    rule_text: str
    rule_type: str | None
