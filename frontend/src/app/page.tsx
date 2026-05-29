"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { DataSourceBadge } from "@/components/DataSourceBadge";
import { getPrediction, getUpcomingMatches, getValueBets } from "@/lib/api";
import type { PredictionResponse, UpcomingMatch } from "@/types";

export default function HomePage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [upcomingMatches, setUpcomingMatches] = useState<UpcomingMatch[]>([]);
  const [predictions, setPredictions] = useState<PredictionResponse[]>([]);
  const [valueBetCount, setValueBetCount] = useState(0);

  useEffect(() => {
    async function loadOverviewData() {
      setLoading(true);
      try {
        const fixtures = await getUpcomingMatches(12);
        setUpcomingMatches(fixtures.matches);

        const predictionResults = await Promise.allSettled(
          fixtures.matches.slice(0, 6).map((match) => getPrediction(match.match_id))
        );

        const livePredictions = predictionResults
          .filter(
            (result): result is PromiseFulfilledResult<PredictionResponse> =>
              result.status === "fulfilled"
          )
          .map((result) => result.value);

        setPredictions(livePredictions);

        const valueBets = await getValueBets(undefined, 0.03);
        setValueBetCount(valueBets.value_bets.length);
        setError(null);
      } catch {
        setError("Failed to load live overview data");
      } finally {
        setLoading(false);
      }
    }

    loadOverviewData();
  }, []);

  const predictionByMatchId = useMemo(() => {
    const table = new Map<string, PredictionResponse>();
    for (const prediction of predictions) {
      table.set(prediction.match_id, prediction);
    }
    return table;
  }, [predictions]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-gray-900">Overview</h2>
        <p className="mt-2 text-gray-600">
          Live rollup from upcoming fixtures, prediction, and market endpoints.
        </p>
        <div className="mt-3">
          <DataSourceBadge
            label="Live API"
            detail="overview cards and fixtures are hydrated from backend endpoints"
            tone="live"
          />
        </div>
        <div className="mt-4 flex gap-3">
          <Link href="/matches" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">
            Open Live Matches
          </Link>
          <Link href="/market" className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm">
            Open Live Market
          </Link>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Active Predictions
          </h3>
          <p className="text-4xl font-bold text-blue-600">{predictions.length}</p>
          <p className="text-sm text-gray-500 mt-1">Prediction cards loaded</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Upcoming Fixtures
          </h3>
          <p className="text-4xl font-bold text-green-600">{upcomingMatches.length}</p>
          <p className="text-sm text-gray-500 mt-1">Rows from /api/v1/matches/upcoming</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Value Bets
          </h3>
          <p className="text-4xl font-bold text-purple-600">{valueBetCount}</p>
          <p className="text-sm text-gray-500 mt-1">Positive EV opportunities</p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">
            Upcoming Matches
          </h3>
        </div>
        {loading ? (
          <div className="px-6 py-8 text-gray-500">Loading live fixtures...</div>
        ) : upcomingMatches.length === 0 ? (
          <div className="px-6 py-8 text-gray-500">No upcoming matches returned by backend.</div>
        ) : (
          <div className="divide-y divide-gray-200">
            {upcomingMatches.slice(0, 8).map((match) => {
              const prediction = predictionByMatchId.get(match.match_id);
              return (
                <div key={match.match_id} className="px-6 py-4">
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center space-x-4">
                      <span className="font-medium">{match.home_team}</span>
                      <span className="text-gray-400">vs</span>
                      <span className="font-medium">{match.away_team}</span>
                    </div>
                    <div className="flex items-center space-x-4">
                      <span className="text-sm text-gray-500">
                        {new Date(match.scheduled_at).toLocaleString()}
                      </span>
                      {prediction ? (
                        <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                          {(prediction.probabilities.home_win * 100).toFixed(0)}% / {(prediction.probabilities.draw * 100).toFixed(0)}% / {(prediction.probabilities.away_win * 100).toFixed(0)}%
                        </span>
                      ) : (
                        <span className="px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-sm">
                          Prediction unavailable
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
