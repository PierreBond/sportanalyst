"use client";

import { useEffect, useState } from "react";
import { getValueBets } from "@/lib/api";
import type { ValueBet } from "@/types";

export default function ValueBetsPage() {
  const [valueBets, setValueBets] = useState<ValueBet[]>([]);
  const [loading, setLoading] = useState(true);
  const [date, setDate] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"edge" | "kelly">("edge");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadValueBets() {
      try {
        const data = await getValueBets(date || undefined);
        setValueBets(data.value_bets);
        setError(null);
      } catch (err) {
        setError("Failed to load value bets");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    loadValueBets();
  }, [date]);

  const sortedBets = [...valueBets].sort((a, b) => {
    if (sortBy === "edge") {
      return b.edge - a.edge;
    }
    return b.kelly_stake_pct - a.kelly_stake_pct;
  });

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="h-12 bg-gray-200 rounded mb-6"></div>
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Value Bets</h1>
        <p className="text-gray-500 mt-1">
          Positive expected value betting opportunities
        </p>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-600">{error}</p>
        </div>
      )}

      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <input
            type="date"
            value={date || ""}
            onChange={(e) => setDate(e.target.value || null)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={() => setDate(null)}
            className="px-4 py-2 text-sm text-blue-600 hover:text-blue-800"
          >
            Show all dates
          </button>
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-sm text-gray-500">Sort by:</span>
          <button
            onClick={() => setSortBy("edge")}
            className={`px-3 py-1 rounded-lg text-sm ${
              sortBy === "edge"
                ? "bg-blue-100 text-blue-700"
                : "bg-gray-100 text-gray-600"
            }`}
          >
            Edge
          </button>
          <button
            onClick={() => setSortBy("kelly")}
            className={`px-3 py-1 rounded-lg text-sm ${
              sortBy === "kelly"
                ? "bg-blue-100 text-blue-700"
                : "bg-gray-100 text-gray-600"
            }`}
          >
            Kelly %
          </button>
        </div>
      </div>

      {sortedBets.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <div className="text-gray-400 mb-4">
            <svg
              className="w-16 h-16 mx-auto"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            No Value Bets Found
          </h3>
          <p className="text-gray-500">
            No positive expected value bets at the current threshold
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Match
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Selection
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Model Prob
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Odds
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Implied
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Edge
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Kelly
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Sportsbook
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {sortedBets.map((bet, index) => (
                  <tr
                    key={index}
                    className={index % 2 === 0 ? "bg-white" : "bg-gray-50"}
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <a
                        href={`/matches/${bet.match_id}`}
                        className="text-blue-600 hover:text-blue-800 font-medium"
                      >
                        {bet.match_id}
                      </a>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-sm font-semibold">
                        {bet.selection.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {(bet.model_prob * 100).toFixed(1)}%
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">
                      {bet.best_odds.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {(bet.implied_prob * 100).toFixed(1)}%
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-sm font-bold">
                        +{(bet.edge * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {bet.kelly_stake_pct.toFixed(2)}%
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {bet.sportsbook}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">Total Opportunities</div>
          <div className="text-2xl font-bold text-gray-900">
            {sortedBets.length}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">Avg Edge</div>
          <div className="text-2xl font-bold text-green-600">
            {sortedBets.length > 0
              ? `+${(
                  (sortedBets.reduce((sum, b) => sum + b.edge, 0) /
                    sortedBets.length) *
                  100
                ).toFixed(1)}%`
              : "0%"}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">Total Kelly Exposure</div>
          <div className="text-2xl font-bold text-gray-900">
            {sortedBets
              .reduce((sum, b) => sum + b.kelly_stake_pct, 0)
              .toFixed(1)}
            %
          </div>
        </div>
      </div>
    </div>
  );
}
