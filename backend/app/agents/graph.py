from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.correction_planner import correction_planner_node
from app.agents.correction_sql import correction_sql_node
from app.agents.query_planner import query_planner_node
from app.agents.response_synthesizer import response_synthesizer_node
from app.agents.schema_linker import schema_linker_node
from app.agents.sql_executor import sql_executor_node
from app.agents.sql_generator import sql_generator_node
from app.agents.sql_validator import sql_validator_node
from app.agents.state import AgentState
from app.agents.subproblem import subproblem_node
from app.core.config import settings


def route_after_validation(state: AgentState) -> str:
    if state["sql_is_valid"]:
        return "sql_executor"
    if state["correction_count"] < settings.correction_max_retries:
        return "correction_planner"
    return "response_synthesizer"


def route_after_execution(state: AgentState) -> str:
    if state["execution_error"] is None:
        return "response_synthesizer"
    if state["correction_count"] < settings.correction_max_retries:
        return "correction_planner"
    return "response_synthesizer"


def build_graph() -> Any:
    graph = StateGraph(AgentState)

    graph.add_node("schema_linker", schema_linker_node)
    graph.add_node("subproblem_agent", subproblem_node)
    graph.add_node("query_planner", query_planner_node)
    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("sql_validator", sql_validator_node)
    graph.add_node("sql_executor", sql_executor_node)
    graph.add_node("correction_planner", correction_planner_node)
    graph.add_node("correction_sql", correction_sql_node)
    graph.add_node("response_synthesizer", response_synthesizer_node)

    graph.set_entry_point("schema_linker")
    graph.add_edge("schema_linker", "subproblem_agent")
    graph.add_edge("subproblem_agent", "query_planner")
    graph.add_edge("query_planner", "sql_generator")
    graph.add_edge("sql_generator", "sql_validator")

    graph.add_conditional_edges("sql_validator", route_after_validation)
    graph.add_conditional_edges("sql_executor", route_after_execution)

    graph.add_edge("correction_planner", "correction_sql")
    graph.add_edge("correction_sql", "sql_validator")

    graph.add_edge("response_synthesizer", END)

    return graph.compile()
