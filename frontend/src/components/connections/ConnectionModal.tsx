"use client";

import { Loader2, X } from "lucide-react";
import { useState } from "react";
import { ApiError, createConnection, testNewConnection, updateConnection } from "@/lib/api";
import { DB_TYPES, SUPPORTED_DB_TYPES, dbTypeInfo } from "@/lib/dbTypes";
import type { Connection, ConnectionInput, ConnectionTestResult, DbType } from "@/lib/types";

interface ConnectionModalProps {
  /** Conexão a editar; ausente = criar nova. */
  connection?: Connection;
  onClose: () => void;
  onSaved: (connection: Connection, isNew: boolean) => void;
}

type FormState = Omit<ConnectionInput, "port"> & { port: string };

function initialForm(connection?: Connection): FormState {
  if (connection) {
    return {
      name: connection.name,
      db_type: connection.db_type,
      host: connection.host,
      port: String(connection.port),
      database_name: connection.database_name,
      username: connection.username,
      password: "",
      ssl_enabled: connection.ssl_enabled,
      schema_name: connection.schema_name,
    };
  }
  return {
    name: "",
    db_type: "postgresql",
    host: "localhost",
    port: String(DB_TYPES.postgresql.defaultPort),
    database_name: "",
    username: "",
    password: "",
    ssl_enabled: false,
    schema_name: "public",
  };
}

const inputClass =
  "w-full rounded-lg border border-border-subtle bg-bg-elevated px-3 py-2 text-sm text-text-primary transition-colors focus:border-accent focus:outline-none";
const labelClass = "mb-1 block text-xs font-medium text-text-secondary";

export function ConnectionModal({ connection, onClose, onSaved }: ConnectionModalProps) {
  const isEdit = Boolean(connection);
  const [form, setForm] = useState<FormState>(() => initialForm(connection));
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const info = dbTypeInfo(form.db_type);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setTestResult(null);
  }

  function onDbTypeChange(dbType: DbType) {
    setForm((prev) => ({
      ...prev,
      db_type: dbType,
      port: String(DB_TYPES[dbType].defaultPort || prev.port),
      schema_name: DB_TYPES[dbType].usesSchema ? prev.schema_name || "public" : "",
    }));
    setTestResult(null);
  }

  function buildPayload(): Omit<ConnectionInput, "name"> {
    return {
      db_type: form.db_type,
      host: form.host.trim(),
      port: Number(form.port),
      database_name: form.database_name.trim(),
      username: form.username.trim(),
      password: form.password,
      ssl_enabled: form.ssl_enabled,
      schema_name: info.usesSchema ? form.schema_name.trim() || "public" : "public",
    };
  }

  async function handleTest() {
    setTesting(true);
    setError(null);
    setTestResult(null);
    try {
      setTestResult(await testNewConnection(buildPayload()));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao testar a conexão.");
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      if (isEdit && connection) {
        const payload: Partial<ConnectionInput> = { ...buildPayload(), name: form.name.trim() };
        if (!form.password) delete payload.password;
        const saved = await updateConnection(connection.id, payload);
        onSaved(saved, false);
      } else {
        const saved = await createConnection({ ...buildPayload(), name: form.name.trim() });
        onSaved(saved, true);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao salvar a conexão.");
      setSaving(false);
    }
  }

  const canSave = form.name.trim() && form.host.trim() && form.database_name.trim() && form.username.trim();

  return (
    <div
      className="animate-in fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="animate-scale-in max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-card border border-border-subtle bg-bg-surface p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">
            {isEdit ? "Editar conexão" : "Nova conexão"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar"
            className="text-text-muted hover:text-text-primary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <label className={labelClass} htmlFor="conn-name">Nome da conexão</label>
            <input
              id="conn-name"
              className={inputClass}
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="Produção — ERP Financeiro"
            />
          </div>

          <div>
            <label className={labelClass} htmlFor="conn-type">Tipo de banco</label>
            <select
              id="conn-type"
              className={`${inputClass} disabled:opacity-60`}
              value={form.db_type}
              disabled={isEdit}
              onChange={(e) => onDbTypeChange(e.target.value as DbType)}
            >
              {SUPPORTED_DB_TYPES.map((t) => (
                <option key={t} value={t}>
                  {DB_TYPES[t].icon} {DB_TYPES[t].label}
                </option>
              ))}
            </select>
            {isEdit && (
              <p className="mt-1 text-xs text-text-muted">
                O tipo de banco não pode ser alterado — crie uma nova conexão.
              </p>
            )}
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              <label className={labelClass} htmlFor="conn-host">Host</label>
              <input id="conn-host" className={inputClass} value={form.host} onChange={(e) => set("host", e.target.value)} />
            </div>
            <div className="w-24">
              <label className={labelClass} htmlFor="conn-port">Porta</label>
              <input
                id="conn-port"
                className={inputClass}
                inputMode="numeric"
                value={form.port}
                onChange={(e) => set("port", e.target.value.replace(/\D/g, ""))}
              />
            </div>
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              <label className={labelClass} htmlFor="conn-db">Nome do banco</label>
              <input
                id="conn-db"
                className={inputClass}
                value={form.database_name}
                onChange={(e) => set("database_name", e.target.value)}
              />
            </div>
            {info.usesSchema && (
              <div className="flex-1">
                <label className={labelClass} htmlFor="conn-schema">Schema</label>
                <input
                  id="conn-schema"
                  className={inputClass}
                  value={form.schema_name}
                  onChange={(e) => set("schema_name", e.target.value)}
                  placeholder={form.db_type === "sqlserver" ? "dbo" : "public"}
                />
              </div>
            )}
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              <label className={labelClass} htmlFor="conn-user">Usuário</label>
              <input
                id="conn-user"
                className={inputClass}
                value={form.username}
                onChange={(e) => set("username", e.target.value)}
                autoComplete="off"
              />
            </div>
            <div className="flex-1">
              <label className={labelClass} htmlFor="conn-pass">Senha</label>
              <input
                id="conn-pass"
                type="password"
                className={inputClass}
                value={form.password}
                onChange={(e) => set("password", e.target.value)}
                placeholder={isEdit ? "•••••• (inalterada)" : ""}
                autoComplete="new-password"
              />
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm text-text-secondary">
            <input
              type="checkbox"
              checked={form.ssl_enabled}
              onChange={(e) => set("ssl_enabled", e.target.checked)}
              className="accent-[color:var(--accent)]"
            />
            Usar SSL/TLS
          </label>

          {testResult && (
            <p className={`text-sm ${testResult.success ? "text-success" : "text-error"}`}>
              {testResult.success ? "✅" : "❌"} {testResult.message}
              {testResult.db_version ? ` — ${testResult.db_version}` : ""}
              {testResult.latency_ms != null ? ` (${testResult.latency_ms} ms)` : ""}
            </p>
          )}
          {error && <p className="text-sm text-error">{error}</p>}
        </div>

        <div className="mt-6 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={handleTest}
            disabled={testing || saving || !form.password}
            className="flex items-center gap-2 rounded-lg border border-border-strong px-3 py-2 text-sm text-accent-text transition-colors hover:bg-accent-subtle disabled:opacity-40"
          >
            {testing && <Loader2 className="h-4 w-4 animate-spin" />}
            Testar conexão
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-3 py-2 text-sm text-text-secondary hover:bg-bg-elevated"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !canSave || (!isEdit && !form.password)}
              className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
            >
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {isEdit ? "Salvar" : "Salvar e introspeccionar"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
