export type MessageRole = "user" | "assistant";

export type ColumnFormat = "currency" | "integer" | "decimal_number" | "date" | "datetime" | "text";

export interface ChatMessageMetadata {
  [key: string]: unknown;
  rowCount: number;
  truncated: boolean;
  tablesUsed: string[];
  columnFormats?: Record<string, ColumnFormat>;
}

export type ChartType = "bar" | "line" | "pie" | "horizontal_bar";

export interface ChartSeries {
  name: string;
  values: number[];
  color?: string;
  valueFormat?: "currency" | "number" | null;
  sourceColumn?: string | null;
}

export interface ChartSpec {
  chartType: ChartType;
  title: string;
  xLabel: string;
  yLabel: string;
  xData: string[];
  series: ChartSeries[];
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  /** Só preenchido em mensagens do assistant — a pergunta do usuário que a originou,
   * necessária pro export (/api/export precisa da pergunta original). */
  question?: string;
  sql?: string;
  columns?: string[];
  rows?: Record<string, unknown>[];
  metadata?: ChatMessageMetadata;
  chart?: ChartSpec;
  status?: string;
  isStreaming?: boolean;
  isError?: boolean;
}

export interface SSEEvent {
  event: string;
  data: unknown;
}

export interface ExportReadyPayload {
  format: "docx" | "pdf";
  auto: boolean;
}

// --- Conexões e metadados (Fase 5) ---

export type DbType = "postgresql" | "mysql" | "sqlserver" | "oracle" | "sqlite";

/** Resposta da API — snake_case, sem `password`. */
export interface Connection {
  id: string;
  name: string;
  db_type: DbType;
  host: string;
  port: number;
  database_name: string;
  username: string;
  ssl_enabled: boolean;
  schema_name: string;
  is_active: boolean;
  table_count: number | null;
  last_introspected_at: string | null;
  created_at: string;
}

export interface ConnectionDetail extends Connection {
  column_count: number;
}

/** Corpo de POST /api/connections e POST /api/connections/test. */
export interface ConnectionInput {
  name: string;
  db_type: DbType;
  host: string;
  port: number;
  database_name: string;
  username: string;
  password: string;
  ssl_enabled: boolean;
  schema_name: string;
}

export interface ConnectionTestResult {
  success: boolean;
  message: string;
  db_version: string | null;
  latency_ms: number | null;
}

export interface IntrospectionResult {
  tables: number;
  columns: number;
  relationships: number;
  embeddings: number;
  warnings: string[];
}

export interface MetadataSynonym {
  id: string;
  synonym: string;
  language: string;
}

export interface MetadataEnumValue {
  id: string;
  stored_value: string;
  display_label: string | null;
  description: string | null;
}

export interface MetadataColumn {
  id: string;
  column_name: string;
  data_type: string | null;
  is_nullable: boolean;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  description: string | null;
  sample_values: string[];
  synonyms: MetadataSynonym[];
  enum_values: MetadataEnumValue[];
}

export interface MetadataTable {
  id: string;
  table_name: string;
  schema_name: string;
  description: string | null;
  row_count: number | null;
  synonyms: MetadataSynonym[];
  columns: MetadataColumn[];
}

export type BusinessRuleType = "filter" | "join" | "aggregation" | "format" | "general";

export interface BusinessRule {
  id: string;
  table_id: string | null;
  rule_text: string;
  rule_type: BusinessRuleType | null;
}
