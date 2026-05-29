interface DataSourceBadgeProps {
  label: string;
  detail?: string;
  tone?: "live" | "mixed" | "static";
}

export function DataSourceBadge({ label, detail, tone = "live" }: DataSourceBadgeProps) {
  const toneClass =
    tone === "live"
      ? "bg-green-100 text-green-800 border-green-200"
      : tone === "mixed"
      ? "bg-amber-100 text-amber-800 border-amber-200"
      : "bg-gray-100 text-gray-700 border-gray-200";

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full border text-xs ${toneClass}`}>
      <span className="font-semibold">Data source:</span>
      <span>{label}</span>
      {detail && <span className="opacity-80">({detail})</span>}
    </div>
  );
}
