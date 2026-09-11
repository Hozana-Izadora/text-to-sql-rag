AGENT_LLM_CONFIG: dict[str, dict[str, str]] = {
    "schema_linker": {"provider": "gemini", "model": "gemini-3.6-flash"},
    "subproblem_agent": {"provider": "gemini", "model": "gemini-3.6-flash"},
    "query_planner": {"provider": "gemini", "model": "gemini-3.6-flash"},
    "sql_generator": {"provider": "gemini", "model": "gemini-3.6-flash"},
    "correction_planner": {"provider": "groq", "model": "openai/gpt-oss-120b"},
    "correction_sql": {"provider": "groq", "model": "openai/gpt-oss-120b"},
    "response_synthesizer": {"provider": "gemini", "model": "gemini-3.6-flash"},
}
