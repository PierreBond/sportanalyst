import { cn } from "@/lib/utils";

export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-xl border border-white/[0.07] bg-surface", className)}>
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  context,
  action,
}: {
  title: string;
  context?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-white/[0.07] px-5 py-4">
      <div className="flex items-baseline gap-3">
        <h2 className="text-[15px] font-medium text-ink">{title}</h2>
        {context ? <span className="text-xs text-ink-mute">{context}</span> : null}
      </div>
      {action}
    </div>
  );
}

export function StatCard({
  label,
  value,
  note,
  tone = "plain",
}: {
  label: string;
  value: string | number;
  note?: string;
  tone?: "plain" | "accent" | "pos" | "neg";
}) {
  const toneClass = {
    plain: "text-ink",
    accent: "text-accent",
    pos: "text-pos",
    neg: "text-neg",
  }[tone];

  return (
    <div className="rounded-xl border border-white/[0.07] bg-surface px-5 py-4">
      <p className="text-xs text-ink-mute">{label}</p>
      <p className={cn("tnum mt-2 font-mono text-[26px] leading-none", toneClass)}>{value}</p>
      {note ? <p className="mt-2 text-xs leading-relaxed text-ink-soft">{note}</p> : null}
    </div>
  );
}

export function SectionHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-[26px] font-medium leading-tight tracking-tight text-ink">
          {title}
        </h1>
        {description ? (
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-soft">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-xl border border-dashed border-white/[0.1] bg-surface/50 px-6 py-14 text-center">
      <h3 className="text-[15px] font-medium text-ink">{title}</h3>
      <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-ink-soft">
        {description}
      </p>
    </div>
  );
}

export function ErrorNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-6 rounded-lg border border-neg/30 bg-neg/[0.08] px-4 py-3 text-sm text-neg">
      {children}
    </div>
  );
}
