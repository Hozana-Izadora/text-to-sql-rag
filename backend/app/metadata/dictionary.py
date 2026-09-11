from pathlib import Path

import yaml
from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger(__name__)


class EnumValueDict(BaseModel):
    label: str
    description: str | None = None


class ColumnDict(BaseModel):
    description: str | None = None
    synonyms: list[str] = []
    enum_values: dict[str, EnumValueDict] = {}


class TableDict(BaseModel):
    description: str | None = None
    synonyms: list[str] = []
    columns: dict[str, ColumnDict] = {}


class BusinessRuleDict(BaseModel):
    table: str | None = None
    type: str | None = None
    text: str


class DataDictionary(BaseModel):
    tables: dict[str, TableDict] = {}
    business_rules: list[BusinessRuleDict] = []

    def table(self, table_name: str) -> TableDict | None:
        return self.tables.get(table_name)

    def column(self, table_name: str, column_name: str) -> ColumnDict | None:
        table_dict = self.tables.get(table_name)
        if table_dict is None:
            return None
        return table_dict.columns.get(column_name)


def load_dictionary(path: str | Path) -> DataDictionary:
    """Carrega o dicionário de dados enriquecido a partir de um arquivo YAML."""
    file_path = Path(path)
    if not file_path.exists():
        logger.warning("dictionary_not_found", path=str(file_path))
        return DataDictionary()

    with file_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    return DataDictionary.model_validate(raw)
