"use client";

import { FileDown, FileText, Loader2 } from "lucide-react";
import { useState } from "react";
import type { ChartSpec, ChatMessageMetadata } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ExportPayload {
  question: string;
  responseText: string;
  sql: string;
  columns: string[];
  rows: Record<string, unknown>[];
  metadata: Record<string, unknown>;
  columnFormats?: ChatMessageMetadata["columnFormats"];
  chartSpec?: ChartSpec;
}

/** Reaproveitado tanto pelos botões manuais quanto pelo auto-download (evento
 * export_ready) em ChatContainer.tsx. */
export async function downloadExport(format: "docx" | "pdf", payload: ExportPayload): Promise<void> {
  const response = await fetch(`${API_URL}/api/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, format }),
  });

  if (!response.ok) {
    throw new Error(`Falha ao gerar ${format}`);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const timestamp = new Date().toISOString().replace(/[-:]/g, "").replace("T", "_").slice(0, 15);

  const link = document.createElement("a");
  link.href = url;
  link.download = `relatorio_${timestamp}.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

interface ExportButtonsProps {
  question: string;
  responseText: string;
  sql: string;
  columns: string[];
  rows: Record<string, unknown>[];
  metadata?: ChatMessageMetadata;
  chartSpec?: ChartSpec;
}

export function ExportButtons({
  question,
  responseText,
  sql,
  columns,
  rows,
  metadata,
  chartSpec,
}: ExportButtonsProps) {
  const [loadingFormat, setLoadingFormat] = useState<"docx" | "pdf" | null>(null);

  const handleExport = async (format: "docx" | "pdf") => {
    setLoadingFormat(format);
    try {
      await downloadExport(format, {
        question,
        responseText,
        sql,
        columns,
        rows,
        metadata: metadata ?? {},
        columnFormats: metadata?.columnFormats,
        chartSpec,
      });
    } catch {
      // Falha de export não deve travar o chat — o usuário pode tentar de novo.
    } finally {
      setLoadingFormat(null);
    }
  };

  const buttonClass =
    "flex items-center gap-1.5 rounded-lg border border-border-strong px-4 py-2 text-sm text-accent-text transition-colors hover:bg-accent-subtle disabled:cursor-not-allowed disabled:opacity-40";

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      <button
        type="button"
        onClick={() => handleExport("docx")}
        disabled={loadingFormat !== null}
        className={buttonClass}
      >
        {loadingFormat === "docx" ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <FileText className="h-4 w-4" />
        )}
        {loadingFormat === "docx" ? "Gerando..." : "Baixar Word"}
      </button>
      <button
        type="button"
        onClick={() => handleExport("pdf")}
        disabled={loadingFormat !== null}
        className={buttonClass}
      >
        {loadingFormat === "pdf" ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <FileDown className="h-4 w-4" />
        )}
        {loadingFormat === "pdf" ? "Gerando..." : "Baixar PDF"}
      </button>
    </div>
  );
}
