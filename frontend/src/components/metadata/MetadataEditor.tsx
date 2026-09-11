"use client";

import { KeyRound, Link2, Loader2, Plus, RefreshCw, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import {
  addEnumValue,
  addSynonym,
  ApiError,
  introspectConnection,
  listBusinessRules,
  listMetadataTables,
  removeEnumValue,
  removeSynonym,
  updateColumnDescription,
  updateTableDescription,
} from "@/lib/api";
import type { BusinessRule, MetadataColumn, MetadataTable } from "@/lib/types";
import { BusinessRulesPanel } from "./BusinessRulesPanel";
import { EditableText } from "./EditableText";
import { SynonymChips } from "./SynonymChips";

export function MetadataEditor({ connectionId }: { connectionId: string }) {
  const [tables, setTables] = useState<MetadataTable[] | null>(null);
  const [rules, setRules] = useState<BusinessRule[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const reload = useCallback(async () => {
    try {
      const [nextTables, nextRules] = await Promise.all([
        listMetadataTables(connectionId),
        listBusinessRules(connectionId),
      ]);
      setTables(nextTables);
      setRules(nextRules);
      setError(null);
      setSelectedId((prev) => prev ?? nextTables[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao carregar os metadados.");
    }
  }, [connectionId]);

  useEffect(() => {
    // Fetch inicial no cliente (a API só é alcançável pelo navegador — ver CLAUDE.md).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void reload();
  }, [reload]);

  async function handleReintrospect() {
    setSyncing(true);
    setError(null);
    try {
      await introspectConnection(connectionId);
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao re-introspeccionar.");
    } finally {
      setSyncing(false);
    }
  }

  if (error && tables === null) {
    return (
      <>
        <AppHeader back={{ href: "/connections", label: "Conexões" }} />
        <p className="p-6 text-sm text-error">{error}</p>
      </>
    );
  }
  if (tables === null) {
    return (
      <>
        <AppHeader back={{ href: "/connections", label: "Conexões" }} />
        <div className="flex justify-center p-12 text-text-muted">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      </>
    );
  }

  const selected = tables.find((t) => t.id === selectedId) ?? null;

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-bg-base">
      <AppHeader back={{ href: "/connections", label: "Conexões" }}>
        <button
          type="button"
          onClick={handleReintrospect}
          disabled={syncing}
          className="flex items-center gap-1.5 rounded-lg border border-border-strong px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-bg-elevated disabled:opacity-40"
        >
          {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Sincronizar
        </button>
      </AppHeader>

      {error && <div className="bg-error/10 px-4 py-2 text-sm text-error">{error}</div>}

      <div className="grid min-h-0 flex-1 grid-cols-1 overflow-hidden md:grid-cols-[220px_1fr]">
        <nav className="max-h-40 overflow-y-auto border-b border-border-subtle bg-bg-surface py-2 md:max-h-none md:border-b-0 md:border-r">
          <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-text-muted">
            Tabelas ({tables.length})
          </p>
          {tables.map((table) => (
            <button
              key={table.id}
              type="button"
              onClick={() => setSelectedId(table.id)}
              className={`block w-full truncate px-3 py-1.5 text-left text-sm ${
                table.id === selectedId
                  ? "bg-accent-subtle font-medium text-accent-text"
                  : "text-text-secondary hover:bg-bg-elevated"
              }`}
            >
              {table.table_name}
            </button>
          ))}
        </nav>

        <div className="min-h-0 overflow-y-auto p-5">
          {selected ? (
            <TableDetail
              key={selected.id}
              connectionId={connectionId}
              table={selected}
              onChange={reload}
            />
          ) : (
            <p className="text-sm text-text-muted">Nenhuma tabela introspectada ainda.</p>
          )}

          <hr className="my-6 border-border-subtle" />
          <BusinessRulesPanel
            connectionId={connectionId}
            rules={rules}
            tables={tables}
            onChange={reload}
          />
        </div>
      </div>
    </div>
  );
}

function TableDetail({
  connectionId,
  table,
  onChange,
}: {
  connectionId: string;
  table: MetadataTable;
  onChange: () => Promise<void>;
}) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-text-primary">{table.table_name}</h2>
        <p className="text-xs text-text-muted">
          schema {table.schema_name}
          {table.row_count != null && ` · ~${table.row_count.toLocaleString("pt-BR")} linhas`}
        </p>
      </div>

      <EditableText
        value={table.description}
        placeholder="Adicionar descrição da tabela…"
        onSave={async (value) => {
          await updateTableDescription(connectionId, table.id, value);
          await onChange();
        }}
      />

      <SynonymChips
        synonyms={table.synonyms}
        onAdd={async (value) => {
          await addSynonym(connectionId, table.id, {
            entity_type: "table",
            entity_id: table.id,
            synonym: value,
          });
          await onChange();
        }}
        onRemove={async (synonymId) => {
          await removeSynonym(connectionId, synonymId);
          await onChange();
        }}
      />

      <div>
        <h3 className="mb-2 text-sm font-semibold text-text-primary">Colunas ({table.columns.length})</h3>
        <div className="space-y-3">
          {table.columns.map((column) => (
            <ColumnRow
              key={column.id}
              connectionId={connectionId}
              tableId={table.id}
              column={column}
              onChange={onChange}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function ColumnRow({
  connectionId,
  tableId,
  column,
  onChange,
}: {
  connectionId: string;
  tableId: string;
  column: MetadataColumn;
  onChange: () => Promise<void>;
}) {
  const [enumValue, setEnumValue] = useState("");
  const [enumLabel, setEnumLabel] = useState("");
  const [addingEnum, setAddingEnum] = useState(false);

  async function submitEnum() {
    if (!enumValue.trim()) return;
    await addEnumValue(connectionId, {
      column_id: column.id,
      stored_value: enumValue.trim(),
      display_label: enumLabel.trim() || null,
    });
    setEnumValue("");
    setEnumLabel("");
    setAddingEnum(false);
    await onChange();
  }

  return (
    <div className="rounded-md border border-border-subtle bg-bg-surface p-3">
      <div className="flex items-center gap-2">
        <code className="font-mono text-sm font-medium text-text-primary">{column.column_name}</code>
        <span className="text-xs text-text-muted">{column.data_type}</span>
        {column.is_primary_key && <KeyRound className="h-3.5 w-3.5 text-warning" aria-label="PK" />}
        {column.is_foreign_key && <Link2 className="h-3.5 w-3.5 text-info" aria-label="FK" />}
        {!column.is_nullable && <span className="text-[10px] text-text-muted">NOT NULL</span>}
      </div>

      <div className="mt-1.5">
        <EditableText
          value={column.description}
          placeholder="Adicionar descrição da coluna…"
          onSave={async (value) => {
            await updateColumnDescription(connectionId, column.id, value);
            await onChange();
          }}
        />
      </div>

      <div className="mt-1.5">
        <SynonymChips
          synonyms={column.synonyms}
          onAdd={async (value) => {
            await addSynonym(connectionId, tableId, {
              entity_type: "column",
              entity_id: column.id,
              synonym: value,
            });
            await onChange();
          }}
          onRemove={async (synonymId) => {
            await removeSynonym(connectionId, synonymId);
            await onChange();
          }}
        />
      </div>

      {(column.enum_values.length > 0 || column.sample_values.length > 0 || addingEnum) && (
        <div className="mt-2 border-t border-border-subtle pt-2">
          <p className="text-xs text-text-secondary">Valores:</p>
          <div className="mt-1 space-y-1">
            {column.enum_values.map((value) => (
              <div key={value.id} className="flex items-center gap-2 text-xs">
                <code className="font-mono text-text-secondary">{value.stored_value}</code>
                {value.display_label && <span className="text-text-secondary">→ “{value.display_label}”</span>}
                <button
                  type="button"
                  onClick={async () => {
                    await removeEnumValue(connectionId, value.id);
                    await onChange();
                  }}
                  aria-label="Remover valor"
                  className="text-text-muted hover:text-error"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
            {column.enum_values.length === 0 && column.sample_values.length > 0 && (
              <p className="text-xs text-text-muted">
                Exemplos detectados: {column.sample_values.join(", ")}
              </p>
            )}
          </div>

          {addingEnum ? (
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <input
                autoFocus
                value={enumValue}
                onChange={(e) => setEnumValue(e.target.value)}
                placeholder="valor no banco"
                className="w-32 rounded border border-accent px-1.5 py-0.5 text-xs focus:outline-none"
              />
              <input
                value={enumLabel}
                onChange={(e) => setEnumLabel(e.target.value)}
                placeholder="rótulo amigável"
                className="w-36 rounded border border-border-strong px-1.5 py-0.5 text-xs focus:outline-none"
              />
              <button type="button" onClick={submitEnum} className="text-xs text-accent-text">
                salvar
              </button>
              <button type="button" onClick={() => setAddingEnum(false)} className="text-xs text-text-muted">
                cancelar
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setAddingEnum(true)}
              className="mt-1.5 flex items-center gap-0.5 text-xs text-accent-text hover:text-accent"
            >
              <Plus className="h-3 w-3" /> adicionar valor
            </button>
          )}
        </div>
      )}

      {column.enum_values.length === 0 && column.sample_values.length === 0 && !addingEnum && (
        <button
          type="button"
          onClick={() => setAddingEnum(true)}
          className="mt-2 flex items-center gap-0.5 text-xs text-text-muted hover:text-accent-text"
        >
          <Plus className="h-3 w-3" /> mapear valores possíveis
        </button>
      )}
    </div>
  );
}
