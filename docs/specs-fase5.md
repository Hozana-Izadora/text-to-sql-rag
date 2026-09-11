# Fase 5 — Plataforma Dinâmica: Conexão a Qualquer Banco via Frontend

## Objetivo

Transformar o QueryMind de um sistema acoplado a um banco específico (SeguraPro) em uma plataforma onde o usuário conecta qualquer banco de dados pela interface, o sistema introspecta o schema automaticamente, e o usuário enriquece os metadados (descrições, sinônimos, regras) pelo frontend — sem tocar em YAML, SQL ou terminal.

Ao final desta fase:
- O usuário abre o QueryMind, clica "Nova Conexão", preenche host/porta/banco/usuário/senha
- O sistema testa a conexão, introspecta o schema, gera embeddings
- O usuário vê a lista de tabelas/colunas e pode adicionar descrições, sinônimos e regras pelo frontend
- O chat funciona com qualquer banco conectado — o usuário escolhe qual banco consultar

---

## Visão geral da nova arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│                                                              │
│  ┌─────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │  Conexões   │  │  Editor de       │  │  Chat           │  │
│  │  (CRUD)     │  │  Metadados       │  │  (por conexão)  │  │
│  └──────┬──────┘  └────────┬─────────┘  └────────┬────────┘  │
└─────────┼──────────────────┼──────────────────────┼──────────┘
          │                  │                      │
          ▼                  ▼                      ▼
┌──────────────────────────────────────────────────────────────┐
│                      Backend API                             │
│                                                              │
│  /api/connections    /api/metadata      /api/chat            │
│  CRUD + test         tabelas, colunas   pipeline por conexão │
│  + introspect        sinônimos, regras                       │
└──────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────┐
│  Banco de metadados (pgvector)                               │
│                                                              │
│  connections ──→ tables ──→ columns ──→ synonyms             │
│       │                                                      │
│       └──→ business_rules, enum_values, embeddings           │
└──────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Banco do        │ │ Banco do        │ │ Banco do        │
│ usuário A       │ │ usuário B       │ │ usuário C       │
│ (PostgreSQL)    │ │ (MySQL)         │ │ (SQL Server)    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

---

## Entregáveis

### E1. Tabela `connections` no banco de metadados

Adicionar em `app/metadata/models.py`:

```
Tabela: connections
├── id              UUID, PK
├── name            VARCHAR(100) NOT NULL          — nome amigável ("Produção SeguraPro")
├── db_type         VARCHAR(20) NOT NULL           — postgresql, mysql, sqlserver, oracle, sqlite
├── host            VARCHAR(255) NOT NULL
├── port            INTEGER NOT NULL
├── database_name   VARCHAR(100) NOT NULL
├── username        VARCHAR(100) NOT NULL
├── password_encrypted  TEXT NOT NULL              — criptografado com Fernet
├── ssl_enabled     BOOLEAN DEFAULT false
├── is_active       BOOLEAN DEFAULT true
├── schema_name     VARCHAR(100) DEFAULT 'public'  — schema do banco (para PostgreSQL)
├── last_introspected_at  TIMESTAMP               — quando foi introspectado pela última vez
├── table_count     INTEGER                        — cache da contagem de tabelas
├── created_at      TIMESTAMP DEFAULT NOW()
├── updated_at      TIMESTAMP DEFAULT NOW()
```

**Todas as tabelas existentes (tables, columns, synonyms, etc.) ganham uma FK `connection_id`:**

```sql
ALTER TABLE tables ADD COLUMN connection_id UUID NOT NULL REFERENCES connections(id) ON DELETE CASCADE;
ALTER TABLE business_rules ADD COLUMN connection_id UUID REFERENCES connections(id) ON DELETE CASCADE;
ALTER TABLE metadata_embeddings ADD COLUMN connection_id UUID NOT NULL REFERENCES connections(id) ON DELETE CASCADE;
ALTER TABLE synthetic_examples ADD COLUMN connection_id UUID REFERENCES connections(id) ON DELETE CASCADE;
```

O `ON DELETE CASCADE` garante que ao remover uma conexão, todos os metadados associados são limpos.

---

### E2. Criptografia de senhas

Criar em `app/core/encryption.py`:

Senhas de banco nunca são armazenadas em texto plano. Usar Fernet (criptografia simétrica) com chave derivada de uma variável de ambiente.

```python
from cryptography.fernet import Fernet

class CredentialEncryptor:
    def __init__(self, secret_key: str):
        """
        Deriva chave Fernet a partir de ENCRYPTION_SECRET_KEY do .env.
        Se a variável não existir, gerar uma e avisar o usuário.
        """

    def encrypt(self, plaintext: str) -> str:
        """Retorna string base64 criptografada."""

    def decrypt(self, ciphertext: str) -> str:
        """Retorna senha original."""
```

Adicionar ao `.env.example`:
```env
ENCRYPTION_SECRET_KEY=   # Gerar com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

### E3. Suporte multi-banco no introspector

Refatorar `app/database/introspector.py`:

O introspector atual só funciona com PostgreSQL. Precisa suportar múltiplos bancos.

```python
class BaseIntrospector(ABC):
    """Interface comum para todos os introspectors."""

    @abstractmethod
    async def introspect(self) -> list[TableMetadata]:
        """Extrai schema completo do banco."""

    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """Testa se a conexão funciona e retorna info básica."""

class PostgresIntrospector(BaseIntrospector):
    """Introspector existente, refatorado para herdar de Base."""

class MySQLIntrospector(BaseIntrospector):
    """
    Usa information_schema do MySQL.
    Diferenças:
    - Sem schema_name (MySQL usa database_name)
    - PKs via SHOW INDEX ou information_schema.TABLE_CONSTRAINTS
    - FKs via information_schema.KEY_COLUMN_USAGE
    - row_count via information_schema.TABLES.TABLE_ROWS
    - Driver: aiomysql
    """

class SQLServerIntrospector(BaseIntrospector):
    """
    Usa sys.tables, sys.columns, sys.foreign_keys do SQL Server.
    Diferenças:
    - Schema padrão é 'dbo', não 'public'
    - Tipos de dados diferentes (NVARCHAR, BIT, MONEY, DATETIME2)
    - Driver: aioodbc
    """

class OracleIntrospector(BaseIntrospector):
    """
    Usa ALL_TABLES, ALL_TAB_COLUMNS, ALL_CONSTRAINTS do Oracle.
    Diferenças:
    - Sem schema_name — usa owner
    - row_count via ALL_TABLES.NUM_ROWS (após ANALYZE)
    - Driver: oracledb (async)
    """

def get_introspector(connection: Connection) -> BaseIntrospector:
    """Factory que retorna o introspector correto para o db_type."""
```

**Drivers adicionais no pyproject.toml:**
```toml
"aiomysql>=0.2",        # MySQL
"aioodbc>=0.5",         # SQL Server (via ODBC)
"oracledb>=2.0",        # Oracle
```

**Nota:** os drivers são opcionais. Instalar apenas os necessários:
```toml
[project.optional-dependencies]
mysql = ["aiomysql>=0.2"]
sqlserver = ["aioodbc>=0.5"]
oracle = ["oracledb>=2.0"]
```

---

### E4. API de conexões

Criar em `app/api/connections.py`:

```python
router = APIRouter(prefix="/api/connections")

@router.get("/")
async def list_connections() -> list[ConnectionResponse]:
    """Lista todas as conexões (sem expor senhas)."""

@router.post("/")
async def create_connection(request: ConnectionCreate) -> ConnectionResponse:
    """
    1. Validar campos obrigatórios
    2. Criptografar senha
    3. Testar conexão (get_introspector → test_connection)
    4. Se teste OK, salvar no banco de metadados
    5. Disparar introspection assíncrona (background task)
    6. Retornar conexão criada
    """

@router.get("/{connection_id}")
async def get_connection(connection_id: UUID) -> ConnectionDetailResponse:
    """Retorna detalhes da conexão + contagem de tabelas/colunas."""

@router.put("/{connection_id}")
async def update_connection(connection_id: UUID, request: ConnectionUpdate) -> ConnectionResponse:
    """Atualiza campos da conexão. Se credenciais mudaram, re-testar."""

@router.delete("/{connection_id}")
async def delete_connection(connection_id: UUID):
    """Remove conexão + todos os metadados associados (CASCADE)."""

@router.post("/{connection_id}/test")
async def test_connection(connection_id: UUID) -> ConnectionTestResult:
    """Testa conexão existente. Retorna sucesso/erro + versão do banco."""

@router.post("/{connection_id}/introspect")
async def introspect_connection(connection_id: UUID) -> IntrospectionResult:
    """
    Re-introspecta o schema do banco:
    1. Rodar introspector
    2. Upsert tabelas e colunas no banco de metadados
    3. Gerar embeddings para novos metadados
    4. Retornar estatísticas (tabelas, colunas, FKs)
    """
```

**Schemas:**
```python
class ConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    db_type: Literal["postgresql", "mysql", "sqlserver", "oracle", "sqlite"]
    host: str
    port: int = Field(..., gt=0, le=65535)
    database_name: str
    username: str
    password: str                  # texto plano — será criptografado antes de salvar
    ssl_enabled: bool = False
    schema_name: str = "public"

class ConnectionResponse(BaseModel):
    id: UUID
    name: str
    db_type: str
    host: str
    port: int
    database_name: str
    username: str
    # SEM campo password
    ssl_enabled: bool
    schema_name: str
    is_active: bool
    table_count: int | None
    last_introspected_at: datetime | None
    created_at: datetime

class ConnectionTestResult(BaseModel):
    success: bool
    message: str               # "Conexão OK" ou mensagem de erro
    db_version: str | None     # "PostgreSQL 16.2"
    latency_ms: int | None     # tempo de resposta
```

---

### E5. API de metadados editáveis

Criar em `app/api/metadata.py`:

```python
router = APIRouter(prefix="/api/connections/{connection_id}/metadata")

@router.get("/tables")
async def list_tables(connection_id: UUID) -> list[TableDetailResponse]:
    """
    Lista tabelas da conexão com:
    - Colunas (nome, tipo, nullable, PK, FK)
    - Descrição (editável)
    - Sinônimos (editáveis)
    - row_count
    """

@router.put("/tables/{table_id}")
async def update_table(table_id: UUID, request: TableUpdate):
    """Atualiza descrição da tabela. Regenera embedding."""

@router.put("/columns/{column_id}")
async def update_column(column_id: UUID, request: ColumnUpdate):
    """Atualiza descrição da coluna. Regenera embedding."""

@router.post("/tables/{table_id}/synonyms")
async def add_synonym(table_id: UUID, request: SynonymCreate):
    """Adiciona sinônimo para tabela ou coluna."""

@router.delete("/synonyms/{synonym_id}")
async def remove_synonym(synonym_id: UUID):
    """Remove sinônimo."""

@router.get("/business-rules")
async def list_rules(connection_id: UUID) -> list[BusinessRuleResponse]:
    """Lista regras de negócio da conexão."""

@router.post("/business-rules")
async def create_rule(connection_id: UUID, request: BusinessRuleCreate):
    """Cria regra de negócio. Gera embedding."""

@router.put("/business-rules/{rule_id}")
async def update_rule(rule_id: UUID, request: BusinessRuleUpdate):
    """Atualiza regra. Regenera embedding."""

@router.delete("/business-rules/{rule_id}")
async def delete_rule(rule_id: UUID):
    """Remove regra e embedding associado."""

@router.post("/enum-values")
async def add_enum_value(request: EnumValueCreate):
    """Adiciona mapeamento de valor armazenado → label amigável."""

@router.delete("/enum-values/{enum_id}")
async def remove_enum_value(enum_id: UUID):
    """Remove enum value."""
```

**Schemas de update:**
```python
class TableUpdate(BaseModel):
    description: str | None = None

class ColumnUpdate(BaseModel):
    description: str | None = None

class SynonymCreate(BaseModel):
    entity_type: Literal["table", "column"]
    entity_id: UUID
    synonym: str
    language: str = "pt-BR"

class BusinessRuleCreate(BaseModel):
    table_id: UUID | None = None     # null = regra global
    rule_text: str
    rule_type: Literal["filter", "join", "aggregation", "format", "general"]

class EnumValueCreate(BaseModel):
    column_id: UUID
    stored_value: str
    display_label: str
    description: str | None = None
```

**Comportamento importante:** toda vez que o usuário edita uma descrição, sinônimo ou regra, o sistema regenera o embedding correspondente automaticamente. O usuário não precisa saber que embeddings existem.

---

### E6. Adaptação do pipeline para multi-conexão

Atualizar `app/agents/pipeline.py` e `app/api/routes.py`:

O chat agora recebe um `connection_id` junto com a pergunta:

```python
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    connection_id: UUID          # NOVO — qual banco consultar
```

O pipeline usa o `connection_id` para:
1. Buscar metadados/embeddings/sinônimos apenas daquela conexão
2. Conectar ao banco correto (descriptografar senha, instanciar driver)
3. Executar SQL no banco do usuário

Atualizar `EmbeddingService.search()`:
```python
async def search(self, query: str, connection_id: UUID, ...) -> list[SearchResult]:
    # Filtrar por connection_id na tabela metadata_embeddings
```

Atualizar `MetadataRepository` — todos os métodos recebem `connection_id`.

Atualizar `SQLExecutor` — recebe a `Connection` e instancia o driver correto.

---

### E7. Geração de SQL dialeto-específico

Atualizar `app/agents/sql_generator.py`:

O prompt do SQL Generator precisa informar o dialeto:

```
Você é um gerador de SQL {dialect}. ...
```

Diferenças entre dialetos que o prompt deve considerar:

| Aspecto | PostgreSQL | MySQL | SQL Server |
|---|---|---|---|
| Limitar linhas | `LIMIT N` | `LIMIT N` | `TOP N` |
| String concat | `\|\|` | `CONCAT()` | `+` |
| Data atual | `CURRENT_DATE` | `CURDATE()` | `GETDATE()` |
| Booleano | `true/false` | `1/0` | `1/0` |
| Case-sensitive | Sim (padrão) | Não (padrão) | Depende do collation |
| Escape identifiers | `"nome"` | `` `nome` `` | `[nome]` |

Atualizar o `schema_context` para indicar o dialeto e incluir as particularidades no prompt.

Atualizar o `SQL Validator` para aceitar `TOP N` como válido em SQL Server.

---

### E8. Frontend — Página de conexões

Criar em `src/app/connections/page.tsx`:

Página que lista as conexões e permite criar/editar/remover.

**Layout:**

```
┌──────────────────────────────────────────────────────────┐
│  QueryMind                           [+ Nova Conexão]    │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ 🐘 Produção SeguraPro                              │  │
│  │ PostgreSQL · localhost:5432 · segurapro            │  │
│  │ 15 tabelas · 138 colunas · Última sync: há 2h      │  │
│  │                                                    │  │
│  │ [Editar metadados]  [Re-introspect]  [Remover]     │  │
│  │ [Abrir chat →]                                     │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ 🐬 ERP Financeiro                                  │  │
│  │ MySQL · 192.168.1.50:3306 · erp_prod               │  │
│  │ 42 tabelas · 310 colunas · Última sync: há 1 dia   │  │
│  │                                                    │  │
│  │ [Editar metadados]  [Re-introspect]  [Remover]     │  │
│  │ [Abrir chat →]                                     │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**Ícones por db_type:**
- PostgreSQL: 🐘
- MySQL: 🐬
- SQL Server: 🪟
- Oracle: 🔴
- SQLite: 📄

---

### E9. Frontend — Modal de nova conexão

Criar em `src/components/connections/ConnectionModal.tsx`:

Modal/dialog com formulário para criar ou editar uma conexão.

**Campos do formulário:**
- Nome da conexão (texto livre)
- Tipo de banco (select: PostgreSQL, MySQL, SQL Server, Oracle, SQLite)
- Host
- Porta (pré-preenchida conforme o tipo: 5432, 3306, 1433, 1521)
- Nome do banco de dados
- Schema (apenas para PostgreSQL, default "public")
- Usuário
- Senha (campo password)
- SSL (checkbox)

**Botão "Testar conexão":**
- Chama POST `/api/connections/{id}/test` (ou testa antes de salvar)
- Mostra resultado inline: ✅ "Conexão OK — PostgreSQL 16.2 (latência: 12ms)" ou ❌ "Erro: connection refused"

**Botão "Salvar e introspeccionar":**
- Salva a conexão
- Dispara introspection
- Mostra progresso: "Introspectando... 15 tabelas encontradas, gerando embeddings..."
- Ao completar, redireciona para a página de edição de metadados

---

### E10. Frontend — Editor de metadados

Criar em `src/app/connections/[id]/metadata/page.tsx`:

Interface para o usuário enriquecer os metadados do banco conectado.

**Layout:**

```
┌──────────────────────────────────────────────────────────┐
│  ← Voltar    Produção SeguraPro    [Re-introspect]       │
├────────────────┬─────────────────────────────────────────┤
│                │                                         │
│  Tabelas       │  policies (Apólices de seguro)   [✏️]   │
│  ─────────     │                                         │
│  > departments │  Sinônimos: apólices, contratos   [+]   │
│  > brokers     │                                         │
│  > clients     │  Colunas:                               │
│  ▶ policies    │  ┌────────────────────────────────────┐ │
│  > claims      │  │ premium_amount  DECIMAL(12,2)      │ │
│  > commissions │  │ "Valor total do prêmio"      [✏️]  │ │
│  > payments    │  │ Sinônimos: prêmio, valor  [+]      │ │
│  > ...         │  │                                    │ │
│                │  │ status  VARCHAR(20)                │ │
│                │  │ "Status da apólice"           [✏️] │ │
│                │  │ Valores:                           │ │
│                │  │   active → "Vigente"          [✏️] │ │
│                │  │   expired → "Vencida"         [✏️] │ │
│                │  │   cancelled → "Cancelada"     [✏️] │ │
│                │  │   [+ Adicionar valor]              │ │
│                │  └────────────────────────────────────┘ │
│                │                                         │
│  Regras        │  Regras de negócio:                     │
│  ─────────     │  ┌────────────────────────────────────┐ │
│  3 regras      │  │ [filtro] "Apólices vigentes =      │ │
│  [+ Nova]      │  │  status active + end_date >= hoje" │ │
│                │  │                              [✏️❌]│ │
│                │  └────────────────────────────────────┘ │
└────────────────┴─────────────────────────────────────────┘
```

**Comportamentos:**
- Painel esquerdo: lista de tabelas (árvore colapsável)
- Painel direito: detalhes da tabela selecionada
- Edição inline: clicar ✏️ abre campo de edição no lugar
- Ao salvar uma edição, o backend regenera o embedding automaticamente
- Feedback visual: "Salvo ✓" ao lado do campo editado
- Botão [+] para adicionar sinônimos, enum values, regras
- Botão ❌ para remover sinônimos, enum values, regras

---

### E11. Frontend — Seletor de conexão no chat

Atualizar `src/app/page.tsx` e `ChatContainer.tsx`:

O chat agora tem um seletor de conexão no topo:

```
┌──────────────────────────────────────────────┐
│  🐘 Produção SeguraPro  ▼                    │
├──────────────────────────────────────────────┤
│                                              │
│  [mensagens do chat]                         │
│                                              │
├──────────────────────────────────────────────┤
│  [input de pergunta]              [Enviar]   │
└──────────────────────────────────────────────┘
```

O dropdown lista todas as conexões ativas. Ao trocar, limpa o histórico de mensagens e mostra mensagem de boas-vindas com o nome do banco e quantidade de tabelas.

O `connection_id` é enviado em cada POST para `/api/chat`.

---

### E12. Frontend — Navegação

Adicionar navegação entre as páginas:

```
/                    → redireciona para /connections
/connections         → lista de conexões (E8)
/connections/new     → modal de nova conexão
/connections/[id]    → chat com essa conexão (E11)
/connections/[id]/metadata  → editor de metadados (E10)
```

Sidebar ou header com navegação:
```
┌────────────────────────────────────────┐
│  QueryMind     [Conexões]  [Chat]      │
└────────────────────────────────────────┘
```

---

### E13. Migration dos dados existentes

Script para migrar a instalação existente (SeguraPro) para o novo formato:

```python
# scripts/migrate_to_multi_connection.py

"""
1. Criar registro na tabela connections para o banco SeguraPro
2. Atualizar todas as tabelas/columns/synonyms/rules/embeddings
   existentes com o connection_id da SeguraPro
3. Não perder nenhum dado — é um backfill
"""
```

---

### E14. Dependências adicionais

Adicionar ao `pyproject.toml`:

```toml
"cryptography>=43.0",   # Fernet para criptografia de senhas

[project.optional-dependencies]
mysql = ["aiomysql>=0.2"]
sqlserver = ["aioodbc>=0.5"]
oracle = ["oracledb>=2.0"]
all-databases = ["aiomysql>=0.2", "aioodbc>=0.5", "oracledb>=2.0"]
```

Adicionar ao `.env.example`:
```env
ENCRYPTION_SECRET_KEY=   # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

### E15. Testes

| Arquivo | O que testa |
|---|---|
| `test_connections_api.py` | CRUD de conexões. Senha não aparece no GET. Teste de conexão retorna sucesso/erro. |
| `test_encryption.py` | Encrypt → decrypt retorna original. Decrypt com chave errada falha. |
| `test_introspectors.py` | PostgresIntrospector funciona (teste existente adaptado). Factory retorna introspector correto por db_type. |
| `test_metadata_api.py` | Criar/editar sinônimo. Criar/editar regra. Editar descrição regenera embedding. |
| `test_multi_connection.py` | Pipeline funciona com connection_id. Embeddings de conexão A não aparecem na busca de conexão B. |

---

## Critérios de aceite

1. Criar uma conexão via frontend, testar, e introspeccionar funciona
2. Editar descrições, sinônimos e regras pelo frontend funciona e regenera embeddings
3. O chat funciona com a conexão selecionada — perguntas retornam dados do banco correto
4. Duas conexões diferentes têm metadados isolados (embeddings de uma não vazam para outra)
5. Senhas são armazenadas criptografadas — não aparecem em logs, API responses ou banco
6. Remover uma conexão limpa todos os metadados associados (CASCADE)
7. O banco SeguraPro existente continua funcionando após a migração
8. Todos os testes passam

---

## Decisões técnicas

**Por que Fernet e não bcrypt/argon2?**
Bcrypt e argon2 são hashing — one-way. Precisamos recuperar a senha original para conectar ao banco, então é criptografia simétrica (encrypt/decrypt). Fernet é a implementação recomendada do cryptography package, usa AES-128-CBC com HMAC-SHA256.

**Por que drivers opcionais?**
Nem todo usuário precisa de MySQL, SQL Server e Oracle. Instalar aioodbc puxa ODBC headers e pesa o container. Com optional dependencies, o usuário instala só o que precisa: `pip install querymind[mysql]` ou `pip install querymind[all-databases]`.

**Por que não multi-tenant com autenticação nesta fase?**
Cada conexão é visível para todos os usuários do sistema. Multi-tenant (cada usuário vê só suas conexões) exige autenticação, roles e row-level security — escopo de uma Fase 6. Esta fase foca em tornar o sistema dinâmico, não em controle de acesso.

**Por que regenerar embedding a cada edição?**
É operação barata (< 50ms por texto em CPU). Garante que a busca semântica sempre reflete o estado atual dos metadados. Alternativa seria batch regeneration, mas adicionaria complexidade sem benefício real para o volume que temos (centenas de embeddings, não milhões).
