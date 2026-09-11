"""Geração de dataset sintético few-shot (pares pergunta/SQL).

Placeholder para a Fase 2 do projeto: uso do pipeline de agentes para gerar
pares (question_nl, query_sql) sintéticos a partir do schema ingerido, a
serem persistidos em `synthetic_examples` para few-shot retrieval.
"""

from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


def main() -> None:
    configure_logging()
    logger.warning("generate_synthetic_not_implemented", detail="Planejado para a Fase 2")


if __name__ == "__main__":
    main()
