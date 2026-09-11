## Tarefa: Trocar modelo de embeddings para multilíngue e ajustes finais

A busca semântica em português está fraca porque o `all-MiniLM-L6-v2` é focado em inglês. Preciso trocar para `intfloat/multilingual-e5-small` que suporta português nativamente, tem as mesmas 384 dimensões (não precisa mudar nada no pgvector) e roda em CPU (~120MB).

### 1. Trocar o modelo de embeddings

No `app/metadata/embeddings.py`:

- Alterar o modelo padrão de `all-MiniLM-L6-v2` para `intfloat/multilingual-e5-small`
- O `multilingual-e5-small` exige prefixos para funcionar bem:
  - Textos que são **queries** (pergunta do usuário na busca) devem ser prefixados com `"query: "`
  - Textos que são **passages** (conteúdo indexado — descrições de tabelas, colunas, regras) devem ser prefixados com `"passage: "`
- Adaptar o método `generate()` para aceitar um parâmetro `prefix: str = "passage: "` e prepender automaticamente
- Adaptar o método `search()` para usar `prefix="query: "` ao gerar o embedding da query do usuário
- Na ingestão (quando geramos embeddings dos metadados), usar `prefix="passage: "`

Exemplo de como ficaria:

```python
def generate(self, texts: list[str], prefix: str = "passage: ") -> list[list[float]]:
    prefixed = [f"{prefix}{t}" for t in texts]
    embeddings = self.model.encode(prefixed, normalize_embeddings=True)
    return embeddings.tolist()

async def search(self, query: str, ...) -> list[SearchResult]:
    query_embedding = self.generate([query], prefix="query: ")[0]
    # ... resto da busca por cosine distance no pgvector
```

### 2. Atualizar config e .env

- Em `app/core/config.py` e `.env.example`, trocar o default de `EMBEDDING_MODEL` para `intfloat/multilingual-e5-small`
- Atualizar o `.env` também

### 3. Regenerar todos os embeddings

Depois de trocar o modelo, os embeddings existentes no banco de metadados ficam incompatíveis (foram gerados com outro modelo). O script de ingestão precisa regenerá-los.

```bash
cd backend && uv run python -m scripts.ingest_metadata
```

Isso deve apagar os embeddings antigos e gerar novos com o modelo correto (o script já é idempotente — ele limpa e recria).

### 4. Atualizar testes

Em `test_embeddings.py`:
- A dimensão continua 384, então a validação de dimensão não muda
- Garantir que os textos de teste estejam em português para validar a melhoria
- Se houver testes que passam o texto direto pro `generate()`, adicionar o prefix correto

### 5. Validar a melhoria

Rodar o script de ingestão e depois testar as mesmas 3 buscas que falharam antes:

```python
await embedding_service.search("valor total dos prêmios das apólices vigentes")
await embedding_service.search("sinistros em análise este mês")
await embedding_service.search("comissões pendentes por corretor")
```

Me reportar os resultados de cada busca (top 5 de cada) para confirmar que a qualidade melhorou.

### 6. Verificação do pgAdmin

Confirmar que os bancos estão acessíveis via pgAdmin usando `host.docker.internal` como Host:
- Produção: host=`host.docker.internal`, port=`5432`, db=`segurapro`, user=`segurapro_admin`, password=`segurapro_dev`
- Metadados: host=`host.docker.internal`, port=`5433`, db=`querymind_metadata`, user=`querymind`, password=`querymind_dev`

### Restrições:
- Manter as mesmas 384 dimensões — não mudar nada no schema do pgvector
- Seguir convenções do CLAUDE.md
- Não quebrar os testes existentes
- Se o download do modelo `multilingual-e5-small` for lento, é normal (~120MB na primeira vez)