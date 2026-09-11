# Fase 4 — Outputs Multimodais: Gráficos, Relatórios .docx e .pdf

## Objetivo

Adicionar ao sistema a capacidade de gerar outputs visuais e documentais a partir dos dados retornados pelo pipeline. O usuário pode pedir um gráfico, um relatório Word ou um PDF diretamente no chat, e recebe o resultado inline ou como arquivo para download.

Ao final desta fase, o sistema suporta:
- "Mostre um gráfico de prêmios por corretor" → gráfico interativo inline no chat
- "Gere um relatório em Word dos sinistros abertos" → arquivo .docx para download
- "Quero um PDF com o resumo de produção mensal" → arquivo .pdf para download

---

## Visão geral do fluxo

```
Pergunta do usuário
    │
    ├─── Pipeline Text-to-SQL (Fase 2) ──→ dados + resposta NL
    │
    ▼
Classifier de output (novo)
    │
    ├── "gráfico" / "mostre" / "chart" ──→ Chart Generator ──→ JSON de chart inline
    ├── "relatório word" / "docx" ───────→ DocxGenerator ───→ arquivo .docx
    ├── "relatório pdf" / "pdf" ─────────→ PdfGenerator ────→ arquivo .pdf
    └── (nenhum) ────────────────────────→ resposta NL apenas (Fase 3)
```

O classifier roda **depois** do pipeline retornar os dados. Ele não é um agente LangGraph — é uma classificação simples que detecta se o usuário pediu um output especial.

---

## Entregáveis

### E1. Output classifier

Criar em `app/export/classifier.py`:

Detecta o tipo de output solicitado pelo usuário. Sem LLM — é matching de keywords.

```python
from enum import Enum

class OutputType(str, Enum):
    TEXT = "text"           # Resposta NL apenas (padrão)
    CHART = "chart"         # Gráfico inline
    DOCX = "docx"           # Relatório Word
    PDF = "pdf"             # Relatório PDF

def classify_output(question: str) -> OutputType:
    """
    Classifica o tipo de output desejado baseado em keywords.

    Keywords para CHART:
      gráfico, grafico, chart, visualize, visualizar, mostre,
      mostra, plotar, plot, barras, pizza, linha, histograma

    Keywords para DOCX:
      word, docx, documento word, relatório word, relatorio word

    Keywords para PDF:
      pdf, relatório pdf, relatorio pdf

    Se múltiplos matcham, prioridade: DOCX > PDF > CHART > TEXT
    Se nenhum matcha: TEXT
    """
```

---

### E2. Chart generator — backend

Criar em `app/export/chart_generator.py`:

Recebe os dados do pipeline e gera uma especificação de gráfico que o frontend renderiza.

```python
class ChartSpec(BaseModel):
    chart_type: str          # bar, line, pie, horizontal_bar
    title: str
    x_label: str
    y_label: str
    x_data: list[str]        # labels do eixo X
    series: list[ChartSeries]

class ChartSeries(BaseModel):
    name: str
    values: list[float]
    color: str | None = None  # hex opcional

async def generate_chart_spec(
    question: str,
    columns: list[str],
    rows: list[dict],
    response_text: str,
) -> ChartSpec:
    """
    Usa LLM para decidir:
    1. Qual tipo de gráfico (bar, line, pie)
    2. Qual coluna é o eixo X (categórica)
    3. Qual coluna é o eixo Y (numérica)
    4. Título e labels
    5. Se precisa agrupar/pivotar os dados

    Prompt:
    "Dados os dados abaixo e a pergunta do usuário, defina a melhor
     visualização. Retorne JSON no formato ChartSpec."

    Fallback: se a LLM falhar, usar heurística:
    - Primeira coluna string → eixo X
    - Primeira coluna numérica → eixo Y
    - Se <= 8 categorias → bar chart
    - Se > 8 categorias → horizontal bar
    - Se dados temporais → line chart
    """
```

O backend NÃO gera a imagem do gráfico. Ele retorna o `ChartSpec` como JSON, e o frontend renderiza com Recharts. Isso evita dependência de matplotlib/plotly no backend e mantém os gráficos interativos.

---

### E3. Chart renderer — frontend

Criar em `src/components/data/ChartRenderer.tsx`:

Renderiza o `ChartSpec` recebido via SSE usando Recharts.

```typescript
interface ChartSpec {
  chartType: "bar" | "line" | "pie" | "horizontal_bar";
  title: string;
  xLabel: string;
  yLabel: string;
  xData: string[];
  series: { name: string; values: number[]; color?: string }[];
}
```

**Comportamentos:**
- `bar` → `<BarChart>` do Recharts com barras verticais
- `horizontal_bar` → `<BarChart layout="vertical">`
- `line` → `<LineChart>` com pontos e linhas
- `pie` → `<PieChart>` com labels e percentuais
- Responsivo via `<ResponsiveContainer>`
- Tooltip ao passar o mouse com valores formatados (R$ para monetário)
- Legenda automática se houver mais de uma série
- Cores padrão consistentes (paleta de 6 cores que funcione em claro/escuro)

**Paleta de cores sugerida:**
```typescript
const CHART_COLORS = [
  "#4F46E5", // indigo
  "#059669", // emerald
  "#D97706", // amber
  "#DC2626", // red
  "#7C3AED", // violet
  "#0891B2", // cyan
];
```

---

### E4. Integração chart no fluxo SSE

Adicionar novo evento SSE no stream:

```
data: {"event": "chart", "data": { ...ChartSpec JSON... }}\n\n
```

O evento `chart` é emitido **depois** do `answer` e **antes** do `done`.

Atualizar `app/api/streaming.py`:
```python
# Após o response_synthesizer
output_type = classify_output(question)
if output_type == OutputType.CHART and execution_result:
    chart_spec = await generate_chart_spec(question, columns, rows, response_text)
    yield sse_event("chart", chart_spec.model_dump())
```

Atualizar `src/lib/types.ts`:
```typescript
export interface ChatMessage {
  // ... campos existentes
  chart?: ChartSpec;  // novo
}
```

Atualizar `MessageBubble.tsx` para renderizar `<ChartRenderer>` quando `message.chart` existir, abaixo da resposta NL e acima da DataTable.

---

### E5. Docx generator

Criar em `app/export/docx_generator.py`:

Gera relatórios Word (.docx) usando `python-docx`.

```python
from pathlib import Path

async def generate_docx(
    question: str,
    response_text: str,
    sql: str,
    columns: list[str],
    rows: list[dict],
    metadata: dict,
) -> Path:
    """
    Gera um relatório .docx com:

    1. CABEÇALHO
       - Logo placeholder (retângulo com "SeguraPro")
       - Título: "Relatório de Dados"
       - Subtítulo: data/hora de geração

    2. SEÇÃO: Consulta
       - "Pergunta:" em negrito + a pergunta do usuário
       - "SQL executado:" em negrito + bloco monospace com o SQL

    3. SEÇÃO: Resultados
       - Parágrafo com a resposta em linguagem natural
       - Tabela formatada com os dados:
         - Cabeçalho com fundo cinza escuro, texto branco
         - Linhas alternando branco e cinza claro (zebra)
         - Valores numéricos alinhados à direita
         - Formatação: R$ para monetários, dd/mm/aaaa para datas

    4. RODAPÉ
       - "Gerado por QueryMind em {data}" + número da página

    Retorna o Path do arquivo gerado em /tmp/exports/
    Nome do arquivo: relatorio_{timestamp}.docx
    """
```

**Formatação da tabela:**
- Larguras de coluna proporcionais (colunas numéricas mais estreitas)
- Máximo de 100 linhas na tabela (com nota "Resultados truncados" se necessário)
- Font: Calibri 11pt para texto, Consolas 9pt para SQL

**Dependência:** `python-docx` (já no pyproject.toml da Fase 1)

---

### E6. PDF generator

Criar em `app/export/pdf_generator.py`:

Gera relatórios PDF usando WeasyPrint (HTML/CSS → PDF).

```python
async def generate_pdf(
    question: str,
    response_text: str,
    sql: str,
    columns: list[str],
    rows: list[dict],
    metadata: dict,
    chart_spec: ChartSpec | None = None,
) -> Path:
    """
    Gera um relatório .pdf com:

    1. Gera um HTML intermediário com o mesmo conteúdo do .docx
    2. Se houver chart_spec, renderiza o gráfico como SVG inline no HTML
    3. Converte HTML → PDF via WeasyPrint

    Template HTML:
    - CSS com @page para margens, cabeçalho/rodapé
    - Tabela com estilos inline (WeasyPrint não suporta CSS externo)
    - Gráfico SVG embutido (se houver)
    - Código SQL em bloco <pre> com fundo escuro

    Retorna o Path do arquivo em /tmp/exports/
    Nome do arquivo: relatorio_{timestamp}.pdf
    """
```

**Para o gráfico no PDF:**
O frontend renderiza com Recharts (HTML Canvas/SVG), mas no PDF não temos browser. Opções:
- Gerar o gráfico como SVG puro via matplotlib no backend (apenas para PDF)
- Usar plotly com `plotly.io.to_image()` gerando PNG

Abordagem recomendada: usar matplotlib para gerar SVG string in-memory (sem salvar arquivo) e embutir no HTML antes de converter com WeasyPrint. Matplotlib roda em CPU sem problemas.

```python
import matplotlib
matplotlib.use("Agg")  # backend sem GUI
import matplotlib.pyplot as plt
import io

def chart_to_svg(chart_spec: ChartSpec) -> str:
    """Converte ChartSpec em string SVG usando matplotlib."""
    fig, ax = plt.subplots(figsize=(8, 4))
    # ... renderizar conforme chart_type
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue().decode("utf-8")
```

**Dependência:** adicionar `weasyprint` e `matplotlib` ao pyproject.toml.

**Nota sobre WeasyPrint:** precisa de dependências de sistema (pango, cairo). No Dockerfile, adicionar:
```dockerfile
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    libffi-dev libcairo2 && rm -rf /var/lib/apt/lists/*
```

---

### E7. Endpoint de download

Criar em `app/api/routes.py`:

```python
@router.post("/api/export")
async def export_report(request: ExportRequest) -> FileResponse:
    """
    Gera e retorna arquivo para download.

    Request:
    {
      "format": "docx" | "pdf",
      "question": "...",
      "response_text": "...",
      "sql": "...",
      "columns": [...],
      "rows": [...],
      "metadata": {...},
      "chart_spec": {...} | null
    }

    Response: FileResponse com Content-Disposition attachment
    """
```

**Schemas:**
```python
class ExportRequest(BaseModel):
    format: Literal["docx", "pdf"]
    question: str
    response_text: str
    sql: str
    columns: list[str]
    rows: list[dict]
    metadata: dict
    chart_spec: ChartSpec | None = None
```

**Limpeza de arquivos:** os arquivos gerados em `/tmp/exports/` são temporários. Adicionar cleanup automático de arquivos com mais de 1 hora.

---

### E8. Botões de export no frontend

Atualizar `src/components/chat/MessageBubble.tsx`:

Quando a mensagem do assistant tiver dados (`rows` não vazio), mostrar botões de export abaixo da DataTable:

```
┌────────────────────────────────────────┐
│  [resposta NL]                         │
│  [gráfico se houver]                   │
│  [tabela de dados]                     │
│                                        │
│  ┌──────────────┐ ┌─────────────────┐  │
│  │ 📄 Baixar Word │ │ 📑 Baixar PDF  │  │
│  └──────────────┘ └─────────────────┘  │
└────────────────────────────────────────┘
```

**Comportamento dos botões:**
1. Ao clicar, envia POST para `/api/export` com os dados da mensagem
2. Mostra loading indicator no botão ("Gerando...")
3. Recebe o arquivo como blob
4. Trigger download automático no browser via `URL.createObjectURL`
5. Nome do arquivo: `relatorio_YYYYMMDD_HHmmss.docx` ou `.pdf`

Criar em `src/components/data/ExportButtons.tsx`:

```typescript
interface ExportButtonsProps {
  question: string;
  responseText: string;
  sql: string;
  columns: string[];
  rows: Record<string, unknown>[];
  metadata: ChatMessage["metadata"];
  chartSpec?: ChartSpec;
}
```

---

### E9. Integração com output classifier no streaming

Atualizar `app/api/streaming.py` para o fluxo completo:

```python
async def stream_pipeline(question: str):
    # ... pipeline existente (Fase 3) ...

    # Após o response_synthesizer completar:
    output_type = classify_output(question)

    if output_type == OutputType.CHART and state.get("execution_result"):
        chart_spec = await generate_chart_spec(
            question=question,
            columns=state["columns"],
            rows=state["execution_result"],
            response_text=state["response_text"],
        )
        yield sse_event("chart", chart_spec.model_dump())

    # Para DOCX/PDF: não gerar automaticamente
    # O frontend mostra os botões de export e o usuário decide
    # A geração acontece sob demanda via POST /api/export

    yield sse_event("done", None)
```

**Decisão importante:** gráficos são inline (gerados automaticamente quando o usuário pede). Relatórios .docx/.pdf são sob demanda (botão de download), porque gerar um arquivo a cada pergunta seria desperdício — o usuário decide se quer exportar.

Porém: se o usuário pedir explicitamente ("gere um PDF dos sinistros"), o classifier detecta PDF e o streaming pode incluir um evento especial:

```
data: {"event": "export_ready", "data": {"format": "pdf", "auto": true}}\n\n
```

O frontend interpreta esse evento e dispara o download automaticamente.

---

### E10. Template HTML para PDF

Criar em `app/export/templates/report.html`:

Template Jinja2 usado pelo PDF generator.

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    @page {
      size: A4;
      margin: 2cm;
      @bottom-center {
        content: "Gerado por QueryMind — Página " counter(page);
        font-size: 9px;
        color: #666;
      }
    }
    body { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 11pt; color: #1a1a1a; }
    h1 { font-size: 18pt; color: #1e3a5f; margin-bottom: 4px; }
    .subtitle { font-size: 10pt; color: #666; margin-bottom: 24px; }
    .section-title { font-size: 13pt; font-weight: 600; color: #1e3a5f; border-bottom: 2px solid #e5e7eb; padding-bottom: 4px; margin: 20px 0 8px; }
    .question { background: #f3f4f6; padding: 10px 14px; border-radius: 6px; font-style: italic; }
    pre.sql { background: #1e293b; color: #a5f3fc; padding: 12px; border-radius: 6px; font-size: 9pt; overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 10pt; }
    th { background: #1e3a5f; color: white; padding: 8px 10px; text-align: left; }
    td { padding: 6px 10px; border-bottom: 1px solid #e5e7eb; }
    tr:nth-child(even) td { background: #f9fafb; }
    .numeric { text-align: right; font-family: "Courier New", monospace; }
    .chart-container { margin: 16px 0; text-align: center; }
    .truncated { font-size: 9pt; color: #666; font-style: italic; margin-top: 4px; }
  </style>
</head>
<body>
  <h1>Relatório de Dados</h1>
  <div class="subtitle">SeguraPro Corretora · {{ generated_at }}</div>

  <div class="section-title">Consulta</div>
  <div class="question">{{ question }}</div>

  <div class="section-title">SQL Executado</div>
  <pre class="sql">{{ sql }}</pre>

  <div class="section-title">Análise</div>
  <p>{{ response_text }}</p>

  {% if chart_svg %}
  <div class="section-title">Visualização</div>
  <div class="chart-container">{{ chart_svg | safe }}</div>
  {% endif %}

  <div class="section-title">Dados ({{ row_count }} registros{% if truncated %}, truncado{% endif %})</div>
  <table>
    <thead><tr>{% for col in columns %}<th{% if col.is_numeric %} class="numeric"{% endif %}>{{ col.name }}</th>{% endfor %}</tr></thead>
    <tbody>
    {% for row in rows %}
      <tr>{% for col in columns %}<td{% if col.is_numeric %} class="numeric"{% endif %}>{{ row[col.key] }}</td>{% endfor %}</tr>
    {% endfor %}
    </tbody>
  </table>
  {% if truncated %}<div class="truncated">Exibindo os primeiros 100 registros de {{ row_count }}.</div>{% endif %}
</body>
</html>
```

---

### E11. Dependências adicionais

Adicionar ao `pyproject.toml`:

```toml
"weasyprint>=62.0",
"matplotlib>=3.9",
"jinja2>=3.1",
```

Atualizar `backend/Dockerfile` com as dependências de sistema do WeasyPrint:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    libffi-dev libcairo2 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
```

No `frontend`, Recharts já foi instalado na Fase 3. Verificar que está disponível.

---

### E12. Testes

| Arquivo | O que testa |
|---|---|
| `test_classifier.py` | "gráfico de prêmios" → CHART. "relatório word" → DOCX. "gere um pdf" → PDF. "quantos clientes?" → TEXT. |
| `test_chart_generator.py` | Dados com 1 coluna string + 1 numérica → bar chart. Dados temporais → line chart. ChartSpec JSON válido. |
| `test_docx_generator.py` | Gera arquivo .docx que abre sem erro. Contém tabela com colunas certas. Contém a pergunta e o SQL. |
| `test_pdf_generator.py` | Gera arquivo .pdf que abre sem erro. Contém texto da resposta NL. |
| `test_export_api.py` | POST /api/export com format=docx retorna arquivo com Content-Type correto. POST com format=pdf idem. |

---

## Critérios de aceite

A Fase 4 está completa quando:

1. "Mostre um gráfico dos prêmios por corretor" renderiza um bar chart interativo no chat
2. "Quantos sinistros por status?" renderiza um gráfico adequado (bar ou pie)
3. Clicar "Baixar Word" gera e baixa um .docx com cabeçalho, pergunta, SQL, resposta NL e tabela formatada
4. Clicar "Baixar PDF" gera e baixa um .pdf com o mesmo conteúdo + gráfico SVG se aplicável
5. O classifier não gera gráfico quando o usuário não pediu
6. Perguntas sem dados (resultado vazio) não mostram botões de export
7. Os gráficos são responsivos e legíveis em desktop e mobile
8. Todos os testes passam
9. O código segue as convenções do CLAUDE.md

---

## Decisões técnicas

**Por que gráficos no frontend (Recharts) e não no backend (matplotlib)?**
Recharts renderiza gráficos interativos (tooltip, hover, resize). Matplotlib geraria imagens estáticas que precisariam ser enviadas como base64 — mais pesadas, sem interatividade. O backend só envia a especificação (JSON com tipo, dados, labels), e o frontend renderiza. Exceção: para PDFs, usamos matplotlib no backend porque o WeasyPrint precisa de SVG/imagem estática.

**Por que não gerar relatórios automaticamente?**
Gerar .docx/.pdf a cada pergunta seria desperdício de processamento. O fluxo ideal é: o usuário vê a resposta no chat, decide se quer exportar, e clica o botão. Exceção: se pedir explicitamente ("gere um PDF"), o sistema detecta e oferece o download diretamente.

**Por que WeasyPrint e não ReportLab?**
WeasyPrint converte HTML/CSS em PDF. Isso significa que o template é HTML legível, fácil de manter e estilizar com CSS. ReportLab é mais poderoso para layouts complexos, mas requer código Python imperativo para cada elemento — mais difícil de manter. Para relatórios tabulares como os nossos, HTML/CSS é suficiente e muito mais produtivo.

**Por que cleanup de arquivos temporários?**
Os .docx/.pdf são gerados em `/tmp/exports/`. Sem cleanup, acumulariam indefinidamente. Um background task que apaga arquivos com mais de 1 hora resolve sem complexidade.
