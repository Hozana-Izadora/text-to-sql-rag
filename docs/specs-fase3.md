# Fase 3 — API FastAPI + Frontend React com Chat Streaming

## Objetivo

Conectar o pipeline multi-agente (Fase 2) a uma interface de chat web. O usuário digita uma pergunta, vê a resposta sendo gerada em tempo real (streaming), e pode visualizar o SQL gerado e os dados retornados em tabela.

Ao final desta fase, o sistema funciona de ponta a ponta via navegador: `http://localhost:3000`

---

## Visão geral da arquitetura

```
┌─────────────────────────┐     SSE stream      ┌──────────────────────────┐
│   React (porta 3000)  │ ◄──────────────────► │  FastAPI (porta 8000)    │
│                         │                      │                          │
│  Chat UI                │   POST /api/chat     │  Recebe pergunta         │
│  Histórico de mensagens │   ──────────────►    │  Roda pipeline LangGraph │
│  Tabela de dados        │                      │  Streama eventos SSE     │
│  SQL colapsável         │   GET /api/health    │                          │
│  Loading states         │   ──────────────►    │  Health check            │
└─────────────────────────┘                      └──────────────────────────┘
```

**Comunicação:** SSE (Server-Sent Events) via POST. Não WebSocket — SSE é mais simples, funciona com HTTP/2, não precisa de gerenciamento de conexão bidirecional, e o nosso fluxo é unidirecional (backend → frontend). O frontend envia a pergunta via POST e recebe um stream de eventos.

---

## Entregáveis

### E1. API FastAPI — Rotas

Criar/atualizar em `app/api/`:

#### `app/api/routes.py`

```python
router = APIRouter(prefix="/api")

@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    """
    Recebe uma pergunta, roda o pipeline e retorna SSE stream.

    Eventos enviados (cada um é uma linha 'data: {json}\n\n'):
      - {"event": "status",   "data": "Identificando tabelas relevantes..."}
      - {"event": "status",   "data": "Gerando plano de consulta..."}
      - {"event": "status",   "data": "Executando SQL..."}
      - {"event": "status",   "data": "Corrigindo query (tentativa 1/3)..."}
      - {"event": "sql",      "data": "SELECT ..."}
      - {"event": "columns",  "data": ["col1", "col2", ...]}
      - {"event": "rows",     "data": [{"col1": "val1", ...}, ...]}
      - {"event": "metadata", "data": {"row_count": 15, "truncated": false, "tables_used": [...]}}
      - {"event": "answer",   "data": "token por token da resposta NL..."}
      - {"event": "done",     "data": null}
      - {"event": "error",    "data": "mensagem de erro amigável"}
    """

@router.get("/health")
async def health():
    """Retorna status dos serviços (backend, production-db, metadata-db)."""
```

#### Schemas Pydantic — `app/api/schemas.py`

```python
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)

class ChatEvent(BaseModel):
    event: str    # status, sql, columns, rows, metadata, answer, done, error
    data: Any
```

---

### E2. Integração pipeline → SSE stream

Criar em `app/api/streaming.py`:

A função que conecta o pipeline LangGraph ao stream SSE. O pipeline já roda e retorna o `AgentState` final. Precisamos interceptar cada nó para emitir eventos de progresso.

**Abordagem:** usar callbacks do LangGraph para emitir eventos conforme cada nó completa.

```python
async def stream_pipeline(question: str) -> AsyncGenerator[str, None]:
    """
    Roda o pipeline e yield eventos SSE formatados.

    Fluxo de eventos:
    1. Schema Linker começa → yield status "Identificando tabelas..."
    2. Schema Linker completa → yield status "Tabelas: policies, brokers, ..."
    3. Subproblem completa → yield status "Decompondo a consulta..."
    4. Query Planner completa → yield status "Planejando execução..."
    5. SQL Generator completa → yield evento sql com a query
    6. SQL Validator → se falhar, yield status com motivo
    7. SQL Executor →
       - Sucesso: yield columns, rows, metadata
       - Erro: yield status "Corrigindo..." (se count < 3)
    8. Correction loop → yield status a cada tentativa
    9. Response Synthesizer → yield answer token por token
    10. yield done
    """
```

**Formato SSE:**
Cada evento é uma linha no formato:
```
data: {"event": "status", "data": "Identificando tabelas relevantes..."}\n\n
```

O `\n\n` duplo é obrigatório no protocolo SSE para separar eventos.

---

### E3. CORS e configuração da API

Atualizar `app/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend React
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(routes.router)
```

Adicionar variável de ambiente `FRONTEND_URL=http://localhost:3000` para configurar CORS dinamicamente.

---

### E4. Frontend React — Setup do projeto

Criar em `frontend/`:

```bash
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --no-import-alias
```

Instalar dependências adicionais:
```bash
cd frontend
npm install lucide-react
```

**Estrutura alvo:**
```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx          # Layout raiz com metadata
│   │   ├── page.tsx            # Página principal (chat)
│   │   └── globals.css         # Tailwind base
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatContainer.tsx    # Container principal do chat
│   │   │   ├── MessageList.tsx      # Lista de mensagens com scroll
│   │   │   ├── MessageBubble.tsx    # Bolha individual (user ou assistant)
│   │   │   ├── InputBar.tsx         # Input + botão de envio
│   │   │   └── StatusIndicator.tsx  # Indicador de progresso por etapa
│   │   ├── data/
│   │   │   ├── DataTable.tsx        # Tabela de dados retornados
│   │   │   └── SqlViewer.tsx        # SQL colapsável com syntax highlight
│   │   └── ui/
│   │       └── LoadingDots.tsx      # Animação de loading
│   └── lib/
│       ├── api.ts               # Função de fetch + parse SSE
│       └── types.ts             # Tipos TypeScript
├── package.json
├── tailwind.config.ts
├── tsconfig.json
└── Dockerfile
```

---

### E5. Tipos TypeScript

Criar em `src/lib/types.ts`:

```typescript
export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;         // Texto da resposta NL
  sql?: string;            // SQL gerado (colapsável)
  columns?: string[];      // Nomes das colunas
  rows?: Record<string, unknown>[];  // Dados retornados
  metadata?: {
    rowCount: number;
    truncated: boolean;
    tablesUsed: string[];
    executionTime?: number;
  };
  status?: string;         // Status atual ("Gerando SQL...")
  isStreaming?: boolean;    // Se ainda está recebendo dados
  isError?: boolean;       // Se houve erro
}

export interface SSEEvent {
  event: string;
  data: unknown;
}
```

---

### E6. Cliente SSE

Criar em `src/lib/api.ts`:

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function streamChat(
  question: string,
  onEvent: (event: SSEEvent) => void,
  onDone: () => void,
  onError: (error: string) => void,
): Promise<void> {
  /**
   * Envia pergunta via POST e parseia o stream SSE.
   *
   * Usa fetch com ReadableStream — não precisa de lib externa.
   * O parsing é manual: ler linha por linha, separar por \n\n,
   * extrair o JSON de cada "data: {...}".
   */
}
```

**Implementação deve:**
- Usar `fetch` nativo com `response.body.getReader()` + `TextDecoder`
- Parsear o stream SSE manualmente (split por `\n\n`, extrair após `data: `)
- Chamar `onEvent` para cada evento parseado
- Chamar `onDone` quando receber evento `done`
- Chamar `onError` em caso de falha de rede ou evento `error`
- Suportar cancelamento via `AbortController`

---

### E7. Componente ChatContainer

Criar em `src/components/chat/ChatContainer.tsx`:

Componente principal que gerencia o estado do chat.

**Estado:**
- `messages: ChatMessage[]` — histórico de mensagens
- `isLoading: boolean` — se o pipeline está rodando
- `currentStatus: string | null` — status atual do pipeline

**Comportamento:**
1. Usuário digita e clica "Enviar" (ou Enter)
2. Adiciona mensagem do usuário ao histórico
3. Cria mensagem do assistant vazia com `isStreaming: true`
4. Chama `streamChat()` passando callbacks
5. Cada evento SSE atualiza a mensagem do assistant:
   - `status` → atualiza `currentStatus` e `message.status`
   - `sql` → define `message.sql`
   - `columns` → define `message.columns`
   - `rows` → define `message.rows`
   - `metadata` → define `message.metadata`
   - `answer` → concatena ao `message.content` (streaming token por token)
   - `done` → marca `isStreaming: false`
   - `error` → marca `isError: true`, define `message.content` com o erro
6. Auto-scroll para a última mensagem

---

### E8. Componente MessageBubble

Criar em `src/components/chat/MessageBubble.tsx`:

Renderiza uma mensagem individual. O layout muda conforme o role:

**Mensagem do usuário:**
- Alinhada à direita
- Fundo com cor de destaque
- Apenas texto

**Mensagem do assistant:**
- Alinhada à esquerda
- Fundo neutro
- Pode conter:
  1. **StatusIndicator** (durante streaming): mostra a etapa atual ("Identificando tabelas...", "Gerando SQL...", etc.) com animação
  2. **Texto da resposta** (após streaming completo ou conforme vai chegando)
  3. **SqlViewer** (colapsável): mostra o SQL gerado com botão de copiar
  4. **DataTable** (se houver dados): tabela responsiva com os resultados

**Ordem de renderização na bolha do assistant:**
```
┌────────────────────────────────────────┐
│ ⏳ Executando SQL...                   │  ← StatusIndicator (some ao completar)
│                                        │
│ O total de prêmios das apólices        │  ← Texto da resposta NL
│ vigentes é de R$ 45.230,00...          │
│                                        │
│ ▶ Ver SQL gerado                       │  ← SqlViewer (colapsável)
│ ┌────────────────────────────────────┐ │
│ │ SELECT b.full_name,               │ │
│ │        ROUND(SUM(p.premium)...)    │ │
│ │ FROM policies p ...                │ │
│ └────────────────────────────────────┘ │
│                                        │
│ ┌──────────┬───────────────┐           │  ← DataTable
│ │ Corretor │ Total Prêmios │           │
│ ├──────────┼───────────────┤           │
│ │ Ana C.   │ R$ 12.350,00  │           │
│ │ Bruno F. │ R$ 8.920,00   │           │
│ └──────────┴───────────────┘           │
│                   15 linhas retornadas  │
└────────────────────────────────────────┘
```

---

### E9. Componente DataTable

Criar em `src/components/data/DataTable.tsx`:

Tabela responsiva para exibir os dados retornados pelo SQL.

**Comportamentos:**
- Recebe `columns: string[]` e `rows: Record<string, unknown>[]`
- Renderiza cabeçalho com nomes das colunas
- Renderiza linhas com os valores
- Se `rows.length > 10`, mostrar apenas 10 e um botão "Ver todas (N linhas)"
- Valores numéricos: alinhar à direita
- Overflow horizontal com scroll em telas pequenas
- Mostrar badge "Resultados truncados" se `metadata.truncated`

---

### E10. Componente SqlViewer

Criar em `src/components/data/SqlViewer.tsx`:

SQL colapsável com syntax highlighting básico.

**Comportamentos:**
- Estado inicial: colapsado, mostra apenas "▶ Ver SQL gerado"
- Ao clicar: expande e mostra o SQL formatado
- Botão de copiar ao lado (ícone clipboard)
- Syntax highlighting simples via CSS (keywords SQL em cor diferente)
- Não precisa de lib de highlight — basta regex para pintar SELECT, FROM, WHERE, JOIN, GROUP BY, ORDER BY, HAVING, LIMIT, AS, ON, AND, OR, NOT, IN, BETWEEN, LIKE, NULL, COUNT, SUM, AVG, MAX, MIN, ROUND, CURRENT_DATE, DISTINCT

---

### E11. Componente InputBar

Criar em `src/components/chat/InputBar.tsx`:

**Comportamentos:**
- Input de texto com placeholder "Pergunte sobre os dados da SeguraPro..."
- Botão "Enviar" com ícone (Send do lucide-react)
- Desabilitado enquanto `isLoading`
- Submit ao pressionar Enter (sem Shift)
- Shift+Enter faz quebra de linha (textarea auto-resize)
- Limpa o input ao enviar

---

### E12. Layout e página principal

#### `src/app/layout.tsx`
- Título: "QueryMind — Assistente de Dados"
- Meta description
- Font: Inter via next/font

#### `src/app/page.tsx`
- Renderiza `ChatContainer` como componente client
- Mensagem inicial do assistant: "Olá! Sou o assistente de dados da SeguraPro. Pergunte sobre apólices, sinistros, comissões, clientes e mais."

---

### E13. Dockerfile do frontend

Criar `frontend/Dockerfile`:

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
ENV NODE_ENV=production
EXPOSE 3000
CMD ["node", "server.js"]
```

Adicionar ao `next.config.ts`:
```typescript
const nextConfig = {
  output: "standalone",
};
```

---

### E14. Docker Compose atualizado

Adicionar serviço `frontend` ao `docker-compose.yml`:

```yaml
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://backend:8000
    depends_on:
      - backend
```

---

### E15. Variáveis de ambiente adicionais

Adicionar ao `.env.example`:

```env
# Frontend
FRONTEND_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

### E16. Testes

| Arquivo | O que testa |
|---|---|
| `backend/tests/test_api.py` | POST /api/chat com pergunta válida retorna SSE stream. POST com pergunta vazia retorna 422. GET /health retorna 200. |
| `backend/tests/test_streaming.py` | Formato SSE correto (data: {...}\n\n). Eventos na ordem certa (status → sql → columns → rows → answer → done). Evento error em caso de falha. |

---

## Design visual

**Princípios:**
- Fundo claro, texto escuro (tema claro padrão)
- Mensagens do usuário com fundo azul/índigo, texto branco
- Mensagens do assistant com fundo cinza claro
- DataTable com bordas sutis, cabeçalho com fundo levemente mais escuro
- SqlViewer com fundo escuro (estilo terminal), texto monoespaçado claro
- StatusIndicator com dots animados e texto em cinza
- Responsivo: funciona em desktop e mobile
- Sem sidebar, sem navegação — é uma tela única de chat

**Paleta Tailwind sugerida:**
- User bubble: `bg-indigo-600 text-white`
- Assistant bubble: `bg-gray-100 text-gray-900`
- SQL viewer: `bg-gray-900 text-green-400 font-mono`
- Status text: `text-gray-500`
- Input border: `border-gray-300 focus:border-indigo-500`
- Send button: `bg-indigo-600 hover:bg-indigo-700 text-white`

---

## Critérios de aceite

A Fase 3 está completa quando:

1. `docker compose up -d` sobe backend, frontend, e os dois bancos
2. Acessar `http://localhost:3000` mostra a interface de chat
3. Digitar "Quantos clientes ativos temos?" e enviar mostra:
   - Status indicators durante o processamento
   - Resposta em linguagem natural
   - SQL gerado (colapsável)
   - Tabela de dados (se houver)
4. O stream SSE funciona (resposta aparece progressivamente, não de uma vez)
5. Enviar pergunta inválida (vazia ou muito curta) mostra erro amigável
6. A interface funciona em telas desktop (>1024px) e mobile (>375px)
7. Testes backend passam
8. O código segue as convenções do CLAUDE.md

---

## Decisões técnicas

**Por que SSE e não WebSocket?**
O fluxo é unidirecional: o usuário envia uma pergunta (POST), o backend streama a resposta. WebSocket adiciona complexidade (gerenciamento de conexão, reconexão, heartbeat) sem benefício. SSE funciona sobre HTTP padrão, é suportado nativamente pelos browsers, e é mais simples de implementar e debugar. Se no futuro precisarmos de bidirecional (ex: cancelar uma query em andamento), podemos adicionar um endpoint POST /api/cancel separado.

**Por que não usar o Vercel AI SDK?**
O Vercel AI SDK (`ai` package) é voltado para chat com LLMs diretamente. Nosso caso é diferente: o backend faz todo o processamento (pipeline multi-agente) e o frontend só consome o stream. Um fetch manual com parsing SSE é mais transparente e não adiciona dependências desnecessárias.

**Por que streaming token por token no Response Synthesizer?**
Na Fase 2, o Response Synthesizer retorna a resposta completa de uma vez. Para streaming real, precisamos que a LLM faça streaming e o backend repasse token por token. Isso dá feedback visual imediato ao usuário. Implementação: usar `llm.astream()` do LangChain no último nó e yield cada chunk como evento SSE.

**Por que sem autenticação nesta fase?**
O foco é funcionalidade end-to-end. Autenticação (JWT, OAuth) seria escopo de uma Fase 5 de hardening para produção. Por ora, a aplicação roda em rede local.
