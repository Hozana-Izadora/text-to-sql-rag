# CLAUDE.md — Instruções para Claude Code

## Sobre o projeto

Inquiro é uma plataforma Text-to-SQL corporativa que converte perguntas em linguagem natural em consultas SQL, executa-as de forma segura e retorna respostas em linguagem natural com suporte a gráficos e relatórios.

A arquitetura combina duas abordagens acadêmicas: a camada de metadados do DANKE (knowledge graph, dicionário de sinônimos, dataset sintético few-shot, view synthesis) com o pipeline multi-agente do SQL-of-Thought (schema linking, subproblem decomposition, query plan com CoT, SQL generation, correction loop guiado por taxonomia de erros).

## Stack e dependências

- **Backend:** Python 3.12, FastAPI, LangGraph, LangChain, SQLAlchemy, asyncpg, sentence-transformers
- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS puro — sem kit de componentes (shadcn/ui) nem
  lib de estado global (zustand): estado do chat é local ao `ChatContainer`, streaming via `fetch` +
  `ReadableStream` manual (sem Vercel AI SDK). Recharts fica reservado para a Fase 4 (gráficos), ainda não
  integrado.
- **Banco de dados:** PostgreSQL 16 com pgvector (vector store) + PostgreSQL de produção (read-only)
- **LLMs:** Gemini (primário), Groq (secundário, correction loop) — ambos free tier. Nomes de modelo exatos
  vivem em `app/agents/config.py` (`AGENT_LLM_CONFIG`) e mudam com o tempo por deprecação dos providers —
  não hardcode um nome de modelo específico aqui no CLAUDE.md além de exemplo ilustrativo.
- **Embeddings:** `intfloat/multilingual-e5-small` via sentence-transformers (CPU) — multilíngue, necessário
  pois as perguntas são em PT-BR
- **Infra:** Docker Compose

## Comandos de desenvolvimento

```bash
# Subir ambiente completo
docker compose up -d

# Backend isolado (dev)
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Frontend isolado (dev)
cd frontend && npm run dev

# Rodar testes backend
cd backend && uv run pytest

# Rodar linter backend
cd backend && uv run ruff check .

# Ingestão de metadados
cd backend && uv run python -m scripts.ingest_metadata

# Gerar dataset sintético few-shot
cd backend && uv run python -m scripts.generate_synthetic_dataset
```

## Estrutura de código e convenções

### Python (backend)
- Ambiente virtual (`venv`)
- Gerenciador de pacotes: `uv` (pyproject.toml)
- Tipagem forte obrigatória: usar type hints em todas as funções e classes
- Modelos de dados: Pydantic v2 para validação, SQLAlchemy para ORM
- Async first: usar `async def` para handlers FastAPI e operações de I/O
- Exceções: nunca silenciar exceções; usar `raise` com tipos específicos
- Imports: absolutos a partir de `app.` (ex: `from app.core.config import settings`)
- Formatação: Ruff (format + lint), line-length 100
- Testes: pytest + pytest-asyncio

### TypeScript (frontend)

- Package manager: npm
- Componentes: React Server Components por padrão, "use client" apenas quando necessário (ex.: `ChatContainer`,
  `InputBar`, `SqlViewer`, `DataTable` — interativos, precisam de client)
- Estilo: Tailwind CSS puro (utility classes), sem CSS modules, sem kit de componentes
- Estado: React hooks locais (`useState`/`useCallback`) — sem lib de estado global; o chat inteiro vive no
  estado do `ChatContainer`
- Fetching: `fetch` nativo com parsing manual de SSE (`src/lib/api.ts`) para o chat — sem lib de streaming
  externa (nem Vercel AI SDK, nem EventSource — POST não é suportado pelo EventSource nativo)

### Ambos

- Sem código comentado em commits
- Sem `print()` / `console.log()` para debug — usar logging estruturado
- Nomes de variáveis e funções em inglês, documentação e comentários em português são aceitáveis
- Commits em português ou inglês, consistentes dentro de cada PR

## Arquitetura de agentes (LangGraph)

O pipeline é um grafo dirigido com os seguintes nós:

```
[schema_linker] → [subproblem_agent] → [query_planner] → [sql_generator] → [sql_validator] → [sql_executor]
                                                                                                     │
                                                                                              ┌──────┤
                                                                                              │ Erro │
                                                                                              └──┬───┘
                                                                                                 ▼
                                                                                        [correction_planner] → [correction_sql] → [sql_executor]
                                                                                                                                       │
                                                                                                                              (max 3 tentativas)
                                                                                                     │
                                                                                              ┌──────┤
                                                                                              │  OK  │
                                                                                              └──┬───┘
                                                                                                 ▼
                                                                                        [response_synthesizer]
```

Cada nó é um módulo em `app/agents/` com:
- Um prompt template dedicado
- Input/output tipados com Pydantic
- Configuração de qual LLM provider usar (Gemini, Groq, ou futuro OpenAI/Claude)

## Abstração de LLM providers

Toda chamada de LLM passa por `app/core/llm_provider.py` que expõe uma factory:

```python
from app.core.llm_provider import get_llm

llm = get_llm(provider="gemini")  # usa o default de app/core/llm_provider.py
# ou
llm = get_llm(provider="groq", model="algum-modelo-atual-do-groq")
# ou futuro
llm = get_llm(provider="openai", model="gpt-4o")
```

Cada agente declara no config qual provider/modelo usar. Trocar modelo = mudar config, não código.

## Segurança do banco de dados

Regras invioláveis:

1. **Read-only absoluto:** toda query gerada passa por validação antes de execução. Bloquear: INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, EXEC, CREATE, GRANT, REVOKE, CALL.
2. **Usuário de banco dedicado:** conexão ao banco de produção via usuário com `GRANT SELECT` apenas nas tabelas permitidas.
3. **Timeout:** queries com timeout de 30 segundos. Cancelar automaticamente.
4. **Limite de linhas:** resultados truncados em 500 linhas. Informar o usuário se truncado.
5. **Sem SQL dinâmico concatenado:** usar parameterized queries quando valores do usuário forem injetados.

## Camada de metadados (banco de metadados)

O banco de metadados (pgvector) armazena:

- **Tabelas de catálogo:** `tables`, `columns`, `relationships`, `synonyms`, `business_rules`, `enum_values`
- **Tabela de exemplos few-shot:** `synthetic_examples` (question_nl, query_sql, tables_used, embedding)
- **Tabela de embeddings:** `metadata_embeddings` (source_type, source_id, content_text, embedding)

A ingestão é feita via script offline (`scripts/ingest_metadata.py`) que:
1. Introspecciona o schema do banco de produção via `information_schema`
2. Enriquece com descrições, sinônimos e regras de negócio de um arquivo YAML
3. Gera embeddings via sentence-transformers
4. Persiste no pgvector

## Variáveis de ambiente

```env
# LLM Providers
GEMINI_API_KEY=
GROQ_API_KEY=

# Banco de produção (read-only)
PRODUCTION_DB_HOST=localhost
PRODUCTION_DB_PORT=5432
PRODUCTION_DB_NAME=production
PRODUCTION_DB_USER=querymind_readonly
PRODUCTION_DB_PASSWORD=

# Banco de metadados (pgvector)
METADATA_DB_HOST=localhost
METADATA_DB_PORT=5433
METADATA_DB_NAME=querymind_metadata
METADATA_DB_USER=querymind
METADATA_DB_PASSWORD=

# Embeddings
EMBEDDING_MODEL=intfloat/multilingual-e5-small
EMBEDDING_DIMENSIONS=384

# App
LOG_LEVEL=INFO
SQL_TIMEOUT_SECONDS=30
SQL_MAX_ROWS=500
CORRECTION_MAX_RETRIES=3

# Frontend (Fase 3)
FRONTEND_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## O que não fazer

- Nunca gerar ou executar SQL que não seja SELECT
- Nunca expor credenciais de banco no frontend ou em logs
- Nunca injetar o schema completo do banco no prompt — usar RAG
- Nunca concatenar valores do usuário diretamente em SQL
- Nunca usar `print()` — usar `logging` com nível adequado
- Nunca commitar API keys, mesmo de free tier
- Nunca ignorar erros de execução SQL — capturar, logar, retornar mensagem amigável
