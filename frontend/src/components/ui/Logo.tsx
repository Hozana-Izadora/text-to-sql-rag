interface LogoProps {
  size?: "sm" | "lg";
  withIcon?: boolean;
  className?: string;
}

const SIZES = {
  sm: { text: "text-[15px]", icon: 18 },
  lg: { text: "text-3xl", icon: 34 },
} as const;

export function InquiroMark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
      <circle cx="13" cy="13" r="9" stroke="var(--accent)" strokeWidth="2.5" />
      <line
        x1="19.6"
        y1="19.6"
        x2="27"
        y2="27"
        stroke="var(--accent)"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <path
        d="M13 8.5 L8.8 15.6 L17.2 15.6 Z"
        stroke="var(--accent)"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      <circle cx="13" cy="8.5" r="1.9" fill="var(--accent)" />
      <circle cx="8.8" cy="15.6" r="1.9" fill="var(--accent)" />
      <circle cx="17.2" cy="15.6" r="1.9" fill="var(--accent)" />
    </svg>
  );
}

/** Wordmark "inquiro" — "in" em violeta (accent), o resto em text-primary. */
export function Logo({ size = "sm", withIcon = false, className = "" }: LogoProps) {
  const s = SIZES[size];
  return (
    <span
      className={`inline-flex items-center gap-2 font-semibold tracking-tight ${s.text} ${className}`}
    >
      {withIcon && <InquiroMark size={s.icon} />}
      <span className="lowercase">
        <span className="text-accent">in</span>
        <span className="text-text-primary">quiro</span>
      </span>
    </span>
  );
}
