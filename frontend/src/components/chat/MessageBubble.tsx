import { ChartRenderer } from "@/components/data/ChartRenderer";
import { DataTable } from "@/components/data/DataTable";
import { ExportButtons } from "@/components/data/ExportButtons";
import { SqlViewer } from "@/components/data/SqlViewer";
import type { ChatMessage } from "@/lib/types";
import { StatusIndicator } from "./StatusIndicator";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  if (message.role === "user") {
    return (
      <div className="animate-in flex justify-end">
        <div className="max-w-[75%] rounded-[16px_16px_4px_16px] bg-accent px-4 py-3 text-white">
          <p className="whitespace-pre-wrap text-sm">{message.content}</p>
        </div>
      </div>
    );
  }

  const showStatus = Boolean(message.isStreaming && message.status && !message.content);

  return (
    <div className="animate-in flex justify-start">
      <div className="max-w-[85%] rounded-[16px_16px_16px_4px] border border-border-subtle bg-bg-surface px-5 py-4 text-text-primary">
        {showStatus && <StatusIndicator status={message.status as string} />}

        {message.content && (
          <p
            className={`whitespace-pre-wrap text-sm ${message.isError ? "text-error" : "text-text-primary"}`}
          >
            {message.content}
          </p>
        )}

        {message.sql && <SqlViewer sql={message.sql} />}

        {message.chart && <ChartRenderer spec={message.chart} />}

        {message.columns && message.rows && (
          <DataTable
            columns={message.columns}
            rows={message.rows}
            truncated={message.metadata?.truncated}
            columnFormats={message.metadata?.columnFormats}
          />
        )}

        {message.rows && message.rows.length > 0 && (
          <ExportButtons
            question={message.question ?? ""}
            responseText={message.content}
            sql={message.sql ?? ""}
            columns={message.columns ?? []}
            rows={message.rows}
            metadata={message.metadata}
            chartSpec={message.chart}
          />
        )}
      </div>
    </div>
  );
}
