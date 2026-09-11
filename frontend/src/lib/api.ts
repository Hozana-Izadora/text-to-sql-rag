import type {
  BusinessRule,
  BusinessRuleType,
  Connection,
  ConnectionDetail,
  ConnectionInput,
  ConnectionTestResult,
  IntrospectionResult,
  MetadataSynonym,
  MetadataTable,
  SSEEvent,
} from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function extractErrorMessage(response: Response): Promise<string> {
  if (response.status === 422) {
    return "Pergunta muito curta ou inválida. Tente reformular com pelo menos 3 caracteres.";
  }
  return extractDetail(response);
}

async function extractDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
      return String(body.detail[0].msg);
    }
    return `Erro ${response.status}`;
  } catch {
    return `Erro ${response.status}`;
  }
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

/** Erro de uma chamada REST, com a mensagem já pronta para exibir ao usuário. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError("Não foi possível conectar ao servidor.", 0);
  }
  if (!response.ok) {
    throw new ApiError(await extractDetail(response), response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

// --- Conexões ---

export const listConnections = () => request<Connection[]>("/api/connections/");

export const getConnection = (id: string) => request<ConnectionDetail>(`/api/connections/${id}`);

export const createConnection = (body: ConnectionInput) =>
  request<Connection>("/api/connections/", { method: "POST", body: JSON.stringify(body) });

export const updateConnection = (id: string, body: Partial<ConnectionInput> & { is_active?: boolean }) =>
  request<Connection>(`/api/connections/${id}`, { method: "PUT", body: JSON.stringify(body) });

export const deleteConnection = (id: string) =>
  request<void>(`/api/connections/${id}`, { method: "DELETE" });

export const testNewConnection = (body: Omit<ConnectionInput, "name">) =>
  request<ConnectionTestResult>("/api/connections/test", { method: "POST", body: JSON.stringify(body) });

export const testConnection = (id: string) =>
  request<ConnectionTestResult>(`/api/connections/${id}/test`, { method: "POST" });

export const introspectConnection = (id: string) =>
  request<IntrospectionResult>(`/api/connections/${id}/introspect`, { method: "POST" });

// --- Metadados ---

const meta = (id: string) => `/api/connections/${id}/metadata`;

export const listMetadataTables = (id: string) => request<MetadataTable[]>(`${meta(id)}/tables`);

export const updateTableDescription = (id: string, tableId: string, description: string | null) =>
  request<void>(`${meta(id)}/tables/${tableId}`, { method: "PUT", body: JSON.stringify({ description }) });

export const updateColumnDescription = (id: string, columnId: string, description: string | null) =>
  request<void>(`${meta(id)}/columns/${columnId}`, { method: "PUT", body: JSON.stringify({ description }) });

export const addSynonym = (
  id: string,
  tableId: string,
  entity: { entity_type: "table" | "column"; entity_id: string; synonym: string },
) =>
  request<MetadataSynonym>(`${meta(id)}/tables/${tableId}/synonyms`, {
    method: "POST",
    body: JSON.stringify({ ...entity, language: "pt-BR" }),
  });

export const removeSynonym = (id: string, synonymId: string) =>
  request<void>(`${meta(id)}/synonyms/${synonymId}`, { method: "DELETE" });

export const listBusinessRules = (id: string) => request<BusinessRule[]>(`${meta(id)}/business-rules`);

export const createBusinessRule = (
  id: string,
  body: { table_id: string | null; rule_text: string; rule_type: BusinessRuleType },
) => request<BusinessRule>(`${meta(id)}/business-rules`, { method: "POST", body: JSON.stringify(body) });

export const updateBusinessRule = (
  id: string,
  ruleId: string,
  body: { rule_text?: string; rule_type?: BusinessRuleType },
) => request<void>(`${meta(id)}/business-rules/${ruleId}`, { method: "PUT", body: JSON.stringify(body) });

export const deleteBusinessRule = (id: string, ruleId: string) =>
  request<void>(`${meta(id)}/business-rules/${ruleId}`, { method: "DELETE" });

export const addEnumValue = (
  id: string,
  body: { column_id: string; stored_value: string; display_label: string | null },
) => request<void>(`${meta(id)}/enum-values`, { method: "POST", body: JSON.stringify(body) });

export const removeEnumValue = (id: string, enumId: string) =>
  request<void>(`${meta(id)}/enum-values/${enumId}`, { method: "DELETE" });

/**
 * Envia a pergunta via POST e parseia o stream SSE manualmente (sem lib externa).
 *
 * Um chunk de rede pode cortar no meio de um evento SSE — o `\n\n` de fechamento pode
 * só vir no próximo chunk. Por isso mantemos um buffer entre leituras e só processamos
 * eventos completos, guardando o restante (possivelmente incompleto) para a próxima volta.
 */
export async function streamChat(
  question: string,
  connectionId: string,
  onEvent: (event: SSEEvent) => void,
  onDone: () => void,
  onError: (error: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, connection_id: connectionId }),
      signal,
    });
  } catch (error) {
    if (isAbortError(error)) return;
    onError("Não foi possível conectar ao servidor. Verifique sua conexão.");
    return;
  }

  // Uma pergunta inválida (ex.: menos de 3 caracteres) retorna 422 com corpo JSON
  // padrão do FastAPI/Pydantic, não um stream SSE — precisa ser tratado antes de
  // entrar no parser SSE, senão o parsing falha de forma confusa.
  if (!response.ok) {
    onError(await extractErrorMessage(response));
    return;
  }

  if (!response.body) {
    onError("Resposta do servidor sem corpo de stream.");
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";

      for (const part of parts) {
        const trimmed = part.trim();
        if (!trimmed.startsWith("data:")) continue;

        const jsonText = trimmed.slice("data:".length).trim();
        if (!jsonText) continue;

        let parsed: SSEEvent;
        try {
          parsed = JSON.parse(jsonText) as SSEEvent;
        } catch {
          continue; // linha malformada — ignora e segue, não derruba o stream inteiro
        }

        if (parsed.event === "error") {
          finished = true;
          onError(typeof parsed.data === "string" ? parsed.data : "Erro ao processar a pergunta.");
          return;
        }
        if (parsed.event === "done") {
          finished = true;
          onDone();
          return;
        }
        onEvent(parsed);
      }
    }
  } catch (error) {
    if (isAbortError(error)) return;
    onError("A conexão com o servidor foi interrompida.");
    return;
  }

  if (!finished) {
    onError("A conexão foi encerrada antes da resposta ser concluída.");
  }
}
