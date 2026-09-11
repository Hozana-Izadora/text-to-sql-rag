"use client";

import { Check, ChevronRight, Copy } from "lucide-react";
import { useState } from "react";

const KEYWORDS = new Set([
  "SELECT", "FROM", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "CROSS",
  "WHERE", "GROUP", "ORDER", "BY", "HAVING", "LIMIT", "OFFSET", "ON", "AS", "AND",
  "OR", "NOT", "IN", "BETWEEN", "LIKE", "ILIKE", "DISTINCT", "WITH", "UNION",
  "EXCEPT", "INTERSECT", "ALL", "CASE", "WHEN", "THEN", "ELSE", "END", "IS",
  "NULL", "ASC", "DESC", "TOP", "OVER", "PARTITION", "USING",
]);

const FUNCTIONS = new Set([
  "SUM", "COUNT", "AVG", "MAX", "MIN", "ROUND", "COALESCE", "NULLIF", "CAST",
  "EXTRACT", "DATE_TRUNC", "CURRENT_DATE", "CURRENT_TIMESTAMP", "NOW", "CURDATE",
  "GETDATE", "ABS", "GREATEST", "LEAST", "CONCAT", "LOWER", "UPPER", "LENGTH",
  "TRIM",
]);

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const TOKEN_RE = /(--[^\n]*)|('(?:[^']|'')*')|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)/g;

/** Highlight por tokenização single-pass — cada trecho é escapado individualmente,
 * nunca há risco de re-wrapear HTML já injetado. */
function highlightSql(sql: string): string {
  let result = "";
  let lastIndex = 0;
  let prevWord = "";
  let match: RegExpExecArray | null;

  TOKEN_RE.lastIndex = 0;
  while ((match = TOKEN_RE.exec(sql)) !== null) {
    result += escapeHtml(sql.slice(lastIndex, match.index));
    lastIndex = TOKEN_RE.lastIndex;

    const [, comment, string, number, word] = match;
    if (comment !== undefined) {
      result += `<span class="sql-comment">${escapeHtml(comment)}</span>`;
    } else if (string !== undefined) {
      result += `<span class="sql-str">${escapeHtml(string)}</span>`;
    } else if (number !== undefined) {
      result += `<span class="sql-num">${escapeHtml(number)}</span>`;
    } else {
      const upper = word.toUpperCase();
      if (KEYWORDS.has(upper)) {
        result += `<span class="sql-kw">${escapeHtml(word)}</span>`;
      } else if (FUNCTIONS.has(upper)) {
        result += `<span class="sql-fn">${escapeHtml(word)}</span>`;
      } else if (prevWord === "AS") {
        result += `<span class="sql-alias">${escapeHtml(word)}</span>`;
      } else {
        result += escapeHtml(word);
      }
      prevWord = upper;
    }
  }
  result += escapeHtml(sql.slice(lastIndex));
  return result;
}

interface SqlViewerProps {
  sql: string;
}

export function SqlViewer({ sql }: SqlViewerProps) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = async (event: React.MouseEvent) => {
    event.stopPropagation();
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard indisponível (ex.: contexto não seguro) — falha silenciosa
    }
  };

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex items-center gap-1 text-sm text-text-secondary transition-colors hover:text-text-primary"
      >
        <ChevronRight className={`h-4 w-4 transition-transform ${expanded ? "rotate-90" : ""}`} />
        SQL gerado
      </button>

      <div
        className="grid transition-[grid-template-rows] duration-[250ms] ease-out"
        style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden">
          <div className="relative mt-2 overflow-x-auto rounded-lg border border-border-subtle bg-[#0D1117] p-3 font-mono text-[13px] text-[#c9d1d9]">
            <button
              type="button"
              onClick={handleCopy}
              className="absolute right-2 top-2 rounded p-1 text-[#8b949e] hover:bg-white/10 hover:text-white"
              aria-label="Copiar SQL"
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </button>
            {copied && (
              <span className="absolute right-10 top-2.5 rounded bg-black/60 px-1.5 py-0.5 text-[11px] text-white">
                Copiado!
              </span>
            )}
            {/* highlightSql escapa o HTML antes de injetar as tags de highlight */}
            <pre
              className="whitespace-pre-wrap pr-8 leading-relaxed"
              dangerouslySetInnerHTML={{ __html: highlightSql(sql) }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
