from typing import TypedDict


class AgentState(TypedDict):
    # Entrada
    question: str
    # UUID (como str) da conexão-alvo e dialeto do banco dela ("postgresql" | "mysql" |
    # "sqlserver"). Vazio/"postgresql" nos contextos de teste sem conexão real.
    connection_id: str
    dialect: str

    # Schema Linker
    relevant_tables: list[str]
    relevant_columns: dict[str, list[str]]
    schema_context: str
    few_shot_examples: list[dict]
    matched_keywords: list[dict]

    # Subproblem Agent
    subproblems: dict[str, str]

    # Query Plan Agent
    query_plan: str

    # SQL Generator
    generated_sql: str
    sql_is_valid: bool

    # SQL Executor
    execution_result: list[dict] | None
    execution_error: str | None
    row_count: int
    was_truncated: bool

    # Correction Loop
    correction_count: int
    correction_plan: str | None
    error_category: str | None

    # Response
    response_text: str
    response_data: list[dict] | None


def create_initial_state(
    question: str, connection_id: str = "", dialect: str = "postgresql"
) -> AgentState:
    """Popula o AgentState inicial com os defaults de cada campo (TypedDict não tem defaults)."""
    return AgentState(
        question=question,
        connection_id=connection_id,
        dialect=dialect,
        relevant_tables=[],
        relevant_columns={},
        schema_context="",
        few_shot_examples=[],
        matched_keywords=[],
        subproblems={},
        query_plan="",
        generated_sql="",
        sql_is_valid=False,
        execution_result=None,
        execution_error=None,
        row_count=0,
        was_truncated=False,
        correction_count=0,
        correction_plan=None,
        error_category=None,
        response_text="",
        response_data=None,
    )
