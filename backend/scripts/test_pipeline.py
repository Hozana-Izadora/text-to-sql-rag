"""Testa o pipeline completo com perguntas do domínio SeguraPro.

Roda fora do pytest — é um teste funcional manual.

Uso: cd backend && uv run python -m scripts.test_pipeline
"""

import asyncio
import time

from app.agents.pipeline import Pipeline
from app.core.logging import configure_logging, get_logger
from app.database.connection import get_metadata_session
from app.metadata.connections import list_connections

logger = get_logger(__name__)

CONNECTION_NAME = "Produção SeguraPro"

TEST_QUESTIONS = [
    # Simples — 1 tabela, sem JOIN
    "Quantos clientes ativos temos?",
    "Quais corretores estão ativos?",
    # Média — JOIN simples, filtro
    "Qual o total de prêmios das apólices vigentes?",
    "Quais sinistros estão em análise?",
    # Média-alta — JOIN + agregação + GROUP BY
    "Qual o total de prêmios por corretor nas apólices ativas?",
    "Quantas apólices cada seguradora tem vigentes?",
    # Complexa — múltiplos JOINs, regra de negócio
    "Qual a sinistralidade por ramo de seguro?",
    "Quais parcelas estão em atraso e de qual cliente?",
    # Complexa — subquery ou HAVING
    "Quais corretores têm mais de R$ 1.000 em comissões pendentes?",
    "Qual seguradora tem o menor prêmio médio em seguros auto?",
]


def _print_result(question: str, state: dict, elapsed_seconds: float) -> None:
    print(f"\n{'=' * 80}")
    print(f"PERGUNTA: {question}")
    print(f"{'-' * 80}")
    print(f"Tabelas selecionadas: {state.get('relevant_tables')}")
    print(f"SQL gerado: {state.get('generated_sql')}")
    print(f"Tentativas de correção: {state.get('correction_count')}")
    if state.get("execution_error"):
        print(f"Erro final: {state.get('execution_error')}")
    print(f"Linhas retornadas: {state.get('row_count')} (truncado: {state.get('was_truncated')})")
    print(f"Resposta:\n{state.get('response_text')}")
    print(f"Tempo total: {elapsed_seconds:.2f}s")


async def main() -> None:
    configure_logging()
    pipeline = Pipeline()

    async with get_metadata_session() as session:
        connections = await list_connections(session, active_only=True)
    connection = next((c for c in connections if c.name == CONNECTION_NAME), None) or (
        connections[0] if connections else None
    )
    if connection is None:
        raise SystemExit(
            "Nenhuma conexão cadastrada. Rode 'uv run python -m scripts.migrate_to_multi_connection'."
        )

    for question in TEST_QUESTIONS:
        start = time.perf_counter()
        state = await pipeline.run(question, str(connection.id), connection.db_type)
        elapsed = time.perf_counter() - start
        _print_result(question, state, elapsed)


if __name__ == "__main__":
    asyncio.run(main())
