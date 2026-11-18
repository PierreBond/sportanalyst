"use client";

import type { MarketsResponse } from "@/types";

const PCT = (p: number) => `${(p * 100).toFixed(1)}%`;

export function MarketsPanel({ markets }: { markets: MarketsResponse }) {
  const xg = [
    { label: "xG home", value: markets.xg.home.toFixed(2) },
    { label: "xG away", value: markets.xg.away.toFixed(2) },
    { label: "Total xG", value: markets.xg.total.toFixed(2) },
  ];

  return (
    <section
      data-testid="markets-panel"
      className="rounded-xl border border-white/[0.07] bg-surface"
    >
      <div className="flex items-baseline justify-between gap-4 border-b border-white/[0.07] px-5 py-4">
        <h2 className="text-[15px] font-medium text-ink">Goal markets</h2>
        <span className="font-mono text-[11px] text-ink-mute">
          xG type: {markets.xg_type}
        </span>
      </div>

      <div className="grid grid-cols-3 divide-x divide-white/[0.07] border-b border-white/[0.07]">
        {xg.map((item) => (
          <div key={item.label} className="px-5 py-4">
            <p className="text-[11px] text-ink-mute">{item.label}</p>
            <p className="tnum mt-1.5 font-mono text-[22px] leading-none text-ink">
              {item.value}
            </p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-8 px-5 py-5 md:grid-cols-2">
        <div>
          <h3 className="text-[13px] font-medium text-ink">Goals and both sides</h3>
          <dl className="mt-3 divide-y divide-white/[0.05]">
            <div className="flex items-center justify-between py-2">
              <dt className="text-[13px] text-ink-soft">Both teams to score</dt>
              <dd className="tnum font-mono text-[13px] text-ink">{PCT(markets.btts)}</dd>
            </div>
            {markets.totals.map((t) => (
              <div key={t.line} className="flex items-center justify-between py-2">
                <dt className="text-[13px] text-ink-soft">
                  Over {t.line.toFixed(1)} goals
                </dt>
                <dd className="tnum font-mono text-[13px] text-ink">{PCT(t.p_over)}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div>
          <h3 className="text-[13px] font-medium text-ink">Most likely scores</h3>
          <ul className="mt-3 space-y-1.5">
            {markets.correct_scores.map((s) => (
              <li
                key={s.score}
                className="flex items-center justify-between rounded-lg bg-white/[0.02] px-3 py-2"
              >
                <span className="tnum font-mono text-[13px] text-ink">{s.score}</span>
                <span className="tnum font-mono text-[13px] text-ink-soft">{PCT(s.prob)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <p className="border-t border-white/[0.07] px-5 py-3 text-[11px] leading-relaxed text-ink-mute">
        Backtested (513 matches, 2026): totals and BTTS accuracy is about league base
        rates. Goal-model analytics, not a betting edge.
      </p>
    </section>
  );
}
