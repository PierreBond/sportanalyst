"use client";

import { useEffect, useState } from "react";
import { getPrediction, getUpcomingLeagues, getUpcomingMatches } from "@/lib/api";
import { PredictionCard } from "@/components/PredictionCard";
import { DataSourceBadge } from "@/components/DataSourceBadge";
import type { PredictionResponse } from "@/types";

type LeagueOption = {
  league: string;
  match_count: number;
};

export default function MatchesPage() {
  const [predictions, setPredictions] = useState<PredictionResponse[]>([]);
  const [leagues, setLeagues] = useState<LeagueOption[]>([]);
  const [selectedLeague, setSelectedLeague] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadPredictions() {
      setLoading(true);
      setError(null);
      try {
        const [leagueData, fixtures] = await Promise.all([
          getUpcomingLeagues(),
          getUpcomingMatches(20, selectedLeague === "all" ? undefined : selectedLeague),
        ]);

        if (leagueData.leagues.length === 0) {
          setLeagues([]);
          setError("No leagues available - please check data ingestion");
          setPredictions([]);
          setLoading(false);
          return;
        }

        setLeagues(leagueData.leagues);
        const matchIds = fixtures.matches.map((m) => m.match_id);

        if (matchIds.length === 0) {
          setPredictions([]);
          setError(
            selectedLeague === "all"
              ? "No upcoming fixtures found in database"
              : `No upcoming fixtures for ${selectedLeague.replaceAll("_", " ")}`
          );
          return;
        }

        const results = await Promise.allSettled(matchIds.map((id) => getPrediction(id)));
        const loaded = results
          .filter((r): r is PromiseFulfilledResult<PredictionResponse> => r.status === "fulfilled")
          .map((r) => r.value);

        setPredictions(loaded);
        setError(loaded.length === 0 ? "No live predictions returned by backend" : null);
      } catch (err) {
        setError("Failed to load live predictions");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    loadPredictions();
  }, [selectedLeague]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/3 mb-6"></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="h-44 bg-gray-200 rounded"></div>
            <div className="h-44 bg-gray-200 rounded"></div>
            <div className="h-44 bg-gray-200 rounded"></div>
            <div className="h-44 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Live Match Predictions</h1>
        <p className="text-gray-500 mt-1">
          API-driven predictions from model-serving, hydrated from real fixture rows when available.
        </p>
        <div className="mt-3">
          <DataSourceBadge
            label="Live API"
            detail="fixtures + predictions endpoints are live; labels come from matches/teams ingestion tables"
            tone="live"
          />
        </div>
        <div className="mt-4 flex items-center gap-3">
          <label htmlFor="league-filter" className="text-sm text-gray-600">
            League
          </label>
          <select
            id="league-filter"
            value={selectedLeague}
            onChange={(e) => setSelectedLeague(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="all">All leagues</option>
            {leagues.map((item) => (
              <option key={item.league} value={item.league}>
                {item.league.replaceAll("_", " ")} ({item.match_count})
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-600">{error}</p>
        </div>
      )}

      {predictions.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-10 text-center text-gray-500">
          No prediction cards to display.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {predictions.map((prediction) => (
            <PredictionCard key={prediction.match_id} prediction={prediction} />
          ))}
        </div>
      )}
    </div>
  );
}
