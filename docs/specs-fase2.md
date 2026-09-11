# Fase 2 — Pipeline Multi-Agente Text-to-SQL com LangGraph

## Objetivo

Implementar o pipeline completo de Text-to-SQL: o usuário envia uma pergunta em linguagem natural, o sistema identifica as tabelas relevantes via RAG, decompõe o problema, gera um plano, produz o SQL, executa com segurança e, se der erro, corrige automaticamente. Ao final, retorna a resposta em linguagem natural com os dados.

Ao final desta fase, deve ser possível rodar via script ou endpoint temporário:

```python
resposta = await pipeline.run("Qual o total de prêmios das apólices vigentes por corretor?")
# Retorna: texto NL + dados estruturados + SQL gerado
```

---

## Visão geral do grafo

```
                         ┌─────────────────┐
      Pergunta NL ──────>│  Schema Linker   │
                         └────────┬────────┘
                                  │ tabelas + colunas relevantes
                                  ▼
                         ┌─────────────────┐
                         │ Subproblem Agent │
                         └────────┬────────┘
                                  │ subproblemas por cláusula
                                  ▼
                         ┌─────────────────┐
                         │ Query Plan Agent │  (Chain-of-Thought)
                         └────────┬────────┘
                                  │ plano procedural (sem SQL)
                                  ▼
                         ┌─────────────────┐
                         │   SQL Generator  │
                         └────────┬────────┘
                                  │ query SQL
                                  ▼
                         ┌─────────────────┐
                         │  SQL Validator   │
                         └────────┬────────┘
                                  │ validação read-only
                                  ▼
                         ┌─────────────────┐
                         │  SQL Executor    │──── Sucesso ────> Response Synthesizer
                         └────────┬────────┘
                                  │ Erro
                                  ▼
                         ┌─────────────────┐
                         │ Correction Plan  │  (Taxonomia de erros)
                         └────────┬────────┘
                                  │ diagnóstico + plano de correção
                                  ▼
                         ┌─────────────────┐
                         │ Correction SQL   │──── volta pro SQL Executor
                         └─────────────────┘     (max 3 tentativas)
```

---

## Entregáveis

### E1. Estado compartilhado do grafo (AgentState)

Criar em `app/agents/state.py` o modelo Pydantic que representa o estado compartilhado entre todos os nós do grafo LangGraph:

```python
class AgentState(TypedDict):
    # Entrada
    question: str                              # Pergunta original do usuário

    # Schema Linker
    relevant_tables: list[str]                 # Nomes das tabelas selecionadas
    relevant_columns: dict[str, list[str]]     # {tabela: [colunas]}
    schema_context: str                        # DDL resumido + descrições para o prompt
    few_shot_examples: list[dict]              # Exemplos similares do dataset sintético
    matched_keywords: list[dict]               # Keywords matchadas no dicionário

    # Subproblem Agent
    subproblems: dict[str, str]                # {clausula: expressão parcial}

    # Query Plan Agent
    query_plan: str                            # Plano procedural em linguagem natural

    # SQL Generator
    generated_sql: str                         # SQL gerado
    sql_is_valid: bool                         # Passou na validação read-only

    # SQL Executor
    execution_result: list[dict] | None        # Linhas retornadas
    execution_error: str | None                # Mensagem de erro se falhou
    row_count: int                             # Quantidade de linhas retornadas
    was_truncated: bool                        # Se excedeu SQL_MAX_ROWS

    # Correction Loop
    correction_count: int                      # Tentativas de correção (0 a 3)
    correction_plan: str | None                # Diagnóstico do erro
    error_category: str | None                 # Categoria da taxonomia de erros

    # Response
    response_text: str                         # Resposta final em linguagem natural
    response_data: list[dict] | None           # Dados estruturados para o frontend
```

---

### E2. Schema Linker (fusão DANKE + SoT)

Criar em `app/agents/schema_linker.py`.

Este é o nó mais importante — combina a abordagem do DANKE (matching no dicionário + RAG vetorial) com a confirmação do SoT (LLM decide o conjunto final).

**Fluxo interno:**

1. **Extrair keywords** da pergunta via LLM (chamada simples):
   - Prompt: "Extraia as palavras-chave relevantes para uma consulta SQL: {question}"
   - Output: lista de keywords

2. **Matching no dicionário** (sem LLM, só código):
   - Para cada keyword, buscar na tabela `synonyms` do banco de metadados
   - Se a keyword bate com um sinônimo, retornar a tabela/coluna associada
   - Também buscar na tabela `enum_values` (ex: "vigente" → policies.status = 'active')

3. **RAG vetorial** via `EmbeddingService.search()`:
   - Buscar os top 10 metadados mais similares à pergunta completa
   - Filtrar por source_type para pegar tabelas, colunas e regras

4. **Few-shot retrieval** do dataset sintético:
   - Buscar na tabela `synthetic_examples` os 3-5 exemplos mais similares à pergunta
   - Filtrar pelos que usam tabelas já identificadas nos passos anteriores

5. **Confirmação via LLM** (prompt do DANKE adaptado):
   - Input: pergunta, keywords matchadas, candidatas do RAG, lista completa de tabelas do schema
   - Output: lista final de tabelas necessárias (JSON)
   - O LLM pode adicionar tabelas que o matching/RAG não pegou (ex: tabelas intermediárias para JOINs)

6. **Montar schema_context**:
   - Para cada tabela selecionada, gerar DDL resumido: `CREATE TABLE nome (col1 tipo, col2 tipo, ...)`
   - Incluir descrições das colunas como comentários SQL
   - Incluir relationships (FKs) entre as tabelas selecionadas
   - Incluir business_rules relevantes

**Saída no state:**
- `relevant_tables`, `relevant_columns`, `schema_context`, `few_shot_examples`, `matched_keywords`

**LLM recomendado:** Gemini Flash (precisa de raciocínio para decidir tabelas)

---

### E3. Subproblem Agent

Criar em `app/agents/subproblem.py`.

Decompõe a pergunta em subproblemas por cláusula SQL. Isso guia o Query Plan Agent e reduz erros.

**Prompt template:**

```
Dada a pergunta e o schema abaixo, decomponha a consulta em subproblemas
por cláusula SQL. Retorne um JSON com as cláusulas necessárias.

Schema:
{schema_context}

Pergunta: {question}

Cláusulas possíveis: SELECT, FROM, JOIN, WHERE, GROUP BY, HAVING,
ORDER BY, LIMIT, DISTINCT, UNION, EXCEPT, INTERSECT, subquery

Exemplo de saída:
{
  "SELECT": "total de prêmios por corretor",
  "FROM": "policies",
  "JOIN": "policies com brokers via broker_id",
  "WHERE": "apólices vigentes (status = 'active' AND end_date >= CURRENT_DATE)",
  "GROUP BY": "agrupar por corretor"
}
```

**Saída no state:** `subproblems`

**LLM recomendado:** Gemini Flash

---

### E4. Query Plan Agent (Chain-of-Thought)

Criar em `app/agents/query_planner.py`.

Gera um plano procedural passo-a-passo em linguagem natural — sem SQL. O paper SoT mostrou que pular esta etapa aumentou queries incorretas em 5%.

**Prompt template:**

```
Você é um planejador de consultas SQL. Dado o schema, os subproblemas
identificados e a pergunta original, gere um plano passo-a-passo
para construir a query.

NÃO gere SQL. Descreva cada passo em linguagem natural.

Schema:
{schema_context}

Pergunta: {question}

Subproblemas identificados:
{subproblems}

Exemplos similares (referência):
{few_shot_examples}

Regras de negócio relevantes:
{business_rules extraídas do schema_context}

Gere o plano como uma lista numerada. Exemplo:
1. Começar pela tabela policies
2. Fazer JOIN com brokers usando broker_id
3. Filtrar por status = 'active' E end_date >= CURRENT_DATE
4. Somar premium_amount agrupando por brokers.full_name
5. Ordenar do maior para o menor
```

**Saída no state:** `query_plan`

**LLM recomendado:** Gemini Flash (o paper SoT mostrou que este agente precisa de bom raciocínio)

---

### E5. SQL Generator

Criar em `app/agents/sql_generator.py`.

Gera o SQL executável a partir do plano. Recebe o plano e o schema, não a pergunta original diretamente (para evitar que ignore o plano).

**Prompt template:**

```
Você é um gerador de SQL PostgreSQL. Converta o plano abaixo em uma
query SQL válida.

Regras obrigatórias:
- Apenas SELECT (nunca INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE)
- Use APENAS as tabelas e colunas listadas no schema
- Use aliases claros para tabelas (ex: p para policies, b para brokers)
- Não use SELECT * — liste as colunas necessárias
- Valores monetários com 2 casas decimais: ROUND(valor, 2)
- Para datas "hoje", use CURRENT_DATE
- Limite de {max_rows} linhas se não houver LIMIT explícito no plano

Schema:
{schema_context}

Plano de execução:
{query_plan}

Keywords matchadas (valores no banco):
{matched_keywords}

Exemplos similares:
{few_shot_examples}

Retorne APENAS o SQL, sem explicações.
```

**Post-processing (código, não LLM):**
- Remover blocos markdown (```sql ... ```)
- Remover comentários `--`
- Remover ponto-e-vírgula final
- Strip de whitespace

**Saída no state:** `generated_sql`

**LLM recomendado:** Gemini Flash

---

### E6. SQL Validator

Criar em `app/agents/sql_validator.py`.

Este nó é **código puro, sem LLM**. Valida que o SQL gerado é seguro antes de executar.

**Checagens obrigatórias:**

1. **Blocklist de comandos** — rejeitar se contiver (case-insensitive, como token isolado):
   `INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, EXEC, CALL, SET, COPY, VACUUM, REINDEX, CLUSTER, LOCK, DISCARD, LOAD, COMMENT`

2. **Deve começar com SELECT ou WITH** (para CTEs)

3. **Não pode conter múltiplos statements** (rejeitar se tiver `;` seguido de outro statement)

4. **Não pode conter funções perigosas:**
   `pg_sleep, pg_terminate_backend, pg_cancel_backend, lo_import, lo_export, dblink`

5. **Validar que todas as tabelas referenciadas existem** no banco de metadados (tabela `tables`)

Implementar como uma função que retorna `(is_valid: bool, rejection_reason: str | None)`.

**Saída no state:** `sql_is_valid` (se False, pula execução e vai direto pro correction loop com o erro de validação)

---

### E7. SQL Executor

Criar em `app/agents/sql_executor.py`.

Executa o SQL no banco de produção usando o usuário read-only.

**Implementação:**

```python
async def execute_sql(sql: str, timeout: int = 30, max_rows: int = 500) -> ExecutionResult:
    """
    Executa SQL no banco de produção com:
    - statement_timeout configurado por conexão
    - Limite de linhas (fetchmany)
    - Captura de exceções com mensagem amigável
    """
```

**Comportamentos:**
- Configurar `statement_timeout` na conexão: `SET statement_timeout = '{timeout}s'`
- Usar `fetchmany(max_rows + 1)` — se retornar max_rows + 1, truncar e marcar `was_truncated = True`
- Capturar exceções asyncpg e extrair mensagem de erro limpa
- Retornar colunas (nomes) + linhas (como list[dict])

**Saída no state:**
- Sucesso: `execution_result`, `row_count`, `was_truncated`, `execution_error = None`
- Erro: `execution_result = None`, `execution_error = "mensagem do erro"`

**Conditional edge depois deste nó:**
- Se `execution_error is None` → vai para Response Synthesizer
- Se `execution_error is not None` AND `correction_count < 3` → vai para Correction Plan
- Se `execution_error is not None` AND `correction_count >= 3` → vai para Response Synthesizer (com mensagem de erro)

---

### E8. Correction Plan Agent (Taxonomia de Erros)

Criar em `app/agents/correction_planner.py`.

Analisa o erro e classifica usando a taxonomia de 31 tipos do SQL-of-Thought. Produz um plano de correção.

**Taxonomia de erros (incluir no prompt):**

```
Syntax: sql_syntax_error, invalid_alias
Schema Link: table_missing, col_missing, ambiguous_col, incorrect_foreign_key
Join: join_missing, join_wrong_type, extra_table, incorrect_col
Filter: where_missing, condition_wrong_col, condition_type_mismatch
Aggregation: agg_no_groupby, groupby_missing_col, having_without_groupby,
             having_incorrect, having_vs_where
Value: hardcoded_value, value_format_wrong
Subquery: unused_subquery, subquery_missing, subquery_correlation_error
Set Operations: union_missing, intersect_missing, except_missing
Other: order_by_missing, limit_missing, duplicate_select,
       unsupported_function, extra_values_selected
```

**Prompt template:**

```
Você é um especialista em correção de SQL PostgreSQL.

A query abaixo falhou ao executar. Analise o erro, classifique-o
usando a taxonomia fornecida, e produza um plano de correção.

Query com erro:
{generated_sql}

Erro de execução:
{execution_error}

Schema disponível:
{schema_context}

Pergunta original:
{question}

Taxonomia de erros SQL:
{error_taxonomy}

Responda no formato:
1. CATEGORIA DO ERRO: (uma das categorias da taxonomia)
2. DIAGNÓSTICO: (o que causou o erro)
3. PLANO DE CORREÇÃO: (passos para corrigir, sem gerar SQL)
```

**Saída no state:** `correction_plan`, `error_category`, `correction_count += 1`

**LLM recomendado:** Groq / Llama 3.3 70B (baixa latência, o diagnóstico é mais direto)

---

### E9. Correction SQL Agent

Criar em `app/agents/correction_sql.py`.

Regenera o SQL baseado no plano de correção, evitando o erro anterior.

**Prompt template:**

```
Você é um gerador de SQL PostgreSQL. A query anterior falhou.
Use o plano de correção abaixo para gerar uma query corrigida.

Query anterior (COM ERRO — não repita o mesmo erro):
{generated_sql}

Erro: {execution_error}
Categoria: {error_category}
Plano de correção: {correction_plan}

Schema:
{schema_context}

Pergunta original: {question}

Retorne APENAS o SQL corrigido, sem explicações.
```

**Saída no state:** `generated_sql` (sobrescreve o anterior)

Depois deste nó, o fluxo volta para o SQL Validator → SQL Executor.

**LLM recomendado:** Groq / Llama 3.3 70B

---

### E10. Response Synthesizer

Criar em `app/agents/response_synthesizer.py`.

Transforma os dados retornados em uma resposta em linguagem natural executiva.

**Prompt template:**

```
Você é um assistente de uma corretora de seguros. O usuário fez a
pergunta abaixo e o sistema executou uma consulta SQL que retornou
os dados a seguir.

Pergunta: {question}
SQL executado: {generated_sql}
Dados retornados ({row_count} linhas{", truncado" if was_truncated}):
{execution_result formatado como tabela markdown}

Gere uma resposta em linguagem natural que:
1. Responda diretamente à pergunta
2. Destaque os números mais relevantes
3. Use formatação brasileira (R$ para valores, dd/mm/aaaa para datas)
4. Seja conciso e executivo (máximo 3 parágrafos)
5. Se os dados estiverem vazios, informe que não há resultados

Se a consulta falhou após todas as tentativas, explique que não foi
possível processar a pergunta e sugira reformulação.
```

**Saída no state:** `response_text`, `response_data`

**LLM recomendado:** Gemini Flash

---

### E11. Grafo LangGraph

Criar em `app/agents/graph.py` o grafo completo.

```python
from langgraph.graph import StateGraph, END

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Nós
    graph.add_node("schema_linker", schema_linker_node)
    graph.add_node("subproblem_agent", subproblem_node)
    graph.add_node("query_planner", query_planner_node)
    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("sql_validator", sql_validator_node)
    graph.add_node("sql_executor", sql_executor_node)
    graph.add_node("correction_planner", correction_planner_node)
    graph.add_node("correction_sql", correction_sql_node)
    graph.add_node("response_synthesizer", response_synthesizer_node)

    # Arestas lineares
    graph.set_entry_point("schema_linker")
    graph.add_edge("schema_linker", "subproblem_agent")
    graph.add_edge("subproblem_agent", "query_planner")
    graph.add_edge("query_planner", "sql_generator")
    graph.add_edge("sql_generator", "sql_validator")

    # Conditional: validator
    graph.add_conditional_edges("sql_validator", route_after_validation)

    # Conditional: executor
    graph.add_conditional_edges("sql_executor", route_after_execution)

    # Correction loop
    graph.add_edge("correction_planner", "correction_sql")
    graph.add_edge("correction_sql", "sql_validator")

    # Final
    graph.add_edge("response_synthesizer", END)

    return graph.compile()


def route_after_validation(state: AgentState) -> str:
    if state["sql_is_valid"]:
        return "sql_executor"
    # SQL inválido = tratar como erro de execução
    if state["correction_count"] < 3:
        return "correction_planner"
    return "response_synthesizer"


def route_after_execution(state: AgentState) -> str:
    if state["execution_error"] is None:
        return "response_synthesizer"
    if state["correction_count"] < 3:
        return "correction_planner"
    return "response_synthesizer"
```

---

### E12. Configuração de providers por agente

Criar em `app/agents/config.py`:

```python
AGENT_LLM_CONFIG = {
    "schema_linker":        {"provider": "gemini", "model": "gemini-2.5-flash"},
    "subproblem_agent":     {"provider": "gemini", "model": "gemini-2.5-flash"},
    "query_planner":        {"provider": "gemini", "model": "gemini-2.5-flash"},
    "sql_generator":        {"provider": "gemini", "model": "gemini-2.5-flash"},
    "correction_planner":   {"provider": "groq",   "model": "llama-3.3-70b-versatile"},
    "correction_sql":       {"provider": "groq",   "model": "llama-3.3-70b-versatile"},
    "response_synthesizer": {"provider": "gemini", "model": "gemini-2.5-flash"},
}
```

Isso permite trocar qualquer agente para OpenAI/Claude no futuro sem tocar no código dos agentes.

---

### E13. Script de teste end-to-end

Criar em `scripts/test_pipeline.py`:

```python
"""
Testa o pipeline completo com perguntas do domínio SeguraPro.
Roda fora do pytest — é um teste funcional manual.

Uso: cd backend && uv run python -m scripts.test_pipeline
"""
```

**Perguntas de teste (da mais simples à mais complexa):**

```python
TEST_QUESTIONS = [
    # Simples — 1 tabela, sem JOIN
    "Quantos clientes ativos temos?",
    "Quais corretores estão ativos?",

    # Média — JOIN simples, filtro
    "Qual o total de prêmios das apólices vigentes?",
    "Quais sinistros estão em análise?",

    # Média-alta — JOIN + agregação + GROUP BY
    "Qual o total de prêmios por corretor nas apólices ativas?",
    "Quantas apólices cada seguradora tem vigentes?",

    # Complexa — múltiplos JOINs, regra de negócio
    "Qual a sinistralidade por ramo de seguro?",
    "Quais parcelas estão em atraso e de qual cliente?",

    # Complexa — subquery ou HAVING
    "Quais corretores têm mais de R$ 1.000 em comissões pendentes?",
    "Qual seguradora tem o menor prêmio médio em seguros auto?",
]
```

Para cada pergunta, o script deve imprimir:
- A pergunta
- Tabelas selecionadas pelo Schema Linker
- SQL gerado
- Se houve correção (quantas tentativas)
- Quantidade de linhas retornadas
- Resposta em linguagem natural
- Tempo total

---

### E14. Testes unitários

Criar em `tests/`:

| Arquivo | O que testa |
|---|---|
| `test_sql_validator.py` | Rejeita INSERT/DELETE/DROP. Aceita SELECT e WITH. Rejeita pg_sleep. Rejeita tabelas inexistentes. |
| `test_state.py` | AgentState é criado corretamente com defaults. |
| `test_graph.py` | Routing: se execution_error=None → response_synthesizer. Se error + count<3 → correction. Se error + count>=3 → response. |

---

## Dependências adicionais

Adicionar ao `pyproject.toml`:

```toml
"langgraph>=0.2",
```

---

## Critérios de aceite

A Fase 2 está completa quando:

1. O grafo LangGraph roda sem erro para as 10 perguntas de teste
2. Perguntas simples (1 tabela) retornam SQL correto na primeira tentativa
3. Perguntas médias (JOIN + filtro) retornam SQL correto em até 1 correção
4. O SQL Validator bloqueia 100% dos comandos de escrita em testes
5. O correction loop corrige pelo menos 1 erro real durante os testes
6. A resposta final está em português com formatação brasileira (R$, datas)
7. Cada pergunta completa o pipeline em menos de 30 segundos
8. Todos os testes unitários passam
9. O código segue as convenções do CLAUDE.md

---

## Decisões técnicas

**Por que Gemini para os agentes principais e Groq para correção?**
O pipeline faz 4-6 chamadas de LLM por pergunta. Gemini Flash tem 1.500 RPD (free tier), dando ~250-375 perguntas/dia. O correction loop precisa de baixa latência (diagnóstico rápido), e o Groq com Llama 3.3 70B responde em 300-800 tok/s. Separar os providers também distribui o consumo entre dois free tiers.

**Por que não usar o SQL-of-Thought puro?**
O SoT foi testado com bases acadêmicas (Spider) onde o schema inteiro cabe no prompt. Com bases reais, o Schema Linker precisa do matching do DANKE para filtrar antes. Também adicionamos o SQL Validator como camada de segurança que não existe no paper.

**Por que o Response Synthesizer recebe os dados brutos?**
Para que a LLM possa formatar valores (R$, datas) e destacar insights. O frontend receberá tanto o texto NL quanto os dados estruturados, podendo renderizar tabelas e gráficos (Fase 4).

**Correction loop máximo de 3 tentativas?**
O paper SoT mostrou que a maioria das correções bem-sucedidas acontecem na 1ª tentativa. Após 3, a probabilidade de sucesso cai drasticamente e o custo de tokens sobe. Melhor retornar uma mensagem amigável pedindo reformulação.