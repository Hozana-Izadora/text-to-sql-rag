export function LoadingDots() {
  return (
    <span
      className="dot-bounce inline-flex items-center gap-1"
      aria-label="Carregando"
      role="status"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-accent-text" />
      <span className="h-1.5 w-1.5 rounded-full bg-accent-text" />
      <span className="h-1.5 w-1.5 rounded-full bg-accent-text" />
    </span>
  );
}
