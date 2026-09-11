"use client";

import { Plus, X } from "lucide-react";
import { useState } from "react";
import type { MetadataSynonym } from "@/lib/types";

interface SynonymChipsProps {
  synonyms: MetadataSynonym[];
  onAdd: (value: string) => Promise<void>;
  onRemove: (synonymId: string) => Promise<void>;
}

export function SynonymChips({ synonyms, onAdd, onRemove }: SynonymChipsProps) {
  const [adding, setAdding] = useState(false);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    const trimmed = value.trim();
    if (!trimmed) return;
    setBusy(true);
    try {
      await onAdd(trimmed);
      setValue("");
      setAdding(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-xs text-text-secondary">Sinônimos:</span>
      {synonyms.map((synonym) => (
        <span
          key={synonym.id}
          className="flex items-center gap-1 rounded-full bg-bg-elevated px-2 py-0.5 text-xs text-text-secondary"
        >
          {synonym.synonym}
          <button
            type="button"
            onClick={() => onRemove(synonym.id)}
            aria-label={`Remover ${synonym.synonym}`}
            className="text-text-muted hover:text-error"
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      {synonyms.length === 0 && !adding && <span className="text-xs text-text-muted">nenhum</span>}
      {adding ? (
        <span className="flex items-center gap-1">
          <input
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submit();
              if (e.key === "Escape") setAdding(false);
            }}
            disabled={busy}
            className="w-28 rounded border border-accent px-1.5 py-0.5 text-xs focus:outline-none"
          />
          <button type="button" onClick={submit} disabled={busy} className="text-xs text-accent-text">
            ok
          </button>
        </span>
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="flex items-center gap-0.5 rounded-full border border-dashed border-border-subtle px-2 py-0.5 text-xs text-text-secondary hover:border-border-strong"
        >
          <Plus className="h-3 w-3" /> add
        </button>
      )}
    </div>
  );
}
