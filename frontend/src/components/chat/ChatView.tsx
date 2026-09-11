"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { ApiError, listConnections } from "@/lib/api";
import type { Connection } from "@/lib/types";
import { ChatContainer } from "./ChatContainer";
import { ConnectionSelector } from "./ConnectionSelector";

export function ChatView({ connectionId }: { connectionId: string }) {
  const router = useRouter();
  const [connections, setConnections] = useState<Connection[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listConnections()
      .then(setConnections)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Falha ao carregar as conexões."));
  }, []);

  if (error) {
    return <CenteredMessage>{error}</CenteredMessage>;
  }
  if (connections === null) {
    return (
      <CenteredMessage>
        <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
      </CenteredMessage>
    );
  }

  const current = connections.find((c) => c.id === connectionId);
  if (!current) {
    return (
      <CenteredMessage>
        <p>Conexão não encontrada.</p>
        <Link href="/connections" className="mt-2 text-sm text-accent-text hover:text-accent">
          Ver conexões
        </Link>
      </CenteredMessage>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-bg-base">
      <div className="flex items-center gap-3 border-b border-border-subtle bg-bg-surface px-4 py-2">
        <Link href="/connections" aria-label="Início" className="hidden sm:block">
          <Logo size="sm" withIcon />
        </Link>
        <div className="mx-auto flex items-center gap-3">
          <ConnectionSelector
            connections={connections}
            currentId={connectionId}
            onSelect={(id) => router.push(`/connections/${id}`)}
          />
          <Link
            href={`/connections/${connectionId}/metadata`}
            className="hidden text-xs text-text-secondary hover:text-text-primary sm:block"
          >
            Metadados
          </Link>
        </div>
        <ThemeToggle />
      </div>
      <ChatContainer key={connectionId} connectionId={connectionId} connectionName={current.name} />
    </div>
  );
}

function CenteredMessage({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-1 bg-bg-base p-8 text-center text-text-secondary">
      {children}
    </div>
  );
}
