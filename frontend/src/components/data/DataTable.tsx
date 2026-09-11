"use client";

import { useState } from "react";
import type { ColumnFormat } from "@/lib/types";

interface DataTableProps {
  columns: string[];
  rows: Record<string, unknown>[];
  truncated?: boolean;
  columnFormats?: Record<string, ColumnFormat>;
}

const PREVIEW_ROW_COUNT = 10;
const NUMERIC_FORMATS: ColumnFormat[] = ["currency", "integer", "decimal_number"];

function formatValue(value: unknown, format?: ColumnFormat): string {
  if (value === null || value === undefined) return "—";
  if (format === "currency" && typeof value === "number") {
    return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }
  if (typeof value === "number") {
    return value.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  }
  return String(value);
}

export function DataTable({ columns, rows, truncated, columnFormats }: DataTableProps) {
  const [showAll, setShowAll] = useState(false);

  if (columns.length === 0 || rows.length === 0) {
    return null;
  }

  const visibleRows = showAll ? rows : rows.slice(0, PREVIEW_ROW_COUNT);
  const hasMore = rows.length > PREVIEW_ROW_COUNT && !showAll;

  return (
    <div className="mt-3">
      <div className="overflow-x-auto rounded-card border border-border-subtle">
        <table className="min-w-full text-sm">
          <thead className="bg-bg-elevated">
            <tr>
              {columns.map((column) => (
                <th
                  key={column}
                  className="px-3 py-2 text-left text-[10px] font-medium uppercase tracking-wider text-text-secondary"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, index) => (
              <tr key={index} className="border-t border-border-subtle hover:bg-bg-elevated">
                {columns.map((column) => {
                  const value = row[column];
                  const format = columnFormats?.[column];
                  const isNumeric =
                    typeof value === "number" || (format && NUMERIC_FORMATS.includes(format));
                  const isNull = value === null || value === undefined;
                  return (
                    <td
                      key={column}
                      className={[
                        "px-3 py-2",
                        isNumeric ? "text-right font-mono" : "text-left",
                        format === "currency" ? "text-success" : "",
                        isNull ? "italic text-text-muted" : "text-text-primary",
                      ].join(" ")}
                    >
                      {formatValue(value, format)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-1 flex flex-wrap items-center justify-between gap-2 text-xs text-text-secondary">
        <span>
          {rows.length} linha{rows.length === 1 ? "" : "s"} retornada{rows.length === 1 ? "" : "s"}
          {truncated && (
            <span className="ml-2 rounded-full bg-warning/20 px-2 py-0.5 text-[11px] font-medium text-warning">
              Resultados truncados
            </span>
          )}
        </span>
        {hasMore && (
          <button
            type="button"
            onClick={() => setShowAll(true)}
            className="font-medium text-accent-text hover:text-accent"
          >
            Ver todas ({rows.length} linhas)
          </button>
        )}
      </div>
    </div>
  );
}
