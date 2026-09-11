from app.database.introspection.base import BaseIntrospector
from app.database.introspection.mysql import MySQLIntrospector
from app.database.introspection.postgres import PostgresIntrospector
from app.database.introspection.sqlserver import SQLServerIntrospector
from app.database.introspection.types import ConnectionConfig

_INTROSPECTORS: dict[str, type[BaseIntrospector]] = {
    "postgresql": PostgresIntrospector,
    "mysql": MySQLIntrospector,
    "sqlserver": SQLServerIntrospector,
}

_NOT_YET_SUPPORTED = {"oracle", "sqlite"}


def get_introspector(config: ConnectionConfig) -> BaseIntrospector:
    """Devolve o introspector do dialeto de `config.db_type`."""
    introspector_cls = _INTROSPECTORS.get(config.db_type)
    if introspector_cls is not None:
        return introspector_cls(config)
    if config.db_type in _NOT_YET_SUPPORTED:
        raise NotImplementedError(
            f"Introspecção para '{config.db_type}' ainda não é suportada nesta versão."
        )
    raise ValueError(f"db_type desconhecido: {config.db_type!r}")
