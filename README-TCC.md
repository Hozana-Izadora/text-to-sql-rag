# Inquiro — Plataforma Inteligente de Text-to-SQL Baseada em RAG e Arquitetura Multi-Agente com Correção Guiada por Taxonomia de Erros

**Trabalho de Conclusão de Curso — GenAI & LLMs Master**

| | |
|---|---|
| **Autora** | Hozana Izadora da Silva Ferreira |
| **Instituição** | Pontifícia Universidade Católica do Rio de Janeiro (PUC-Rio) |
| **Orientador(a)** | *[a definir]* |
| **Local / Ano** | Fortaleza, 2026 |
| **Documento completo** | [`tcc.docx`](tcc.docx) *(ou [`tcc.pdf`](tcc.pdf))* |

> Este README é a porta de entrada do trabalho: resume o problema, a solução proposta, a arquitetura implementada e os resultados obtidos. O texto integral — com referencial teórico, metodologia detalhada, discussão e apêndices — está em [`tcc.docx`](tcc.docx).

---

## Sumário

- [1. Resumo](#1-resumo)
- [2. O problema e a proposta](#2-o-problema-e-a-proposta)
- [3. Fundamentação acadêmica](#3-fundamentação-acadêmica)
- [4. Arquitetura da solução](#4-arquitetura-da-solução)
- [5. Segurança](#5-segurança)
- [6. Ambiente de validação](#6-ambiente-de-validação)
- [7. Resultados](#7-resultados)
- [8. Limitações e trabalhos futuros](#8-limitações-e-trabalhos-futuros)
- [9. Estrutura do repositório](#9-estrutura-do-repositório)
- [10. Como executar](#10-como-executar)
- [11. Referências principais](#11-referências-principais)

---

## 1. Resumo

Sistemas corporativos armazenam informação estratégica em bancos de dados relacionais, mas o acesso a essa informação costuma exigir conhecimento de SQL, criando uma barreira entre usuários de negócio e os dados de que precisam para decidir.

Este trabalho apresenta o **Inquiro**, uma plataforma Text-to-SQL que converte perguntas em linguagem natural, em português, em consultas SQL executadas de forma segura sobre bancos de dados relacionais, retornando respostas em linguagem natural acompanhadas de tabelas, gráficos e relatórios exportáveis.

A arquitetura funde duas propostas acadêmicas recentes:

- a camada de metadados do **DANKE** (NASCIMENTO et al., 2026) — grafo de schema, dicionário de sinônimos e exemplos few-shot recuperados por similaridade semântica;
- o pipeline multi-agente do **SQL-of-Thought** (CHATURVEDI; CHADHA; BINDSCHAEDLER, 2025) — agentes especializados orquestrados por um grafo de estados (LangGraph), com um laço de correção guiado por uma taxonomia de 31 tipos de erro (SHEN et al., 2024).

**Palavras-chave:** Text-to-SQL; RAG; Agentes Inteligentes; LLM; Processamento de Linguagem Natural.

---

## 2. O problema e a proposta

Bancos de produção têm dezenas de tabelas e centenas de colunas — grande demais para caber no contexto de um LLM — e usam nomes técnicos que não coincidem com o vocabulário de negócio do usuário final. Uma abordagem ingênua de "jogar a pergunta para o LLM" falha justamente nesses dois pontos, além de não ter mecanismo de correção quando o SQL gerado está errado.

**Objetivo geral:** projetar, implementar e validar uma plataforma Text-to-SQL corporativa que combine uma camada de metadados enriquecida com um pipeline multi-agente de geração e correção de SQL, com interface web completa e suporte a múltiplos bancos de dados.

**Objetivos específicos:**

1. Camada de metadados com introspecção automática de schema e enriquecimento via dicionário de dados;
2. Pipeline multi-agente (LangGraph) com laço de correção guiado por taxonomia de erros;
3. Três camadas de segurança independentes, garantindo execução exclusivamente `SELECT`;
4. Interface web com chat, visualização de SQL, tabelas e gráficos;
5. Suporte a múltiplos SGBDs e conexões configuráveis pela própria interface;
6. Validação do pipeline em um domínio de teste realista.

---

## 3. Fundamentação acadêmica

| Trabalho | Contribuição usada no Inquiro |
|---|---|
| **DANKE** (NASCIMENTO et al., 2026) | Knowledge graph de schema + dicionário de sinônimos + few-shot recuperado por similaridade semântica |
| **SQL-of-Thought** (CHATURVEDI; CHADHA; BINDSCHAEDLER, 2025) | Decomposição em agentes especializados + laço de correção |
| **Shen et al. (2024)** | Taxonomia de 31 tipos de erro SQL em 9 categorias, usada para diagnosticar falhas de execução |
| **Lewis et al. (2020)** | Fundamento conceitual do RAG usado na recuperação semântica de schema |
| **Wei et al. (2022)** | Chain-of-Thought, aplicado no agente de planejamento de consultas |

A lista completa de referências (16 itens, formato ABNT NBR 6023) está no capítulo de Referências de [`tcc.docx`](tcc.docx).

---

## 4. Arquitetura da solução

```
schema_linker → subproblem_agent → query_planner → sql_generator → sql_validator → sql_executor
                                                                          |
                                                                    (erro de execução)
                                                                          v
                                                            correction_planner → correction_sql → sql_validator
                                                                                                        |
                                                                                              (repete até 3 tentativas)
                                                                                                        v
                                                                                          response_synthesizer
```

| Camada | Tecnologia | Papel |
|---|---|---|
| Frontend | Next.js / TypeScript / Tailwind | Chat, SQL viewer, tabelas, gráficos, editor de metadados |
| API | FastAPI (SSE streaming) | Expõe o pipeline de agentes em tempo real |
| Orquestração | LangGraph (9 nós) | Schema linking → planejamento → geração → validação → execução → correção → resposta |
| LLMs | Gemini Flash (raciocínio) + Groq `openai/gpt-oss-120b` (correção) | Abstração via LangChain — troca de provedor sem mudar código |
| Metadados | PostgreSQL + pgvector | 9 tabelas de catálogo, embeddings via `intfloat/multilingual-e5-small` |
| Produção | PostgreSQL / MySQL / SQL Server (read-only) | Bancos alvo, plugáveis via interface |

Detalhamento de cada um dos 9 nós do agente, dos prompts reais usados e dos diagramas completos: Capítulo 3 e Apêndices A–C de [`tcc.docx`](tcc.docx).

---

## 5. Segurança

Três camadas independentes garantem que **nenhuma operação de escrita** chegue ao banco de produção:

1. **Validação sintática** (sem LLM) — `sqlparse` bloqueia 20 comandos perigosos (`INSERT`, `DROP`, `GRANT`...), exige início em `SELECT`/`WITH`, e detecta contrabando de escrita dentro de CTEs (ex.: `WITH x AS (DELETE ... RETURNING *) SELECT * FROM x`);
2. **Usuário de banco dedicado** com `GRANT SELECT` restrito;
3. **Timeout de 30s + limite de 500 linhas** por execução.

O caso de CTE gravável está coberto por teste automatizado e passou na validação (Seção 7).

---

## 6. Ambiente de validação

A plataforma foi validada sobre **SeguraPro**, um banco fictício de uma corretora de seguros com **15 tabelas** (`clients`, `brokers`, `policies`, `claims`, `commissions`, `payments`, entre outras), dados ambientados em Fortaleza-CE e 10 seguradoras brasileiras reais.

Ingestão de metadados medida diretamente no banco em execução:

| Métrica | Valor |
|---|---|
| Tabelas | 15 |
| Colunas | 138 |
| Sinônimos | 134 |
| Relacionamentos (FKs) | 20 |
| Regras de negócio | 12 |
| Embeddings vetoriais | 165 |

---

## 7. Resultados

**Testes automatizados:** 113/113 aprovados, incluindo o caso crítico de segurança (CTE + `DELETE`).

**Execução real de 10 perguntas** do domínio SeguraPro, via API (Gemini + Groq) e banco de produção reais:

| # | Pergunta | Correções necessárias | Tempo |
|---|---|---|---|
| 1 | Quantos clientes ativos temos? | 0 | 33,15 s |
| 2 | Quais corretores estão ativos? | 0 | 23,74 s |
| 3 | Total de prêmios das apólices vigentes | 0 | 27,59 s |
| 4 | Sinistros em análise | 0 | 31,03 s |
| 5 | Total de prêmios por corretor (ativas) | 0 | 34,07 s |
| 6 | Apólices vigentes por seguradora | 0 | 36,65 s |
| 7 | Sinistralidade por ramo de seguro | 0 | 50,96 s |
| 8 | Parcelas em atraso + cliente | 0 | 29,12 s |
| 9 | Corretores com comissão pendente > R$ 1.000 | 0 | 29,19 s |
| 10 | Menor prêmio médio em seguro auto | 0 | 30,90 s |

**Nas 10 execuções, o pipeline gerou SQL executável sem precisar do laço de correção em nenhum caso** (`correction_count = 0` em todas). Tempo médio de resposta: **~32,6 s** (mín. 23,74 s, máx. 50,96 s).

Duas observações qualitativas registradas na íntegra em [`tcc.docx`](tcc.docx), Seção 4.4: três respostas vieram vazias por uma defasagem temporal nos dados sintéticos (não um erro de geração de SQL), e uma resposta produziu um valor estatístico atípico decorrente do tamanho reduzido do dataset de teste.

---

## 8. Limitações e trabalhos futuros

| Limitação | Encaminhamento |
|---|---|
| Dataset sintético few-shot (DANKE) não foi implementado — `scripts/generate_synthetic.py` é um placeholder | Trabalho futuro: implementar o gerador e medir seu impacto no schema linking |
| Sem métricas quantitativas formais (F1-score de schema linking, exact match) | Trabalho futuro: construir conjunto de teste rotulado |
| Validação restrita a um único domínio (SeguraPro), volume de dados reduzido | Trabalho futuro: ampliar para múltiplos domínios |
| Suporte a Oracle avaliado, não implementado | Trabalho futuro: quarto SGBD suportado |
| Episódio de correção automática relatado pelo autor não foi reproduzido em log | Trabalho futuro: registrar sistematicamente os acionamentos do laço de correção |

Discussão completa: Seções 4.8 e 5.3 de [`tcc.docx`](tcc.docx).

---

## 9. Estrutura do repositório

```
rag-sql/               
├── backend/                  # API FastAPI + pipeline de agentes (LangGraph)
│   └── app/agents/           # Os 9 nós do pipeline (código citado no Capítulo 3)
├── frontend/                 # Interface web (Next.js)
├── database/                 # Schema do banco de teste SeguraPro
└── docs/                     # Especificações de cada fase de desenvolvimento
```

---

## 10. Como executar


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

Sobe backend, frontend e os dois bancos PostgreSQL (produção de teste + metadados/pgvector). Interface em `http://localhost:3000`. Instruções detalhadas de configuração (chaves de API, variáveis de ambiente): [`README.md`](README.md).

---

## 11. Referências principais

Lista completa (16 itens, ABNT NBR 6023) no capítulo de Referências de [`tcc.docx`](tcc.docx). Destaques:

- CHATURVEDI, S.; CHADHA, A.; BINDSCHAEDLER, L. **SQL-of-Thought**: Multi-agentic Text-to-SQL with Guided Error Correction. arXiv:2509.00581v2, 2025.
- NASCIMENTO, E. R. et al. **LLM-based strategy for the text-to-SQL task leveraging knowledge graphs and dynamic few-shot examples**. Data & Knowledge Engineering, v. 164, 102580, 2026.
- SHEN, Y. et al. **Towards Understanding the Errors in NL2SQL**. arXiv preprint, 2024.
- YU, T. et al. **Spider**: A large-scale human-labeled dataset for complex and cross-domain semantic parsing and text-to-SQL task. In: EMNLP, 2018.
- LEWIS, P. et al. **Retrieval-augmented generation for knowledge-intensive NLP tasks**. In: NeurIPS, 2020.
