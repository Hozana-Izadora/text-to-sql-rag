import { LoadingDots } from "@/components/ui/LoadingDots";

interface StatusIndicatorProps {
  status: string;
}

export function StatusIndicator({ status }: StatusIndicatorProps) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full bg-accent-subtle px-3 py-1.5 text-[13px] text-accent-text">
      <LoadingDots />
      <span>{status}</span>
    </div>
  );
}
