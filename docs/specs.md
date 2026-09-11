# Fase 1 — Fundação: Projeto, Infraestrutura e Camada de Metadados

## Objetivo

Entregar a base completa do projeto: estrutura de pastas, containerização, banco de metadados com pgvector, script de ingestão de schema, enriquecimento com dicionário de dados, geração de embeddings e busca semântica funcional. Ao final desta fase, deve ser possível rodar um script que, dado um trecho de texto, retorne as tabelas e colunas mais relevantes do banco de produção.

---

## Entregáveis

### E1. Estrutura do projeto e configuração

**Criar a estrutura de diretórios:**

```
querymind/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app factory (minimal)
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py              # Pydantic Settings com variáveis de ambiente
│   │   │   ├── llm_provider.py        # Factory de LLM providers (Gemini, Groq, OpenAI)
│   │   │   └── logging.py             # Configuração de logging estruturado
│   │   ├── metadata/
│   │   │   ├── __init__.py
│   │   │   ├── models.py              # SQLAlchemy models do banco de metadados
│   │   │   ├── schemas.py             # Pydantic schemas para metadados
│   │   │   ├── repository.py          # CRUD e buscas no banco de metadados
│   │   │   ├── embeddings.py          # Geração e busca de embeddings
│   │   │   └── dictionary.py          # Dicionário de sinônimos e regras de negócio
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py          # Pool de conexões (metadados + produção)
│   │   │   └── introspector.py        # Extração de schema via information_schema
│   │   ├── agents/                    # Placeholder para Fase 2
│   │   │   └── __init__.py
│   │   ├── api/                       # Placeholder para Fase 3
│   │   │   └── __init__.py
│   │   └── export/                    # Placeholder para Fase 4
│   │       └── __init__.py
│   ├── scripts/
│   │   ├── ingest_metadata.py         # Script principal de ingestão
│   │   └── generate_synthetic.py      # Geração de pares (Q_NL, Q_SQL) — placeholder
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                # Fixtures compartilhadas
│   │   ├── test_introspector.py
│   │   ├── test_embeddings.py
│   │   └── test_repository.py
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .env.example
├── frontend/                          # Placeholder para Fase 3
│   └── .gitkeep
├── data/
│   └── dictionary.yaml               # Dicionário de dados enriquecido pelo usuário
├── docker-compose.yml
├── .env.example
├── .gitignore
├── CLAUDE.md
└── README.md
```

**Arquivos de configuração:**

`pyproject.toml` com dependências:
```toml
[project]
name = "querymind-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "pgvector>=0.3",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "sentence-transformers>=3.0",
    "langchain-core>=0.3",
    "langchain-google-genai>=2.0",
    "langchain-groq>=0.2",
    "pyyaml>=6.0",
    "structlog>=24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.8",
    "httpx>=0.27",
]
```

---

### E2. Docker Compose

`docker-compose.yml` com três serviços iniciais:

```yaml
services:
  metadata-db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: querymind_metadata
      POSTGRES_USER: querymind
      POSTGRES_PASSWORD: ${METADATA_DB_PASSWORD:-querymind_dev}
    ports:
      - "5433:5432"
    volumes:
      - metadata_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U querymind -d querymind_metadata"]
      interval: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      metadata-db:
        condition: service_healthy
    volumes:
      - ./backend:/app
      - ./data:/data

volumes:
  metadata_pgdata:
```

O banco de produção (PostgreSQL do usuário) não faz parte do Compose — a conexão é via variável de ambiente apontando para o host do usuário.

---

### E3. Banco de metadados — modelos SQLAlchemy

Criar em `app/metadata/models.py` as seguintes tabelas no banco de metadados (pgvector):

#### Tabela `tables`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | UUID, PK | Identificador |
| table_name | VARCHAR(255), UNIQUE, NOT NULL | Nome da tabela no banco de produção |
| schema_name | VARCHAR(100), default 'public' | Schema do PostgreSQL |
| description | TEXT | Descrição em linguagem natural (do dicionário) |
| row_count | INTEGER | Contagem aproximada de linhas |
| created_at | TIMESTAMP | Data de ingestão |

#### Tabela `columns`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | UUID, PK | Identificador |
| table_id | UUID, FK → tables.id | Tabela pai |
| column_name | VARCHAR(255), NOT NULL | Nome da coluna |
| data_type | VARCHAR(100) | Tipo de dado PostgreSQL |
| is_nullable | BOOLEAN | Aceita NULL |
| is_primary_key | BOOLEAN | É PK |
| is_foreign_key | BOOLEAN | É FK |
| description | TEXT | Descrição em linguagem natural |
| sample_values | JSONB | Array com até 5 valores de exemplo |

#### Tabela `relationships`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | UUID, PK | Identificador |
| source_table_id | UUID, FK → tables.id | Tabela de origem (FK) |
| target_table_id | UUID, FK → tables.id | Tabela referenciada (PK) |
| source_column | VARCHAR(255) | Coluna FK na tabela de origem |
| target_column | VARCHAR(255) | Coluna PK na tabela referenciada |
| constraint_name | VARCHAR(255) | Nome da constraint no banco |

#### Tabela `synonyms`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | UUID, PK | Identificador |
| entity_type | VARCHAR(20) | 'table' ou 'column' |
| entity_id | UUID | FK para tables.id ou columns.id |
| synonym | VARCHAR(255), NOT NULL | Termo alternativo que o usuário pode usar |
| language | VARCHAR(10), default 'pt-BR' | Idioma do sinônimo |

#### Tabela `business_rules`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | UUID, PK | Identificador |
| table_id | UUID, FK → tables.id, NULLABLE | Tabela relacionada (pode ser global) |
| rule_text | TEXT, NOT NULL | Regra em linguagem natural |
| rule_type | VARCHAR(50) | 'filter', 'join', 'aggregation', 'format', 'general' |

#### Tabela `enum_values`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | UUID, PK | Identificador |
| column_id | UUID, FK → columns.id | Coluna que contém o enum |
| stored_value | VARCHAR(255) | Valor armazenado no banco |
| display_label | VARCHAR(255) | Nome amigável para o usuário |
| description | TEXT | Explicação do significado |

#### Tabela `synthetic_examples`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | UUID, PK | Identificador |
| question_nl | TEXT, NOT NULL | Pergunta em linguagem natural |
| query_sql | TEXT, NOT NULL | Query SQL correspondente |
| tables_used | JSONB | Lista de tabelas usadas na query |
| difficulty | VARCHAR(20) | 'simple', 'medium', 'complex' |
| embedding | VECTOR(384) | Embedding da pergunta NL |

#### Tabela `metadata_embeddings`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | UUID, PK | Identificador |
| source_type | VARCHAR(20), NOT NULL | 'table', 'column', 'rule', 'example' |
| source_id | UUID, NOT NULL | ID da entidade de origem |
| content_text | TEXT, NOT NULL | Texto que foi vetorizado |
| embedding | VECTOR(384) | Vetor de embeddings |

**Índices obrigatórios:**
- `metadata_embeddings.embedding` — índice HNSW com operador cosine: `CREATE INDEX ON metadata_embeddings USING hnsw (embedding vector_cosine_ops)`
- `synthetic_examples.embedding` — mesmo tipo de índice
- `synonyms(entity_type, entity_id)` — índice composto
- `columns(table_id)` — índice para JOINs

---

### E4. Introspector de schema

Criar em `app/database/introspector.py` uma classe `SchemaIntrospector` que:

1. Conecta ao banco de **produção** (read-only) via asyncpg
2. Consulta `information_schema.tables` para listar tabelas do schema configurado
3. Consulta `information_schema.columns` para extrair colunas, tipos, nullable
4. Consulta `information_schema.table_constraints` + `information_schema.key_column_usage` + `information_schema.constraint_column_usage` para extrair PKs, FKs e relationships
5. Para cada coluna não-numérica com cardinalidade baixa (<50 valores distintos), extrai sample values via `SELECT DISTINCT ... LIMIT 5`
6. Para cada tabela, obtém `row_count` aproximado via `pg_class.reltuples`
7. Retorna estrutura tipada `list[TableMetadata]` com Pydantic

```python
class ColumnMetadata(BaseModel):
    column_name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    sample_values: list[str] = []

class RelationshipMetadata(BaseModel):
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    constraint_name: str

class TableMetadata(BaseModel):
    table_name: str
    schema_name: str
    row_count: int
    columns: list[ColumnMetadata]
    relationships: list[RelationshipMetadata]
```

---

### E5. Dicionário de dados enriquecido (YAML)

Criar `data/dictionary.yaml` como fonte de enriquecimento humano. O script de ingestão mescla os dados automáticos do introspector com este arquivo. Estrutura:

```yaml
tables:
  customers:
    description: "Cadastro de clientes ativos e inativos da empresa"
    synonyms: ["clientes", "consumidores", "compradores"]
    columns:
      id:
        description: "Identificador único do cliente"
      name:
        description: "Nome completo do cliente"
        synonyms: ["nome", "nome do cliente", "razão social"]
      status:
        description: "Status atual do cadastro"
        synonyms: ["situação", "estado"]
        enum_values:
          active: { label: "Ativo", description: "Cliente com cadastro válido" }
          inactive: { label: "Inativo", description: "Cliente desativado" }
          suspended: { label: "Suspenso", description: "Cliente temporariamente bloqueado" }

  orders:
    description: "Pedidos realizados pelos clientes"
    synonyms: ["pedidos", "compras", "ordens"]
    columns:
      total_amount:
        description: "Valor total do pedido em reais"
        synonyms: ["valor", "total", "montante"]

business_rules:
  - table: orders
    type: filter
    text: "Quando o usuário perguntar sobre 'pedidos recentes', considerar os últimos 30 dias (WHERE created_at >= CURRENT_DATE - INTERVAL '30 days')"
  - table: null
    type: general
    text: "Valores monetários estão em BRL (reais). Formatar com duas casas decimais."
```

O usuário preenche este arquivo para seu banco real. O script de ingestão lê e enriquece os metadados do introspector.

---

### E6. Geração e busca de embeddings

Criar em `app/metadata/embeddings.py`:

#### Classe `EmbeddingService`

```python
class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Carrega modelo sentence-transformers. Roda em CPU."""

    def generate(self, texts: list[str]) -> list[list[float]]:
        """Gera embeddings para uma lista de textos."""

    async def search(
        self,
        query: str,
        source_types: list[str] | None = None,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """
        Busca os top_k metadados mais similares à query.
        Usa pgvector com operador <=> (cosine distance).
        Filtra por source_type se especificado.
        """
```

**Texto vetorizado por tipo:**

- **Tabela:** `"Tabela {table_name}: {description}. Colunas: {col1} ({type1}), {col2} ({type2}), ..."`
- **Coluna:** `"Coluna {table_name}.{column_name} ({data_type}): {description}. Sinônimos: {syn1}, {syn2}. Valores possíveis: {val1}, {val2}"`
- **Regra de negócio:** `"Regra para {table_name}: {rule_text}"`
- **Exemplo few-shot:** texto da `question_nl` diretamente

Isso garante que buscas semânticas como "qual o valor total dos pedidos" retornem tanto a coluna `orders.total_amount` quanto a regra de formatação de valores monetários.

---

### E7. Script de ingestão (`scripts/ingest_metadata.py`)

Script CLI que orquestra toda a ingestão. Fluxo:

```
1. Conectar ao banco de produção
2. Rodar SchemaIntrospector → obter TableMetadata[]
3. Carregar data/dictionary.yaml
4. Mesclar: para cada tabela/coluna do introspector, enriquecer com description, synonyms, enum_values do YAML
5. Persistir no banco de metadados:
   a. Inserir/atualizar tabelas em `tables`
   b. Inserir/atualizar colunas em `columns`
   c. Inserir relationships
   d. Inserir synonyms
   e. Inserir business_rules
   f. Inserir enum_values
6. Gerar embeddings para todos os registros
7. Persistir embeddings em `metadata_embeddings`
8. Criar índices HNSW se não existirem
9. Logar estatísticas: X tabelas, Y colunas, Z sinônimos, W embeddings gerados
```

Comportamento:
- Idempotente: pode rodar múltiplas vezes sem duplicar dados (upsert por table_name + column_name)
- Incremental: detectar tabelas/colunas removidas e marcar (não deletar)
- Tempo esperado: <60 segundos para 30 tabelas em CPU

---

### E8. Abstração de LLM provider

Criar em `app/core/llm_provider.py`:

```python
from langchain_core.language_models import BaseChatModel

def get_llm(
    provider: str = "gemini",
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> BaseChatModel:
    """
    Factory que retorna o ChatModel do LangChain para o provider solicitado.

    Providers suportados:
    - "gemini": ChatGoogleGenerativeAI (default: gemini-2.5-flash)
    - "groq": ChatGroq (default: llama-3.3-70b-versatile)
    - "openai": ChatOpenAI (default: gpt-4o) — futuro
    - "anthropic": ChatAnthropic (default: claude-sonnet-4-20250514) — futuro

    API keys vêm das variáveis de ambiente.
    """
```

Cada agente (Fase 2) declarará qual provider/modelo usa via config, permitindo setup híbrido (Gemini para raciocínio, Groq para correção).

---

### E9. Testes

Testes mínimos obrigatórios para a Fase 1:

| Arquivo | O que testa |
|---|---|
| `test_introspector.py` | `SchemaIntrospector` contra um banco de teste (fixture com tabelas mínimas) |
| `test_embeddings.py` | `EmbeddingService.generate()` retorna vetores de dimensão correta; `search()` retorna resultados ordenados por similaridade |
| `test_repository.py` | CRUD de metadados: inserir tabela, coluna, sinônimo; consultar com filtros |
| `conftest.py` | Fixture que sobe banco PostgreSQL de teste (usar `testcontainers-python` ou banco do Compose) |

---

## Critérios de aceite

A Fase 1 está completa quando:

1. `docker compose up -d` sobe o banco de metadados pgvector sem erros
2. `scripts/ingest_metadata.py` conecta ao banco de produção, extrai schema, mescla com dictionary.yaml, gera embeddings e persiste tudo no banco de metadados
3. Uma busca por similaridade semântica como `"valor total dos pedidos do mês"` retorna as colunas/tabelas/regras relevantes do banco de produção
4. `get_llm("gemini")` e `get_llm("groq")` retornam instâncias válidas do LangChain
5. Todos os testes passam
6. O código segue as convenções do CLAUDE.md: tipagem forte, async, logging estruturado, sem secrets hardcoded

---

## Decisões técnicas para esta fase

**pgvector vs Qdrant/ChromaDB:** pgvector foi escolhido porque o projeto já usa PostgreSQL. Para 30 tabelas, o volume de vetores (estimado 1-5K) é trivial. Índice HNSW com cosine distance é suficiente. Se escalar acima de 100K vetores, reavaliar Qdrant.

**all-MiniLM-L6-v2 vs modelos maiores:** modelo de 80MB, 384 dimensões, roda em CPU em ~10-50ms por texto. Para metadados curtos (nomes de tabelas, descrições), a qualidade é comparável a modelos maiores. Se necessário, trocar para `BAAI/bge-small-en-v1.5` (mesma faixa de tamanho, ligeiramente melhor em retrieval benchmarks).

**YAML para dicionário vs tabela editável:** YAML é versionável no git, editável com qualquer editor, e basta rodar o script de ingestão para aplicar mudanças. Na Fase 3, podemos adicionar uma interface web para editar o dicionário, mas o YAML permanece como source of truth.

**Upsert na ingestão:** usar `INSERT ... ON CONFLICT (table_name) DO UPDATE` para garantir idempotência. Permite re-rodar o script quantas vezes necessário durante o desenvolvimento sem limpar o banco manualmente.
