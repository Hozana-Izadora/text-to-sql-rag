import uuid

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from app.agents.config import AGENT_LLM_CONFIG
from app.agents.llm_utils import invoke_structured
from app.agents.state import AgentState
from app.core.llm_provider import get_llm
from app.core.logging import get_logger
from app.database.connection import get_metadata_session
from app.metadata.embeddings import get_embedding_service_async
from app.metadata.models import Table
from app.metadata.repository import MetadataRepository
from app.metadata.schemas import (
    BusinessRuleContext,
    EnumValueContext,
    MatchedKeyword,
    RelationshipContext,
    SearchResult,
    SyntheticExampleMatch,
)

logger = get_logger(__name__)


class KeywordExtraction(BaseModel):
    keywords: list[str]


class TableSelection(BaseModel):
    tables: list[str]
    reasoning: str | None = None


_KEYWORD_EXTRACTION_PROMPT = """Extraia as palavras-chave relevantes para uma consulta SQL a partir da pergunta abaixo.
Foque em substantivos e termos de domínio (entidades, valores, status, datas). Ignore artigos, preposições e verbos genéricos.

Pergunta: {question}"""

_TABLE_CONFIRMATION_PROMPT = """Você é um especialista em schema linking para Text-to-SQL. Dada a pergunta do \
usuário, as keywords já casadas no dicionário de dados, as tabelas candidatas sugeridas por busca semântica, e a \
lista completa de tabelas do banco, decida quais tabelas são realmente necessárias para responder a pergunta.

Você PODE adicionar tabelas que não apareceram nos candidatos (ex.: tabelas intermediárias necessárias para JOINs) \
e PODE remover candidatas irrelevantes. Use APENAS nomes de tabelas que existem na lista completa abaixo.

Pergunta: {question}

Keywords casadas no dicionário de dados:
{matched_keywords}

Tabelas candidatas (busca semântica):
{candidate_tables}

Lista completa de tabelas do banco:
{all_tables}

Retorne a lista final de tabelas necessárias."""


async def _extract_keywords(llm: BaseChatModel, question: str) -> list[str]:
    result = await invoke_structured(
        llm, KeywordExtraction, _KEYWORD_EXTRACTION_PROMPT.format(question=question)
    )
    return result.keywords


async def _match_keywords_to_dictionary(
    repository: MetadataRepository, keywords: list[str], connection_id: uuid.UUID | None
) -> list[MatchedKeyword]:
    matches: list[MatchedKeyword] = []
    for keyword in keywords:
        matches.extend(await repository.search_synonyms(keyword, connection_id))
        matches.extend(await repository.search_enum_values(keyword, connection_id))
    return matches


async def _resolve_rag_candidates(repository: MetadataRepository, hits: list[SearchResult]) -> list[str]:
    """Resolve hits de tabela/coluna do RAG de volta pro nome da tabela. Hits de
    source_type='rule' não mapeiam pra uma tabela específica (podem ser globais)."""
    candidates: list[str] = []
    seen: set[str] = set()
    for hit in hits:
        table_name: str | None = None
        if hit.source_type == "table":
            table_name = await repository.get_table_name_by_id(hit.source_id)
        elif hit.source_type == "column":
            table_name = await repository.get_table_name_by_column_id(hit.source_id)
        if table_name and table_name not in seen:
            seen.add(table_name)
            candidates.append(table_name)
    return candidates


def _merge_candidates(matched: list[MatchedKeyword], rag_tables: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for match in matched:
        if match.table_name not in seen:
            seen.add(match.table_name)
            merged.append(match.table_name)
    for table_name in rag_tables:
        if table_name not in seen:
            seen.add(table_name)
            merged.append(table_name)
    return merged


def _format_matched_keywords(matched: list[MatchedKeyword]) -> str:
    if not matched:
        return "Nenhuma."
    lines = []
    for match in matched:
        target = f"{match.table_name}.{match.column_name}" if match.column_name else match.table_name
        lines.append(f"- '{match.keyword}' -> {target} (valor: {match.matched_value})")
    return "\n".join(lines)


async def _confirm_tables(
    llm: BaseChatModel,
    question: str,
    matched: list[MatchedKeyword],
    candidates: list[str],
    all_tables: list[str],
) -> TableSelection:
    prompt = _TABLE_CONFIRMATION_PROMPT.format(
        question=question,
        matched_keywords=_format_matched_keywords(matched),
        candidate_tables=", ".join(candidates) or "Nenhuma.",
        all_tables=", ".join(all_tables),
    )
    selection = await invoke_structured(llm, TableSelection, prompt)

    # Defesa contra alucinação: só aceita tabelas que realmente existem no schema.
    valid_tables = {name.lower() for name in all_tables}
    filtered = [name for name in selection.tables if name.lower() in valid_tables]
    if not filtered:
        filtered = candidates

    return TableSelection(tables=filtered, reasoning=selection.reasoning)


async def _load_selected_tables(
    repository: MetadataRepository, table_names: list[str], connection_id: uuid.UUID | None
) -> list[Table]:
    tables: list[Table] = []
    for name in table_names:
        table = await repository.get_table_by_name(name, connection_id=connection_id)
        if table is not None:
            tables.append(table)
    return tables


def _format_table_ddl(table: Table) -> str:
    header = f"-- Tabela {table.table_name}"
    if table.description:
        header += f": {table.description}"

    column_defs = []
    for column in table.columns:
        flags = []
        if column.is_primary_key:
            flags.append("PK")
        if column.is_foreign_key:
            flags.append("FK")
        comment_bits = flags + ([column.description] if column.description else [])
        comment = f"  -- {', '.join(comment_bits)}" if comment_bits else ""
        column_defs.append(f"    {column.column_name} {column.data_type}{comment}")

    body = ",\n".join(column_defs)
    return f"{header}\nCREATE TABLE {table.table_name} (\n{body}\n);"


def _format_enum_values(enum_values: list[EnumValueContext]) -> str:
    if not enum_values:
        return ""
    lines = ["-- Valores possíveis (enums):"]
    for enum_value in enum_values:
        label = f' "{enum_value.display_label}"' if enum_value.display_label else ""
        description = f" ({enum_value.description})" if enum_value.description else ""
        lines.append(f"--   {enum_value.table_name}.{enum_value.column_name} = '{enum_value.stored_value}'{label}{description}")
    return "\n".join(lines)


def _format_relationships(relationships: list[RelationshipContext]) -> str:
    if not relationships:
        return ""
    lines = ["-- Relacionamentos (FKs):"]
    for relationship in relationships:
        lines.append(
            f"--   {relationship.source_table}.{relationship.source_column} -> "
            f"{relationship.target_table}.{relationship.target_column}"
        )
    return "\n".join(lines)


def _format_business_rules(rules: list[BusinessRuleContext]) -> str:
    if not rules:
        return ""
    lines = ["-- Regras de negócio:"]
    for rule in rules:
        scope = rule.table_name or "geral"
        lines.append(f"--   [{scope}] {rule.rule_text}")
    return "\n".join(lines)


async def _build_schema_context(
    repository: MetadataRepository,
    tables: list[Table],
    table_names: list[str],
    connection_id: uuid.UUID | None,
) -> str:
    ddl_blocks = [_format_table_ddl(table) for table in tables]

    enum_values = await repository.list_enum_values_for_tables(table_names, connection_id)
    relationships = await repository.list_relationships_for_tables(table_names, connection_id)
    business_rules = await repository.list_business_rules_for_tables(table_names, connection_id)

    sections = ["\n\n".join(ddl_blocks)]
    for section in (
        _format_enum_values(enum_values),
        _format_relationships(relationships),
        _format_business_rules(business_rules),
    ):
        if section:
            sections.append(section)

    return "\n\n".join(sections)


def _filter_few_shot(examples: list[SyntheticExampleMatch], relevant_tables: list[str]) -> list[dict]:
    relevant_set = set(relevant_tables)
    filtered = [example for example in examples if relevant_set.intersection(example.tables_used)]
    return [example.model_dump(mode="json") for example in filtered]


async def schema_linker_node(state: AgentState) -> dict:
    """Nó 1: combina matching no dicionário (DANKE) + RAG vetorial com confirmação
    via LLM (SoT) para decidir o conjunto final de tabelas e montar o schema_context."""
    llm = get_llm(**AGENT_LLM_CONFIG["schema_linker"])
    question = state["question"]
    connection_id = uuid.UUID(state["connection_id"]) if state.get("connection_id") else None

    keywords = await _extract_keywords(llm, question)

    async with get_metadata_session() as session:
        repository = MetadataRepository(session)
        embedding_service = await get_embedding_service_async()

        matched = await _match_keywords_to_dictionary(repository, keywords, connection_id)
        rag_hits = await embedding_service.search(
            session, question, source_types=["table", "column", "rule"], top_k=10, connection_id=connection_id
        )
        few_shot_hits = await embedding_service.search_synthetic_examples(
            session, question, top_k=5, connection_id=connection_id
        )

        rag_tables = await _resolve_rag_candidates(repository, rag_hits)
        candidates = _merge_candidates(matched, rag_tables)

        all_tables = [table.table_name for table in await repository.list_tables(connection_id)]
        selection = await _confirm_tables(llm, question, matched, candidates, all_tables)

        relevant_tables = selection.tables
        tables = await _load_selected_tables(repository, relevant_tables, connection_id)
        relevant_columns = {table.table_name: [c.column_name for c in table.columns] for table in tables}
        schema_context = await _build_schema_context(repository, tables, relevant_tables, connection_id)

    logger.info(
        "schema_linker_done",
        question=question,
        keywords=keywords,
        relevant_tables=relevant_tables,
    )

    return {
        "relevant_tables": relevant_tables,
        "relevant_columns": relevant_columns,
        "schema_context": schema_context,
        "few_shot_examples": _filter_few_shot(few_shot_hits, relevant_tables),
        "matched_keywords": [match.model_dump() for match in matched],
    }
