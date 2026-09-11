# Inquiro — Text-to-SQL Inteligente com RAG e Agentes

Plataforma corporativa que transforma perguntas em linguagem natural em consultas SQL precisas, executando-as de forma segura e retornando respostas executivas com suporte a gráficos e relatórios.

## Visão geral

```
Pergunta NL → RAG de Metadados → Agentes Multi-Etapa → SQL Seguro → Resposta NL + Dados
```

O sistema combina duas abordagens acadêmicas:

- **Camada de metadados (DANKE-inspired):** dicionário de sinônimos, knowledge graph do schema, dataset sintético few-shot e view synthesis para abstrair JOINs — garantindo que a LLM receba apenas o contexto relevante, mesmo em bases grandes.
- **Pipeline multi-agente (SQL-of-Thought):** decomposição em agentes especializados (Schema Linking → Subproblem → Query Plan com CoT → SQL Generation) com loop de correção guiado por taxonomia de 31 tipos de erros SQL.

## Stack tecnológica

| Camada | Tecnologia | Papel |
|---|---|---|
| LLM primário | Gemini 3.6 Flash (free tier) | Geração SQL, síntese, schema linking |
| LLM secundário | Groq — `openai/gpt-oss-120b` (free tier) | Correction loop (diagnóstico + regeneração de SQL) |
| Embeddings | sentence-transformers — `intfloat/multilingual-e5-small` (CPU) | Vetorização multilíngue (PT-BR) de metadados para RAG |
| Orquestração | LangGraph + LangChain | Grafo de agentes com estado e loops |
| Vector store | PostgreSQL + pgvector | Busca semântica sobre metadados |
| Banco alvo | PostgreSQL | Banco de produção consultado (read-only) |
| Backend | Python 3.12 + FastAPI | API REST + streaming SSE |
| Frontend | Next.js (App Router) + TypeScript + Tailwind | Interface de chat com streaming, sem libs de UI/estado externas |
| Relatórios | python-docx, WeasyPrint, Jinja2, matplotlib | Exportação .docx e .pdf, com gráficos SVG embutidos (Fase 4) |
| Gráficos | Recharts | Visualização interativa inline no chat (Fase 4) |
| Infra | Docker Compose | Conteinerização de todos os serviços |

## Estrutura do projeto

```
inquiro/
├── backend/                  # FastAPI + LangGraph agents
│   ├── app/
│   │   ├── agents/           # Grafo LangGraph: 9 nós (schema_linker → ... → response_synthesizer)
│   │   ├── api/               # routes.py (POST /api/chat SSE, GET /api/health), streaming.py, dependencies.py
│   │   ├── core/              # Config, LLM provider abstraction, logging
│   │   ├── metadata/          # Ingestão de metadados, dicionário, embeddings
│   │   ├── database/          # Conexão, introspecção de schema
│   │   ├── export/            # Classificador de output, geração de gráfico/docx/pdf (Fase 4)
│   │   └── main.py
│   ├── scripts/               # Ingestão, teste manual do pipeline (test_pipeline.py)
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                  # Next.js (App Router) — chat UI
│   ├── src/
│   │   ├── app/                # layout.tsx, page.tsx, globals.css
│   │   ├── components/
│   │   │   ├── chat/            # ChatContainer, MessageList, MessageBubble, InputBar, StatusIndicator
│   │   │   ├── data/             # DataTable, SqlViewer, ChartRenderer, ExportButtons (Fase 4)
│   │   │   └── ui/                # LoadingDots
│   │   └── lib/                 # api.ts (cliente SSE manual), types.ts
│   ├── package.json
│   └── Dockerfile
├── database/                  # DDL e seed do banco de produção de exemplo (SeguraPro)
│   ├── init-schema.sql
│   └── seed-data.sql
├── data/
│   └── dictionary.yaml        # Dicionário de dados enriquecido (descrições, sinônimos, business rules)
├── docs/                      # Documentação e specs (specs.md, specs-fase2.md, specs-fase3.md)
├── docker-compose.yml
├── CLAUDE.md
└── README.md
```

O `docker-compose.yml` sobe quatro serviços: `production-db` (o banco de produção, seedado a partir de `database/`), `metadata-db` (pgvector), `backend` e `frontend`.

## Pré-requisitos

- Docker e Docker Compose (o `docker compose up -d` já sobe production-db + metadata-db com pgvector — não precisa instalar Postgres localmente)
- Python 3.12+ e [uv](https://docs.astral.sh/uv/) (para rodar fora do container)
- Node.js 20+
- Chave de API gratuita: [Google AI Studio](https://aistudio.google.com/apikey) (Gemini)
- Chave de API gratuita: [Groq Console](https://console.groq.com)

> Os nomes de modelo em `app/core/llm_provider.py` e `app/agents/config.py` (`AGENT_LLM_CONFIG`) podem ficar
> desatualizados com o tempo — providers de LLM depreciam modelos com frequência. Se a ingestão/pipeline
> falhar com erro `404`/`model_not_found`, confira o nome do modelo atual na documentação do provider.

## Setup rápido

```bash
# 1. Clonar e configurar variáveis
cp .env.example .env
# Editar .env com as API keys

# 2. Subir todos os serviços
docker compose up -d

# 3. Rodar ingestão de metadados (primeira vez, e sempre que o schema/dictionary.yaml mudar)
docker compose exec backend uv run python -m scripts.ingest_metadata

# 4. Acessar
# Frontend (chat): http://localhost:3000
# Backend API: http://localhost:8000/docs
# Healthcheck: http://localhost:8000/api/health

# Opcional — testar o pipeline direto via script, sem passar pela API/UI:
docker compose exec backend uv run python -m scripts.test_pipeline
```

> Se só o `build.args` do `frontend` mudar no `docker-compose.yml` (ex.: trocar `NEXT_PUBLIC_API_URL`),
> o `docker compose up -d` sozinho **não** rebuilda a imagem automaticamente — rode
> `docker compose build frontend` (ou `up -d --build`) explicitamente, senão o bundle antigo continua
> servido mesmo com a variável "atualizada".
>
> Para rodar o frontend fora do Docker (`cd frontend && npm run dev`), crie um `frontend/.env.local` com
> `NEXT_PUBLIC_API_URL=http://localhost:8000` — em dev local essa variável não vem do Dockerfile.

## Banco de exemplo (SeguraPro)

Para desenvolvimento e testes, o `production-db` já sobe seedado com o schema de uma corretora de seguros fictícia (`database/init-schema.sql` + `database/seed-data.sql`): 15 tabelas (clientes, apólices, sinistros, comissões, cotações etc.), com o usuário `segurapro_readonly` (apenas `GRANT SELECT`) já configurado. O `data/dictionary.yaml` traz as descrições, sinônimos em PT-BR e business rules desse domínio. Para plugar seu próprio banco de produção, troque `database/*.sql` e `data/dictionary.yaml` pelos do seu domínio e rode a ingestão de novo.

## Pipeline de agentes (Fase 2)

`app/agents/pipeline.py` expõe `Pipeline().run(pergunta)`, que roda o grafo LangGraph completo: Schema Linker
(matching no dicionário + RAG vetorial + confirmação via LLM) → Subproblem Agent → Query Plan (CoT) → SQL
Generator → SQL Validator (código puro — blocklist, CTEs, tabelas existentes) → SQL Executor → Response
Synthesizer, com um correction loop (até `CORRECTION_MAX_RETRIES` tentativas) quando a validação ou execução
falha. Detalhes completos em `docs/specs-fase2.md`. `scripts/test_pipeline.py` roda 10 perguntas de teste do
domínio SeguraPro e imprime tabelas selecionadas, SQL gerado, tentativas de correção e resposta final.

## API e chat streaming (Fase 3)

`POST /api/chat` recebe `{"question": "..."}` e retorna um stream SSE (`text/event-stream`) — eventos
`status` (progresso por etapa do grafo), `sql` (query gerada), `columns`/`rows`/`metadata` (resultado da
execução), `answer` (resposta final, token a token) e `done`/`error`. O streaming usa
`graph.astream(state, stream_mode=["updates", "messages"])` do LangGraph: `"updates"` dá o delta de cada nó
completado, `"messages"` dá os chunks de qualquer chamada LLM dentro do grafo — filtrado para só repassar
tokens do nó `response_synthesizer` no evento `answer` (os demais nós também emitem chunks reais via
`ainvoke()`, sem precisar de `.astream()` explícito nos nós). `GET /api/health` confere conectividade real com
`production-db` e `metadata-db`. O frontend (`src/lib/api.ts`) parseia o SSE manualmente via
`fetch` + `ReadableStream`, sem lib externa. Detalhes completos em `docs/specs-fase3.md`.

## Gráficos e exportação .docx/.pdf (Fase 4)

Depois que o `sql_executor` retorna dados, `app/export/classifier.py` classifica a pergunta original em
`TEXT` | `CHART` | `DOCX` | `PDF` por palavras-chave (prioridade `DOCX > PDF > CHART > TEXT`; só dispara se
a execução teve sucesso e retornou ao menos uma linha). Para `CHART`, `app/export/chart_generator.py` pede a
uma LLM (Gemini, fora do grafo LangGraph) um `ChartSpec` estruturado (tipo de gráfico, séries, eixos), com
fallback para uma heurística pura se a LLM falhar, e emite um evento SSE `chart` renderizado no frontend via
Recharts (`ChartRenderer.tsx`). Para `DOCX`/`PDF`, o backend só avisa o frontend (`export_ready`) que pode
disparar o download automático — a geração de fato acontece sob demanda em `POST /api/export`, tanto para
esse auto-download quanto para os botões manuais "Baixar Word"/"Baixar PDF" que aparecem embaixo de qualquer
resposta com dados.

Um ponto de atenção resolvido nesta fase: valores `Decimal`/`date` do Postgres perdem o tipo original ao
virar JSON no SSE (`Decimal` vira `float`, `date` vira string ISO), então não dá pra confiar em re-inferir
formatação a partir do payload já degradado no frontend. A formatação de cada coluna
(`CURRENCY`/`INTEGER`/`DECIMAL_NUMBER`/`DATE`/`DATETIME`/`TEXT`) é calculada uma única vez em
`app/export/formatting.py`, logo após a execução SQL (quando os tipos Python originais do `asyncpg` ainda
existem), e propagada como metadado explícito (`columnFormats`) pelo SSE, pelo estado do frontend e de volta
no corpo de `POST /api/export` — nunca recalculada a partir do JSON já serializado. Colunas `DECIMAL` que
representam taxas (ex.: `commission_rate`, sufixo `_rate`/`_pct`/`_percent`) são deliberadamente excluídas da
formatação `CURRENCY`.

`POST /api/export` recebe pergunta, SQL, colunas/linhas, `column_formats` e (opcionalmente) o `chart_spec` já
usado no chat, e devolve o arquivo pronto (`FileResponse`); a limpeza de arquivos temporários com mais de 1h
roda via `BackgroundTasks` depois da resposta ser enviada, sem bloquear o request. Detalhes completos em
`docs/specs-fase4.md`.

## Fases de implementação

| Fase | Escopo | Status |
|---|---|---|
| 1 | Fundação: projeto, Docker, banco de metadados, ingestão, vector store | ✅ Concluída |
| 2 | Pipeline de agentes LangGraph + execução SQL segura | ✅ Concluída |
| 3 | API FastAPI + frontend Next.js com chat streaming | ✅ Concluída |
| 4 | Outputs multimodais: gráficos, .docx, .pdf | ✅ Concluída |

## Referências acadêmicas

- **SQL-of-Thought** (Chaturvedi et al., 2025) — Multi-agentic Text-to-SQL with Guided Error Correction. [arXiv:2509.00581v2](https://arxiv.org/abs/2509.00581v2)
- **DANKE / Nascimento et al.** (Data & Knowledge Engineering, 2026) — LLM-based strategy for real-world text-to-SQL leveraging knowledge graphs and dynamic few-shot examples.

## Licença

MIT