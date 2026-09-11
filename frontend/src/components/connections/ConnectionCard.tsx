"use client";

import { Loader2, MessageSquare, Pencil, RefreshCw, Trash2 } from "lucide-react";
import Link from "next/link";
import { dbTypeInfo } from "@/lib/dbTypes";
import { relativeTime } from "@/lib/relativeTime";
import type { Connection } from "@/lib/types";

interface ConnectionCardProps {
  connection: Connection;
  busy: "introspect" | "delete" | null;
  onEdit: () => void;
  onReintrospect: () => void;
  onDelete: () => void;
}

const ghostBtn =
  "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-text-secondary transition-colors hover:bg-bg-elevated hover:text-text-primary disabled:opacity-40";

export function ConnectionCard({ connection, busy, onEdit, onReintrospect, onDelete }: ConnectionCardProps) {
  const info = dbTypeInfo(connection.db_type);

  return (
    <div className="flex flex-col rounded-card border border-border-subtle bg-bg-surface p-5 transition-colors hover:border-border-strong">
      <div className="flex items-start gap-3">
        <span
          className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-lg"
          style={{ backgroundColor: `${info.brandColor}22`, color: info.brandColor }}
          aria-hidden
        >
          {info.icon}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-semibold text-text-primary">{connection.name}</h3>
          <p className="truncate text-xs text-text-secondary">
            {info.label} · {connection.host}:{connection.port} · {connection.database_name}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {connection.table_count ?? 0} tabela{connection.table_count === 1 ? "" : "s"} · sync{" "}
            {relativeTime(connection.last_introspected_at)}
            {!connection.is_active && " · inativa"}
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        <Link
          href={`/connections/${connection.id}`}
          className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover"
        >
          <MessageSquare className="h-3.5 w-3.5" /> Abrir chat
        </Link>
        <Link
          href={`/connections/${connection.id}/metadata`}
          className={ghostBtn}
        >
          Metadados
        </Link>
        <button type="button" onClick={onReintrospect} disabled={busy !== null} className={ghostBtn}>
          {busy === "introspect" ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          Sincronizar
        </button>
        <button type="button" onClick={onEdit} disabled={busy !== null} className={ghostBtn}>
          <Pencil className="h-3.5 w-3.5" /> Editar
        </button>
        <button
          type="button"
          onClick={onDelete}
          disabled={busy !== null}
          className="ml-auto flex items-center gap-1.5 rounded-lg border border-error/30 px-3 py-1.5 text-xs text-error transition-colors hover:bg-error/10 disabled:opacity-40"
        >
          {busy === "delete" ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Trash2 className="h-3.5 w-3.5" />
          )}
          Remover
        </button>
      </div>
    </div>
  );
}
