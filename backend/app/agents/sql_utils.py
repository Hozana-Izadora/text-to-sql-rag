import re

import sqlparse
from sqlparse.sql import Identifier, IdentifierList, Parenthesis, TokenList
from sqlparse.tokens import CTE, Keyword

_MARKDOWN_FENCE_RE = re.compile(r"^```(?:sql)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)
_LINE_COMMENT_RE = re.compile(r"--.*?$", re.MULTILINE)


def clean_generated_sql(raw: str) -> str:
    """Remove blocos markdown (```sql ... ```), comentários `--`, ponto-e-vírgula final e whitespace."""
    cleaned = _MARKDOWN_FENCE_RE.sub("", raw)
    cleaned = _LINE_COMMENT_RE.sub("", cleaned)
    cleaned = cleaned.strip()
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
    return cleaned


def _real_name(identifier: Identifier) -> str | None:
    name = identifier.get_real_name()
    return name.lower() if name else None


def _names_from_table_ref(token) -> list[str]:
    """Extrai nome(s) de tabela de um token que aparece logo após FROM/JOIN."""
    if isinstance(token, IdentifierList):
        return [name for item in token.get_identifiers() if isinstance(item, Identifier) and (name := _real_name(item))]
    if isinstance(token, Identifier):
        name = _real_name(token)
        return [name] if name else []
    value = token.value.strip()
    if value and not value.startswith("(") and token.ttype is not None:
        return [value.split(".")[-1].strip('"`').lower()]
    return []


def _cte_names_and_bodies(token) -> list[tuple[str | None, Parenthesis | None]]:
    """Para o token que segue WITH: devolve [(nome_da_cte, subquery_parenthesis), ...]."""
    identifiers = token.get_identifiers() if isinstance(token, IdentifierList) else [token]
    results: list[tuple[str | None, Parenthesis | None]] = []
    for item in identifiers:
        if not isinstance(item, TokenList):
            continue
        first = item.token_first(skip_cm=True)
        name = first.value.strip('"`').lower() if first is not None else None
        body = next((sub for sub in item.tokens if isinstance(sub, Parenthesis)), None)
        results.append((name, body))
    return results


def _walk(tokens, cte_names: set[str], tables: set[str]) -> None:
    expecting_table = False
    expecting_cte = False

    for token in tokens:
        if token.is_whitespace:
            continue

        if expecting_cte:
            expecting_cte = False
            for name, body in _cte_names_and_bodies(token):
                if name:
                    cte_names.add(name)
                if body is not None:
                    _walk(body.tokens, cte_names, tables)
            continue

        if expecting_table:
            expecting_table = False
            if isinstance(token, Parenthesis):
                _walk(token.tokens, cte_names, tables)
            else:
                tables.update(_names_from_table_ref(token))
            continue

        normalized = (token.normalized or "").upper()

        if token.ttype is CTE or (token.ttype is Keyword and normalized == "WITH"):
            expecting_cte = True
            continue

        if token.ttype is Keyword and (normalized == "FROM" or "JOIN" in normalized):
            expecting_table = True
            continue

        if isinstance(token, TokenList):
            _walk(token.tokens, cte_names, tables)


def extract_referenced_tables(sql: str) -> set[str]:
    """Extrai os nomes de tabela referenciados em FROM/JOIN (minúsculo), excluindo
    nomes definidos por CTE (WITH nome AS (...)) — esses não são tabelas reais do schema."""
    tables: set[str] = set()
    cte_names: set[str] = set()

    for statement in sqlparse.parse(sql):
        _walk(statement.tokens, cte_names, tables)

    return tables - cte_names
