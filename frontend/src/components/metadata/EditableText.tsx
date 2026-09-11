"use client";

import { Check, Loader2, Pencil } from "lucide-react";
import { useState } from "react";

interface EditableTextProps {
  value: string | null;
  placeholder: string;
  onSave: (value: string | null) => Promise<void>;
  multiline?: boolean;
}

export function EditableText({ value, placeholder, onSave, multiline = true }: EditableTextProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? "");
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(0);
  const [error, setError] = useState(false);

  function startEditing() {
    setDraft(value ?? "");
    setError(false);
    setEditing(true);
  }

  async function commit() {
    const next = draft.trim() || null;
    if (next === value) {
      setEditing(false);
      return;
    }
    setSaving(true);
    setError(false);
    try {
      await onSave(next);
      setEditing(false);
      setSavedAt(Date.now());
      setTimeout(() => setSavedAt((at) => (Date.now() - at >= 1900 ? 0 : at)), 2000);
    } catch {
      setError(true);
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return (
      <div className="flex items-start gap-2">
        {multiline ? (
          <textarea
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={2}
            className="flex-1 resize-none rounded border border-accent px-2 py-1 text-sm text-text-primary focus:outline-none"
          />
        ) : (
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="flex-1 rounded border border-accent px-2 py-1 text-sm text-text-primary focus:outline-none"
          />
        )}
        <button
          type="button"
          onClick={commit}
          disabled={saving}
          className="rounded bg-accent px-2 py-1 text-xs text-white hover:bg-accent-hover disabled:opacity-40"
        >
          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Salvar"}
        </button>
        <button
          type="button"
          onClick={() => setEditing(false)}
          className="rounded px-2 py-1 text-xs text-text-secondary hover:bg-bg-elevated"
        >
          Cancelar
        </button>
        {error && <span className="text-xs text-error">erro</span>}
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={startEditing}
      className="group flex w-full items-center gap-2 text-left"
    >
      <span className={`text-sm ${value ? "text-text-secondary" : "italic text-text-muted"}`}>
        {value ?? placeholder}
      </span>
      <Pencil className="h-3.5 w-3.5 shrink-0 text-text-muted group-hover:text-text-secondary" />
      {savedAt > 0 && (
        <span className="flex items-center gap-0.5 text-xs text-success">
          <Check className="h-3 w-3" /> Salvo
        </span>
      )}
    </button>
  );
}
