"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { createBusinessRule, deleteBusinessRule } from "@/lib/api";
import type { BusinessRule, BusinessRuleType, MetadataTable } from "@/lib/types";

const RULE_TYPES: BusinessRuleType[] = ["filter", "join", "aggregation", "format", "general"];

interface BusinessRulesPanelProps {
  connectionId: string;
  rules: BusinessRule[];
  tables: MetadataTable[];
  onChange: () => void;
}

export function BusinessRulesPanel({ connectionId, rules, tables, onChange }: BusinessRulesPanelProps) {
  const [text, setText] = useState("");
  const [ruleType, setRuleType] = useState<BusinessRuleType>("general");
  const [tableId, setTableId] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const tableName = (id: string | null) => tables.find((t) => t.id === id)?.table_name ?? "geral";

  async function add() {
    if (!text.trim()) return;
    setBusy(true);
    try {
      await createBusinessRule(connectionId, {
        table_id: tableId || null,
        rule_text: text.trim(),
        rule_type: ruleType,
      });
      setText("");
      setTableId("");
      setRuleType("general");
      onChange();
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    await deleteBusinessRule(connectionId, id);
    onChange();
  }

  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-text-primary">Regras de negócio</h3>

      <div className="space-y-2">
        {rules.length === 0 && <p className="text-xs text-text-muted">Nenhuma regra cadastrada.</p>}
        {rules.map((rule) => (
          <div
            key={rule.id}
            className="flex items-start justify-between gap-2 rounded-md border border-border-subtle bg-bg-surface p-2"
          >
            <div className="min-w-0">
              <span className="mr-1.5 rounded bg-accent-subtle px-1.5 py-0.5 text-[10px] font-medium uppercase text-accent-text">
                {rule.rule_type ?? "general"}
              </span>
              <span className="text-[10px] text-text-muted">{tableName(rule.table_id)}</span>
              <p className="text-sm text-text-secondary">{rule.rule_text}</p>
            </div>
            <button
              type="button"
              onClick={() => remove(rule.id)}
              aria-label="Remover regra"
              className="shrink-0 text-text-muted hover:text-error"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>

      <div className="mt-3 space-y-2 rounded-md border border-dashed border-border-subtle p-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={2}
          placeholder="Ex.: apólices vigentes = status 'active' e end_date >= hoje"
          className="w-full resize-none rounded border border-border-strong px-2 py-1 text-sm text-text-primary focus:border-accent focus:outline-none"
        />
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={ruleType}
            onChange={(e) => setRuleType(e.target.value as BusinessRuleType)}
            className="rounded border border-border-strong px-2 py-1 text-xs text-text-secondary"
          >
            {RULE_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <select
            value={tableId}
            onChange={(e) => setTableId(e.target.value)}
            className="rounded border border-border-strong px-2 py-1 text-xs text-text-secondary"
          >
            <option value="">Regra geral</option>
            {tables.map((t) => (
              <option key={t.id} value={t.id}>{t.table_name}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={add}
            disabled={busy || !text.trim()}
            className="flex items-center gap-1 rounded bg-accent px-2.5 py-1 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-40"
          >
            <Plus className="h-3.5 w-3.5" /> Adicionar regra
          </button>
        </div>
      </div>
    </div>
  );
}
