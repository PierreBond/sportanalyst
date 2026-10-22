"use client";

import type { MarketsResponse } from "@/types";

const PCT = (p: number) => `${(p * 100).toFixed(1)}%`;

export function MarketsPanel({ markets }: { markets: MarketsResponse }) {
  return (
    <div className="bg-white rounded-lg shadow p-6" data-testid="markets-panel">
      <div className="flex justify-between items-baseline mb-4">
        <h2 className="text-xl font-semibold text-gray-900">Goal Markets</h2>
        <span className="text-xs text-gray-400" title="Derived from the Poisson goal model trained on final scores, not shot-based xG">
          xG type: {markets.xg_type}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center p-4 bg-blue-50 rounded-lg">
          <div className="text-xs text-gray-500 mb-1">xG Home</div>
          <div className="text-3xl font-bold text-blue-600">{markets.xg.home.toFixed(2)}</div>
        </div>
        <div className="text-center p-4 bg-purple-50 rounded-lg">
          <div className="text-xs text-gray-500 mb-1">Total xG</div>
          <div className="text-3xl font-bold text-purple-600">{markets.xg.total.toFixed(2)}</div>
        </div>
        <div className="text-center p-4 bg-red-50 rounded-lg">
          <div className="text-xs text-gray-500 mb-1">xG Away</div>
          <div className="text-3xl font-bold text-red-600">{markets.xg.away.toFixed(2)}</div>
        </div>
      </div>

      <table className="w-full text-sm mb-4">
        <thead>
          <tr className="border-b border-gray-200">
            <td className="py-1 text-gray-500">Both teams to score</td>
            <td className="py-1 text-right font-semibold">{PCT(markets.btts)}</td>
          </tr>
          {markets.totals.map((t) => (
            <tr key={t.line} className="border-b border-gray-100">
              <td className="py-1 text-gray-500">Over {t.line.toFixed(1)} goals</td>
              <td className="py-1 text-right font-semibold">{PCT(t.p_over)}</td>
            </tr>
          ))}
        </thead>
      </table>

      <h3 className="text-sm font-semibold text-gray-700 mb-2">Most likely scores</h3>
      <div className="flex gap-2 flex-wrap">
        {markets.correct_scores.map((s) => (
          <span
            key={s.score}
            className="px-3 py-1.5 bg-gray-100 rounded-lg text-sm"
          >
            <span className="font-semibold">{s.score}</span>{" "}
            <span className="text-gray-500">{PCT(s.prob)}</span>
          </span>
        ))}
      </div>

      <p className="mt-4 pt-3 border-t border-gray-100 text-xs text-gray-400">
        Backtested (513 matches, 2026): totals and BTTS accuracy ≈ league base
        rates — treat as goal-model analytics, not a betting edge.
      </p>
    </div>
  );
}
