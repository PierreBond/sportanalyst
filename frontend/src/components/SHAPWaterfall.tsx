"use client";

import type { SHAPExplanation } from "@/types";

interface SHAPWaterfallProps {
  explanation: SHAPExplanation;
  maxItems?: number;
}

export function SHAPWaterfall({ explanation, maxItems = 5 }: SHAPWaterfallProps) {
  const positiveDrivers = explanation.positive_drivers.slice(0, maxItems);
  const negativeDrivers = explanation.negative_drivers.slice(0, maxItems);

  const maxImpact =
    Math.max(
      ...positiveDrivers.map((d) => d.impact),
      ...negativeDrivers.map((d) => Math.abs(d.impact))
    ) || 1;

  return (
    <section className="rounded-xl border border-white/[0.07] bg-surface">
      <div className="border-b border-white/[0.07] px-5 py-4">
        <h2 className="text-[15px] font-medium text-ink">Prediction Drivers (SHAP)</h2>
      </div>

      <div className="space-y-6 px-5 py-5">
        {positiveDrivers.length > 0 ? (
          <div>
            <h3 className="text-[13px] font-medium text-pos">Positive Factors</h3>
            <ul className="mt-3 space-y-3">
              {positiveDrivers.map((driver, index) => (
                <li key={`${driver.feature}-${index}`}>
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="truncate text-[13px] text-ink-soft">{driver.label}</span>
                    <span className="tnum shrink-0 font-mono text-[13px] text-pos">
                      +{(driver.impact * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-white/[0.05]">
                    <div
                      className="h-full rounded-full bg-pos/70"
                      style={{ width: `${(driver.impact / maxImpact) * 100}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {negativeDrivers.length > 0 ? (
          <div>
            <h3 className="text-[13px] font-medium text-neg">Negative Factors</h3>
            <ul className="mt-3 space-y-3">
              {negativeDrivers.map((driver, index) => (
                <li key={`${driver.feature}-${index}`}>
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="truncate text-[13px] text-ink-soft">{driver.label}</span>
                    <span className="tnum shrink-0 font-mono text-[13px] text-neg">
                      {(driver.impact * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-white/[0.05]">
                    <div
                      className="h-full rounded-full bg-neg/70"
                      style={{
                        width: `${(Math.abs(driver.impact) / maxImpact) * 100}%`,
                      }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {positiveDrivers.length === 0 && negativeDrivers.length === 0 ? (
          <p className="text-[13px] leading-relaxed text-ink-soft">
            No driver explanation available for this fixture. The current model is a
            linear scorer, so it does not publish per-feature attributions.
          </p>
        ) : null}
      </div>
    </section>
  );
}
