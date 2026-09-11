import Link from "next/link";
import type { ReactNode } from "react";
import { Logo } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

interface AppHeaderProps {
  /** Ações à direita, antes do toggle de tema (ex.: botão "Nova conexão"). */
  children?: ReactNode;
  /** Link de "voltar" à esquerda, quando a página é uma sub-rota. */
  back?: { href: string; label: string };
}

export function AppHeader({ children, back }: AppHeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-border-subtle bg-bg-surface px-4 py-3">
      <div className="flex items-center gap-3">
        <Link href="/connections" aria-label="Início">
          <Logo size="sm" withIcon />
        </Link>
        {back && (
          <>
            <span className="text-border-strong">/</span>
            <Link href={back.href} className="text-sm text-accent-text hover:text-accent">
              {back.label}
            </Link>
          </>
        )}
      </div>
      <div className="flex items-center gap-2 text-sm">
        {children}
        <ThemeToggle />
      </div>
    </header>
  );
}
