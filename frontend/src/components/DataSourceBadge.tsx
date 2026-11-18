import { cn } from "@/lib/utils";

interface DataSourceBadgeProps {
  label: string;
  detail?: string;
  tone?: "live" | "mixed" | "static";
}

const TONES = {
  live: "border-pos/30 bg-pos/[0.08] text-pos",
  mixed: "border-accent/30 bg-accent/[0.08] text-accent",
  static: "border-white/10 bg-white/[0.03] text-ink-soft",
};

export function DataSourceBadge({ label, detail, tone = "live" }: DataSourceBadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md border px-2.5 py-1 text-[11px]",
        TONES[tone]
      )}
    >
      <span className="font-mono uppercase tracking-wide opacity-70">source</span>
      <span className="font-medium">{label}</span>
      {detail ? <span className="text-ink-soft">{detail}</span> : null}
    </div>
  );
}
