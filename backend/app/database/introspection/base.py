import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from app.database.introspection.types import (
    ConnectionConfig,
    ConnectionTestResult,
    TableMetadata,
)

# Cardinalidade máxima para uma coluna ser tratada como enum (e ter sample_values).
LOW_CARDINALITY_THRESHOLD = 50
SAMPLE_VALUES_LIMIT = 5


class BaseIntrospector(ABC):
    """Interface comum para introspecção de schema, um dialeto por subclasse.

    Cada instância gerencia o ciclo de vida da própria conexão — recebe só os
    parâmetros (`ConnectionConfig`), abre a conexão dentro de cada método e fecha
    ao terminar. Isso permite testar uma conexão antes de qualquer coisa ser salva.
    """

    def __init__(self, config: ConnectionConfig) -> None:
        self._config = config

    @abstractmethod
    async def introspect(self) -> list[TableMetadata]:
        """Extrai o schema completo do banco (tabelas, colunas, PKs, FKs, samples)."""

    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """Abre a conexão, roda um SELECT trivial e devolve versão + latência."""


async def timed_test_connection(
    probe: Callable[[], Awaitable[str | None]],
) -> ConnectionTestResult:
    """Helper compartilhado: mede latência e traduz exceção em mensagem amigável.

    `probe` deve abrir a conexão, obter a versão do servidor (ou None) e fechar.
    """
    start = time.perf_counter()
    try:
        db_version = await probe()
    except Exception as exc:  # driver-specific — normalizado para o usuário
        return ConnectionTestResult(success=False, message=str(exc) or exc.__class__.__name__)
    latency_ms = int((time.perf_counter() - start) * 1000)
    return ConnectionTestResult(
        success=True, message="Conexão OK", db_version=db_version, latency_ms=latency_ms
    )
