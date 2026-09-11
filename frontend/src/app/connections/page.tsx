"use client";

import { Loader2, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { ConnectionCard } from "@/components/connections/ConnectionCard";
import { ConnectionModal } from "@/components/connections/ConnectionModal";
import { ApiError, deleteConnection, introspectConnection, listConnections } from "@/lib/api";
import type { Connection } from "@/lib/types";

type BusyState = { id: string; kind: "introspect" | "delete" } | null;

export default function ConnectionsPage() {
  const router = useRouter();
  const [connections, setConnections] = useState<Connection[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<{ open: boolean; editing?: Connection } | null>(null);
  const [busy, setBusy] = useState<BusyState>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setConnections(await listConnections());
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao carregar as conexões.");
    }
  }, []);

  useEffect(() => {
    // Fetch inicial no cliente (a API só é alcançável pelo navegador — ver CLAUDE.md).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const handleReintrospect = useCallback(
    async (connection: Connection) => {
      setBusy({ id: connection.id, kind: "introspect" });
      setNotice(null);
      try {
        const result = await introspectConnection(connection.id);
        setNotice(
          `${connection.name}: ${result.tables} tabelas, ${result.columns} colunas, ${result.embeddings} embeddings.`,
        );
        await load();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Falha ao re-introspeccionar.");
      } finally {
        setBusy(null);
      }
    },
    [load],
  );

  const handleDelete = useCallback(
    async (connection: Connection) => {
      if (!window.confirm(`Remover "${connection.name}" e todos os metadados associados?`)) return;
      setBusy({ id: connection.id, kind: "delete" });
      try {
        await deleteConnection(connection.id);
        await load();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Falha ao remover a conexão.");
      } finally {
        setBusy(null);
      }
    },
    [load],
  );

  return (
    <div className="min-h-full bg-bg-base">
      <AppHeader>
        <button
          type="button"
          onClick={() => setModal({ open: true })}
          className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
        >
          <Plus className="h-4 w-4" /> Nova conexão
        </button>
      </AppHeader>

      <main className="mx-auto max-w-5xl px-4 py-8">
        <h1 className="mb-1 text-2xl font-semibold text-text-primary">Suas conexões</h1>
        <p className="mb-6 text-sm text-text-secondary">
          Cadastre um banco de dados para consultá-lo em linguagem natural.
        </p>

        {notice && (
          <div className="mb-4 rounded-lg bg-success/10 px-3 py-2 text-sm text-success">{notice}</div>
        )}
        {error && (
          <div className="mb-4 rounded-lg bg-error/10 px-3 py-2 text-sm text-error">{error}</div>
        )}

        {connections === null && !error && (
          <div className="flex justify-center py-12 text-text-muted">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        )}

        {connections !== null && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {connections.map((connection) => (
              <ConnectionCard
                key={connection.id}
                connection={connection}
                busy={busy?.id === connection.id ? busy.kind : null}
                onEdit={() => setModal({ open: true, editing: connection })}
                onReintrospect={() => handleReintrospect(connection)}
                onDelete={() => handleDelete(connection)}
              />
            ))}
            <button
              type="button"
              onClick={() => setModal({ open: true })}
              className="flex min-h-[160px] flex-col items-center justify-center gap-2 rounded-card border-2 border-dashed border-border-subtle text-text-secondary transition-colors hover:border-accent hover:text-accent"
            >
              <Plus className="h-6 w-6" />
              <span className="text-sm font-medium">
                {connections.length === 0 ? "Cadastrar a primeira conexão" : "Nova conexão"}
              </span>
            </button>
          </div>
        )}
      </main>

      {modal?.open && (
        <ConnectionModal
          connection={modal.editing}
          onClose={() => setModal(null)}
          onSaved={(saved, isNew) => {
            setModal(null);
            void load();
            if (isNew) router.push(`/connections/${saved.id}/metadata`);
          }}
        />
      )}
    </div>
  );
}
