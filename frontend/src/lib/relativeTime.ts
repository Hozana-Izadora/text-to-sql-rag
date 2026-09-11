/** "há 2h", "há 3 dias", "agora mesmo" — para o carimbo de última sincronização. */
export function relativeTime(iso: string | null): string {
  if (!iso) return "nunca";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "nunca";
  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 60) return "agora mesmo";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `há ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `há ${hours}h`;
  const days = Math.round(hours / 24);
  if (days < 30) return `há ${days} ${days === 1 ? "dia" : "dias"}`;
  const months = Math.round(days / 30);
  return `há ${months} ${months === 1 ? "mês" : "meses"}`;
}
