"use client";

import { Check, ChevronDown, Database } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { dbTypeInfo } from "@/lib/dbTypes";
import type { Connection } from "@/lib/types";

interface ConnectionSelectorProps {
  connections: Connection[];
  currentId: string;
  onSelect: (id: string) => void;
}

export function ConnectionSelector({ connections, currentId, onSelect }: ConnectionSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = connections.find((c) => c.id === currentId);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-lg border border-border-subtle bg-bg-surface px-3 py-1.5 text-sm text-text-primary transition-colors hover:bg-bg-elevated"
      >
        <span aria-hidden>{current ? dbTypeInfo(current.db_type).icon : <Database className="h-4 w-4" />}</span>
        <span className="max-w-[40vw] truncate font-medium">{current?.name ?? "Selecionar conexão"}</span>
        <ChevronDown className="h-4 w-4 text-text-muted" />
      </button>

      {open && (
        <div className="animate-in absolute left-0 z-20 mt-1 w-72 rounded-lg border border-border-subtle bg-bg-elevated py-1 shadow-lg">
          {connections.map((connection) => (
            <button
              key={connection.id}
              type="button"
              onClick={() => {
                setOpen(false);
                if (connection.id !== currentId) onSelect(connection.id);
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-bg-surface"
            >
              <span aria-hidden>{dbTypeInfo(connection.db_type).icon}</span>
              <span className="flex-1 truncate text-text-primary">{connection.name}</span>
              {connection.id === currentId && <Check className="h-4 w-4 text-accent" />}
            </button>
          ))}
          <div className="mt-1 border-t border-border-subtle px-3 pt-1.5">
            <Link href="/connections" className="text-xs text-accent-text hover:text-accent">
              Gerenciar conexões
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
