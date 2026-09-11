from langchain_core.language_models import BaseChatModel

from app.core.config import settings

_DEFAULT_MODELS = {
    "gemini": "gemini-3.6-flash",
    "groq": "openai/gpt-oss-120b",
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
}


def get_llm(
    provider: str = "gemini",
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> BaseChatModel:
    """Factory que retorna o ChatModel do LangChain para o provider solicitado.

    Providers suportados: "gemini", "groq", "openai" (futuro), "anthropic" (futuro).
    API keys vêm das variáveis de ambiente via app.core.config.settings.
    """
    resolved_model = model or _DEFAULT_MODELS.get(provider)
    if resolved_model is None:
        raise ValueError(f"Provider desconhecido: {provider}")

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=resolved_model,
            temperature=temperature,
            max_output_tokens=max_tokens,
            google_api_key=settings.gemini_api_key,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.groq_api_key,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    raise ValueError(f"Provider não suportado: {provider}")
