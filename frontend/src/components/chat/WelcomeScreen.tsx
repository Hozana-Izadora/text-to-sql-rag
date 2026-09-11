"use client";

import { Logo } from "@/components/ui/Logo";

const SUGGESTIONS = [
  "Qual o total de prêmios das apólices vigentes?",
  "Quais sinistros estão em análise?",
  "Mostre um gráfico de comissões por corretor",
];

interface WelcomeScreenProps {
  connectionName: string;
  onPick: (text: string) => void;
}

export function WelcomeScreen({ connectionName, onPick }: WelcomeScreenProps) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto px-4 py-10 text-center">
      <Logo size="lg" withIcon />
      <p className="mt-4 text-lg text-text-secondary">Da pergunta ao insight.</p>
      <p className="mt-1 max-w-md text-sm text-text-muted">
        Conectado a <span className="text-text-secondary">{connectionName}</span>. Pergunte em
        linguagem natural sobre os dados desse banco.
      </p>

      <div className="mt-8 grid w-full max-w-md gap-2">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onPick(suggestion)}
            className="rounded-card border border-border-subtle px-4 py-3 text-left text-sm text-text-secondary transition-colors hover:border-accent hover:bg-accent-subtle hover:text-text-primary"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}
