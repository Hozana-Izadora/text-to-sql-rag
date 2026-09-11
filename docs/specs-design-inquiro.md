# Inquiro — Identidade Visual e Design System

## Conceito da marca

**Inquiro** vem do latim *inquirere* — investigar a fundo, buscar a verdade dentro dos dados. A marca transmite profundidade intelectual, precisao e confianca. Nao e um chatbot generico: e uma ferramenta de investigacao que traduz a linguagem humana para a linguagem dos dados.

**Personalidade da marca:**
- Inteligente, nao intimidadora
- Preciso, nao burocratico
- Confiavel, nao frio
- Sofisticado, nao complexo

**Tagline:** "Da pergunta ao insight."

---

## Logotipo

O logotipo combina o nome "inquiro" em tipografia minuscula com um icone que representa "investigacao + dados". O icone e uma lupa estilizada cujo circulo e formado por um no de grafo (conexoes entre tabelas), com o cabo sutilmente curvado como um ponto de interrogacao.

Variacoes obrigatorias: horizontal colorida (header), horizontal branca (dark mode), icone colorido (favicon), icone monocromatica (marca d'agua em relatorios).

---

## Paleta de cores

### Filosofia

Dark-first. Ferramentas de dados sao usadas em sessoes longas. O modo escuro e o padrao; o modo claro e a alternativa. Nunca usar preto puro (#000) - usar cinzas suaves na faixa #0E a #1A.

### Cores de base

| Token | Dark | Light | Uso |
|---|---|---|---|
| bg-base | #0F1117 | #FFFFFF | Fundo da aplicacao |
| bg-surface | #161922 | #F8F9FB | Cards, paineis, modais |
| bg-elevated | #1E2130 | #F0F1F5 | Dropdowns, elementos elevados |
| border-subtle | #2A2D3A | #E2E4EA | Bordas de cards |
| border-strong | #3D4155 | #C8CCD8 | Bordas de inputs em foco |
| text-primary | #E4E5EA | #1A1C23 | Texto principal |
| text-secondary | #8B8FA3 | #5A5E72 | Texto secundario |
| text-muted | #5A5E72 | #8B8FA3 | Placeholders, timestamps |

### Cor de destaque (Accent)

| Token | Hex | Uso |
|---|---|---|
| accent-primary | #6C5CE7 | Botoes primarios, links, foco |
| accent-hover | #7D6FF0 | Hover de botoes e links |
| accent-subtle | #6C5CE720 | Backgrounds de tags |
| accent-text | #A294F9 | Texto de destaque em dark mode |

O violeta (#6C5CE7) transmite inteligencia e sofisticacao sem ser corporativo demais (azul) nem agressivo (vermelho). E a cor mais associada a IA no imaginario SaaS atual (Linear, Cursor, Anthropic).

### Cores semanticas

| Token | Hex | Uso |
|---|---|---|
| success | #00C48C | SQL executado, conexao OK |
| warning | #FFB020 | Parcelas em atraso, truncado |
| error | #FF4757 | Erro de execucao, conexao falhou |
| info | #3B82F6 | Status do pipeline, dicas |

### Cores de graficos

Paleta de 6 cores para Recharts (funciona em dark e light):
- #6C5CE7 (violeta/accent)
- #00C48C (esmeralda)
- #FFB020 (ambar)
- #3B82F6 (azul)
- #FF6B81 (coral)
- #00D2D3 (ciano)

---

## Tipografia

### Fonte principal: Inter

| Elemento | Peso | Tamanho | Line-height | Uso |
|---|---|---|---|---|
| heading-1 | 600 | 24px | 32px | Titulo de pagina |
| heading-2 | 600 | 18px | 26px | Titulo de secao |
| heading-3 | 500 | 15px | 22px | Subtitulos |
| body | 400 | 14px | 22px | Texto geral |
| body-small | 400 | 13px | 20px | Texto secundario |
| caption | 400 | 12px | 16px | Labels, timestamps |
| overline | 500 | 11px | 14px | Categorias, tags |

### Fonte monospace: JetBrains Mono

| Elemento | Peso | Tamanho | Uso |
|---|---|---|---|
| code-block | 400 | 13px | SQL viewer, blocos de codigo |
| code-inline | 400 | 12px | Nomes de tabelas inline |

---

## Componentes

### Chat bubbles

Mensagem do usuario:
- Background: accent-primary (#6C5CE7)
- Texto: #FFFFFF
- Raio borda: 16px 16px 4px 16px (canto inferior direito achatado)
- Padding: 12px 16px
- Max-width: 75%
- Alinhamento: direita

Mensagem do assistant:
- Background: bg-surface (#161922)
- Borda: 1px solid border-subtle
- Texto: #E4E5EA
- Raio borda: 16px 16px 16px 4px (canto inferior esquerdo achatado)
- Padding: 16px 20px
- Max-width: 85%
- Alinhamento: esquerda

### SQL Viewer

- Background: #0D1117 (mais escuro que bg-base)
- Borda: 1px solid border-subtle
- Raio borda: 8px
- Fonte: JetBrains Mono 13px
- Syntax highlighting:
  - Keywords (SELECT, FROM, JOIN, WHERE): #FF7B72
  - Strings ('active'): #A5D6FF
  - Numeros: #79C0FF
  - Funcoes (SUM, ROUND, COUNT): #D2A8FF
  - Aliases (AS): #7EE787
  - Comentarios: #8B949E
- Botao copiar: icone clipboard no canto superior direito
- Estado padrao: colapsado

O SQL viewer permanece com fundo escuro mesmo em light mode (convencao de editores de codigo).

### DataTable

- Header: bg-elevated, texto caption uppercase #8B8FA3
- Linhas: texto #E4E5EA, hover bg-elevated
- Valores numericos: alinhados a direita, JetBrains Mono
- Valores monetarios: cor success (#00C48C)
- Valores nulos: #5A5E72, italico, "-"
- Overflow horizontal com scroll em mobile
- Badge "Resultados truncados" com background warning

### Botoes

| Tipo | Background | Texto | Uso |
|---|---|---|---|
| Primary | accent-primary | #FFFFFF | Enviar, Salvar, Conectar |
| Secondary | transparent | accent-text | Cancelar, Voltar, Exportar |
| Ghost | transparent | #8B8FA3 | Editar, Copiar |
| Danger | #FF4757 | #FFFFFF | Remover conexao |

Todos: raio 8px, padding 8px 16px, transicao 150ms.

### Connection Card

- Background: bg-surface, borda border-subtle
- Raio: 12px, padding: 20px
- Hover: borda border-strong, shadow sutil
- Icone por tipo: PostgreSQL (#336791), MySQL (#4479A1), SQL Server (#CC2927), Oracle (#F80000)
- Acoes: botoes ghost + botao accent "Abrir chat"

### Status Indicator

- Tres dots animados (bounce sequencial, 1.2s loop)
- Texto body-small, accent-text
- Background accent-subtle
- Exemplos: "Identificando tabelas...", "Executando SQL..."

### Input Bar

- Background: bg-surface, borda border-subtle
- Raio: 12px, foco: borda accent-primary
- Placeholder: "Pergunte sobre seus dados..." (#5A5E72)
- Botao enviar: accent-primary, icone Send, 40x40px
- Textarea auto-resize: min 44px, max 120px

---

## Layout das paginas

### Pagina de conexoes (/connections)

Header com logo + toggle dark/light. Titulo "Suas conexoes" + botao "+ Nova conexao". Grid responsivo de connection cards. Card "+" com borda tracejada sempre por ultimo.

### Pagina de chat (/connections/[id])

Header: logo + seletor de conexao (dropdown) + link para metadados. Area de chat com mensagem de boas-vindas centralizada (logo, tagline, sugestoes clicaveis). Input fixo no bottom. Chat com max-width 720px centralizado em desktop.

### Editor de metadados (/connections/[id]/metadata)

Sidebar esquerda com lista de tabelas. Painel direito com detalhes: descricao editavel, sinonimos como chips removiveis, colunas com tipos e descricoes, enum values editaveis, regras de negocio. Edicao inline com feedback "Salvo".

---

## Micro-interacoes

| Elemento | Animacao | Duracao |
|---|---|---|
| Mensagem nova | Fade-in + slide-up 12px | 200ms ease-out |
| Status dots | Bounce sequencial | 1.2s loop |
| SQL viewer expand | Height ease | 250ms |
| Botao enviar loading | Icone rota 360 | 800ms linear |
| Card hover | Border transition | 150ms |
| Toast "Salvo" | Fade-in, 2s, fade-out | 200ms + 200ms |
| Chart bars | Crescem de 0 | 600ms ease-out |
| Chip add | Scale 0 a 1 + bounce | 300ms spring |
| Modal open | Backdrop fade + scale 0.95 a 1 | 200ms |

---

## Responsividade

| Breakpoint | Layout |
|---|---|
| < 640px (mobile) | Chat full-width, sidebar vira drawer |
| 640-1024px (tablet) | Grid 2 colunas, sidebar colapsavel |
| > 1024px (desktop) | Layout completo, sidebar fixa, chat max-width 720px |

---

## Acessibilidade

- Contrast ratio minimo: 4.5:1 (WCAG AA)
- Focus visible: outline 2px solid accent-primary, offset 2px
- Aria-labels em botoes com icone-only
- prefers-reduced-motion respeitado
- Chat com role="log", aria-live="polite"
- Navegacao por teclado completa

---

## Decisoes de design

Por que dark-first? Ferramentas de dados sao usadas em sessoes longas. Dark mode reduz fadiga visual e e o padrao esperado por power users.

Por que violeta como accent? Azul e generico. Verde conflita com a cor semantica de sucesso. Violeta transmite inteligencia e investigacao, alinhado com "Inquiro".

Por que Inter + JetBrains Mono? Inter e a fonte mais legivel para interfaces de dados. JetBrains Mono tem ligatures que melhoram SQL. Ambas open-source.

Por que SQL viewer escuro em light mode? Convencao de VS Code e GitHub. Codigo em fundo escuro e mais legivel.
