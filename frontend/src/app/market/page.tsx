"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getValueBets } from "@/lib/api";
import { DataSourceBadge } from "@/components/DataSourceBadge";
import type { ValueBet } from "@/types";

type SortKey = "edge" | "kelly" | "odds";

export default function MarketPage() {
  const [valueBets, setValueBets] = useState<ValueBet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [date, setDate] = useState<string | null>(null);
  const [minEdgePct, setMinEdgePct] = useState(2);
  const [sortBy, setSortBy] = useState<SortKey>("edge");

  useEffect(() => {
    async function loadMarketData() {
      setLoading(true);
      try {
        const data = await getValueBets(date || undefined, minEdgePct / 100);
        setValueBets(data.value_bets);
        setError(null);
      } catch (err) {
        setError("Failed to load market opportunities");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    loadMarketData();
  }, [date, minEdgePct]);

  const sortedBets = useMemo(() => {
    const bets = [...valueBets];

    bets.sort((a, b) => {
      if (sortBy === "edge") return b.edge - a.edge;
      if (sortBy === "kelly") return b.kelly_stake_pct - a.kelly_stake_pct;
      return b.best_odds - a.best_odds;
    });

    return bets;
  }, [valueBets, sortBy]);

  const summary = useMemo(() => {
    if (sortedBets.length === 0) {
      return {
        total: 0,
        avgEdgePct: 0,
        totalKellyPct: 0,
        avgOdds: 0,
      };
    }

    const total = sortedBets.length;
    const totalEdge = sortedBets.reduce((sum, bet) => sum + bet.edge, 0);
    const totalKelly = sortedBets.reduce((sum, bet) => sum + bet.kelly_stake_pct, 0);
    const totalOdds = sortedBets.reduce((sum, bet) => sum + bet.best_odds, 0);

    return {
      total,
      avgEdgePct: (totalEdge / total) * 100,
      totalKellyPct: totalKelly,
      avgOdds: totalOdds / total,
    };
  }, [sortedBets]);

  const topSportsbooks = useMemo(() => {
    const counts: Record<string, number> = {};

    for (const bet of sortedBets) {
      counts[bet.sportsbook] = (counts[bet.sportsbook] || 0) + 1;
    }

    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4);
  }, [sortedBets]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="h-24 bg-gray-200 rounded mb-6"></div>
          <div className="h-72 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Market Intelligence</h1>
        <p className="text-gray-500 mt-1">
          Real-time pricing inefficiencies and position sizing guidance
        </p>
        <div className="mt-3">
          <DataSourceBadge
            label="Live API"
            detail="value-bets endpoint responds live; content may be simulated by backend"
            tone="mixed"
          />
        </div>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-600">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">Opportunities</div>
          <div className="text-2xl font-bold text-gray-900">{summary.total}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">Average Edge</div>
          <div className="text-2xl font-bold text-green-600">
            +{summary.avgEdgePct.toFixed(2)}%
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">Total Kelly</div>
          <div className="text-2xl font-bold text-gray-900">
            {summary.totalKellyPct.toFixed(2)}%
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">Average Odds</div>
          <div className="text-2xl font-bold text-blue-600">{summary.avgOdds.toFixed(2)}</div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <label className="block">
            <span className="text-sm text-gray-600">Date</span>
            <input
              type="date"
              value={date || ""}
              onChange={(e) => setDate(e.target.value || null)}
              className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg"
            />
          </label>

          <label className="block">
            <span className="text-sm text-gray-600">Min Edge: {minEdgePct}%</span>
            <input
              type="range"
              min={0}
              max={15}
              step={1}
              value={minEdgePct}
              onChange={(e) => setMinEdgePct(Number(e.target.value))}
              className="mt-2 w-full"
            />
          </label>

          <label className="block">
            <span className="text-sm text-gray-600">Sort</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortKey)}
              className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="edge">Edge</option>
              <option value="kelly">Kelly %</option>
              <option value="odds">Best Odds</option>
            </select>
          </label>

          <button
            onClick={() => {
              setDate(null);
              setMinEdgePct(2);
              setSortBy("edge");
            }}
            className="px-4 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
          >
            Reset Filters
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-lg shadow overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Best Market Edges</h2>
          </div>

          {sortedBets.length === 0 ? (
            <div className="p-8 text-center text-gray-500">No opportunities match current filters.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Match</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Pick</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Odds</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Edge</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Kelly</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {sortedBets.map((bet, idx) => (
                    <tr key={`${bet.match_id}-${bet.selection}-${idx}`} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm">
                        <Link href={`/matches/${bet.match_id}`} className="text-blue-600 hover:text-blue-800">
                          {bet.match_id}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">
                        {bet.selection.toUpperCase()}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">{bet.best_odds.toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm font-semibold text-green-700">
                        +{(bet.edge * 100).toFixed(2)}%
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">
                        {bet.kelly_stake_pct.toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Top Sportsbooks</h2>
          {topSportsbooks.length === 0 ? (
            <p className="text-sm text-gray-500">No sportsbook data available.</p>
          ) : (
            <ul className="space-y-3">
              {topSportsbooks.map(([name, count]) => (
                <li key={name} className="flex items-center justify-between">
                  <span className="text-sm text-gray-700">{name}</span>
                  <span className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded-full">
                    {count}
                  </span>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-6 p-3 rounded-lg bg-amber-50 border border-amber-200">
            <p className="text-xs text-amber-800">
              Sizing uses Kelly percentages from model edge and current market price. Cap exposure per slate
              according to your bankroll policy.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
