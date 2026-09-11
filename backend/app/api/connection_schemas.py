import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.database.introspection.types import ConnectionConfig, ConnectionTestResult

__all__ = [
    "ConnectionConfig",
    "ConnectionCreate",
    "ConnectionDetailResponse",
    "ConnectionResponse",
    "ConnectionTestRequest",
    "ConnectionTestResult",
    "ConnectionUpdate",
    "IntrospectionResult",
]

DbType = Literal["postgresql", "mysql", "sqlserver", "oracle", "sqlite"]


class ConnectionTestRequest(BaseModel):
    """Parâmetros para testar uma conexão antes de salvá-la (botão "Testar" do modal)."""

    db_type: DbType
    host: str = Field(..., min_length=1)
    port: int = Field(..., gt=0, le=65535)
    database_name: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: str
    ssl_enabled: bool = False
    schema_name: str = "public"

    def to_config(self) -> ConnectionConfig:
        return ConnectionConfig(
            db_type=self.db_type,
            host=self.host,
            port=self.port,
            database_name=self.database_name,
            username=self.username,
            password=self.password,
            ssl_enabled=self.ssl_enabled,
            schema_name=self.schema_name,
        )


class ConnectionCreate(ConnectionTestRequest):
    name: str = Field(..., min_length=1, max_length=100)


class ConnectionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    host: str | None = None
    port: int | None = Field(None, gt=0, le=65535)
    database_name: str | None = None
    username: str | None = None
    password: str | None = None
    ssl_enabled: bool | None = None
    schema_name: str | None = None
    is_active: bool | None = None

    def touches_credentials(self) -> bool:
        return any(
            value is not None
            for value in (self.host, self.port, self.database_name, self.username, self.password, self.ssl_enabled)
        )


class ConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    db_type: str
    host: str
    port: int
    database_name: str
    username: str
    ssl_enabled: bool
    schema_name: str
    is_active: bool
    table_count: int | None
    last_introspected_at: datetime | None
    created_at: datetime


class ConnectionDetailResponse(ConnectionResponse):
    column_count: int


class IntrospectionResult(BaseModel):
    tables: int
    columns: int
    relationships: int
    embeddings: int
    warnings: list[str] = []
