from app.agents.state import create_initial_state


def test_create_initial_state_defaults() -> None:
    state = create_initial_state("Quantos clientes ativos temos?")

    assert state["question"] == "Quantos clientes ativos temos?"
    assert state["relevant_tables"] == []
    assert state["relevant_columns"] == {}
    assert state["schema_context"] == ""
    assert state["few_shot_examples"] == []
    assert state["matched_keywords"] == []
    assert state["subproblems"] == {}
    assert state["query_plan"] == ""
    assert state["generated_sql"] == ""
    assert state["sql_is_valid"] is False
    assert state["execution_result"] is None
    assert state["execution_error"] is None
    assert state["row_count"] == 0
    assert state["was_truncated"] is False
    assert state["correction_count"] == 0
    assert state["correction_plan"] is None
    assert state["error_category"] is None
    assert state["response_text"] == ""
    assert state["response_data"] is None
