from typing import Any, TypeVar

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


def extract_text_content(content: Any) -> str:
    """Extrai o texto de AIMessage.content.

    Alguns modelos (ex.: Gemini com extended thinking) devolvem `content` como uma
    lista de content blocks (`[{"type": "text", "text": "..."}, {"type": "thinking", ...}]`)
    em vez de uma string simples — usar `str(content)` direto nesse caso produz o repr
    do Python (`"[{'type': ...}]"`), não o texto real.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)


async def invoke_structured(llm: BaseChatModel, schema: type[T], prompt: str, *, retries: int = 2) -> T:
    """Invoca o LLM pedindo saída estruturada no formato `schema`, com retry simples.

    Modelos free-tier ocasionalmente devolvem tool-calls malformados; um retry único
    evita que uma falha pontual de parsing derrube o pipeline inteiro.
    """
    structured_llm = llm.with_structured_output(schema, method="function_calling")

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            result = await structured_llm.ainvoke(prompt)
            return schema.model_validate(result)
        except Exception as exc:
            last_error = exc
            logger.warning(
                "structured_output_retry", schema=schema.__name__, attempt=attempt, error=str(exc)
            )

    assert last_error is not None
    raise last_error
