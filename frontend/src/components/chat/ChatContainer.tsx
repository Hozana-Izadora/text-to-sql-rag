"use client";

import { useCallback, useRef, useState } from "react";
import { downloadExport } from "@/components/data/ExportButtons";
import { streamChat } from "@/lib/api";
import type { ChatMessage, ChatMessageMetadata, ExportReadyPayload, SSEEvent } from "@/lib/types";
import { InputBar } from "./InputBar";
import { MessageList } from "./MessageList";
import { WelcomeScreen } from "./WelcomeScreen";

interface ChatContainerProps {
  connectionId: string;
  connectionName: string;
}

interface ChatMetadataEventPayload {
  row_count: number;
  truncated: boolean;
  tables_used: string[];
  column_formats?: ChatMessageMetadata["columnFormats"];
}

function createId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function ChatContainer({ connectionId, connectionName }: ChatContainerProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  // Espelha, de forma síncrona, o que está sendo construído pra mensagem do assistant
  // em andamento — necessário porque "export_ready" pode chegar no meio do parsing
  // SSE, antes do último setMessages "commitar" no estado React (mesmo padrão do
  // accumulated_state que o backend já usa em app/api/streaming.py).
  const pendingRef = useRef<Partial<ChatMessage>>({});

  const updateAssistantMessage = useCallback((id: string, patch: Partial<ChatMessage>) => {
    pendingRef.current = { ...pendingRef.current, ...patch };
    setMessages((prev) => prev.map((message) => (message.id === id ? { ...message, ...patch } : message)));
  }, []);

  const appendAssistantContent = useCallback((id: string, textChunk: string) => {
    pendingRef.current = { ...pendingRef.current, content: (pendingRef.current.content ?? "") + textChunk };
    setMessages((prev) =>
      prev.map((message) => (message.id === id ? { ...message, content: message.content + textChunk } : message)),
    );
  }, []);

  const handleSubmit = useCallback(
    async (question: string) => {
      const userMessage: ChatMessage = { id: createId(), role: "user", content: question };
      const assistantId = createId();
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        question,
        isStreaming: true,
      };

      pendingRef.current = { ...assistantMessage };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsLoading(true);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      const handleEvent = (event: SSEEvent) => {
        switch (event.event) {
          case "status":
            updateAssistantMessage(assistantId, { status: String(event.data) });
            break;
          case "sql":
            updateAssistantMessage(assistantId, { sql: String(event.data) });
            break;
          case "columns":
            updateAssistantMessage(assistantId, { columns: event.data as string[] });
            break;
          case "rows":
            updateAssistantMessage(assistantId, { rows: event.data as Record<string, unknown>[] });
            break;
          case "metadata": {
            const raw = event.data as ChatMetadataEventPayload;
            updateAssistantMessage(assistantId, {
              metadata: {
                rowCount: raw.row_count,
                truncated: raw.truncated,
                tablesUsed: raw.tables_used,
                columnFormats: raw.column_formats,
              },
            });
            break;
          }
          case "chart":
            updateAssistantMessage(assistantId, { chart: event.data as ChatMessage["chart"] });
            break;
          case "answer":
            appendAssistantContent(assistantId, String(event.data));
            break;
          case "export_ready": {
            const payload = event.data as ExportReadyPayload;
            const current = pendingRef.current;
            downloadExport(payload.format, {
              question: current.question ?? question,
              responseText: current.content ?? "",
              sql: current.sql ?? "",
              columns: current.columns ?? [],
              rows: current.rows ?? [],
              metadata: current.metadata ?? {},
              columnFormats: current.metadata?.columnFormats,
              chartSpec: current.chart,
            }).catch(() => {
              // Auto-download falhou — o usuário ainda tem os botões manuais na bolha.
            });
            break;
          }
          default:
            break;
        }
      };

      const handleDone = () => {
        updateAssistantMessage(assistantId, { isStreaming: false, status: undefined });
        setIsLoading(false);
      };

      const handleError = (errorMessage: string) => {
        updateAssistantMessage(assistantId, {
          isStreaming: false,
          isError: true,
          status: undefined,
          content: errorMessage,
        });
        setIsLoading(false);
      };

      await streamChat(question, connectionId, handleEvent, handleDone, handleError, controller.signal);
    },
    [appendAssistantContent, connectionId, updateAssistantMessage],
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-bg-base">
      {messages.length === 0 ? (
        <WelcomeScreen connectionName={connectionName} onPick={handleSubmit} />
      ) : (
        <MessageList messages={messages} />
      )}
      <InputBar onSubmit={handleSubmit} isLoading={isLoading} />
    </div>
  );
}
