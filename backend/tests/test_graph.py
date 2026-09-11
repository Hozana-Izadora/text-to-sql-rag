from app.agents.graph import route_after_execution, route_after_validation
from app.agents.state import create_initial_state
from app.core.config import settings


def test_route_after_validation_valid_sql_goes_to_executor() -> None:
    state = create_initial_state("pergunta")
    state["sql_is_valid"] = True

    assert route_after_validation(state) == "sql_executor"


def test_route_after_validation_invalid_sql_under_retry_limit_goes_to_correction() -> None:
    state = create_initial_state("pergunta")
    state["sql_is_valid"] = False
    state["correction_count"] = 0

    assert route_after_validation(state) == "correction_planner"


def test_route_after_validation_invalid_sql_over_retry_limit_goes_to_response() -> None:
    state = create_initial_state("pergunta")
    state["sql_is_valid"] = False
    state["correction_count"] = settings.correction_max_retries

    assert route_after_validation(state) == "response_synthesizer"


def test_route_after_execution_success_goes_to_response() -> None:
    state = create_initial_state("pergunta")
    state["execution_error"] = None

    assert route_after_execution(state) == "response_synthesizer"


def test_route_after_execution_error_under_retry_limit_goes_to_correction() -> None:
    state = create_initial_state("pergunta")
    state["execution_error"] = "syntax error"
    state["correction_count"] = settings.correction_max_retries - 1

    assert route_after_execution(state) == "correction_planner"


def test_route_after_execution_error_over_retry_limit_goes_to_response() -> None:
    state = create_initial_state("pergunta")
    state["execution_error"] = "syntax error"
    state["correction_count"] = settings.correction_max_retries

    assert route_after_execution(state) == "response_synthesizer"
