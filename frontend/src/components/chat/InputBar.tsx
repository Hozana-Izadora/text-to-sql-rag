"use client";

import { Loader2, Send } from "lucide-react";
import { useRef, useState } from "react";

interface InputBarProps {
  onSubmit: (question: string) => void;
  isLoading: boolean;
}

const MAX_TEXTAREA_HEIGHT_PX = 120;

export function InputBar({ onSubmit, isLoading }: InputBarProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resetHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || isLoading) return;
    onSubmit(trimmed);
    setValue("");
    resetHeight();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  };

  const handleChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(event.target.value);
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, MAX_TEXTAREA_HEIGHT_PX)}px`;
    }
  };

  return (
    <div className="border-t border-border-subtle bg-bg-base px-4 py-4">
      <div className="mx-auto flex w-full max-w-[720px] items-end gap-2 rounded-xl border border-border-subtle bg-bg-surface p-2 transition-colors focus-within:border-accent">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          rows={1}
          placeholder="Pergunte sobre seus dados..."
          className="min-h-[28px] flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none disabled:opacity-40"
        />
        <button
          type="button"
          onClick={handleSubmit}
          disabled={isLoading || !value.trim()}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-accent text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Enviar pergunta"
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin [animation-duration:0.8s]" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </button>
      </div>
    </div>
  );
}
