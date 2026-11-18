"use client";

import { useEffect, useState } from "react";
import { Card, EmptyState, ErrorNote, SectionHeader } from "@/components/ui";
import { getBatchPredictions, getUpcomingLeagues, getUpcomingMatches } from "@/lib/api";
import { PredictionCard } from "@/components/PredictionCard";
import { DataSourceBadge } from "@/components/DataSourceBadge";
import type { PredictionResponse } from "@/types";

export default function MatchesPage() {
  const [predictions, setPredictions] = useState<PredictionResponse[]>([]);
  const [leagues, setLeagues] = useState<{ league: string; match_count: number }[]>([]);
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
          getUpcomingMatches(100, selectedLeague === "all" ? undefined : selectedLeague),
        ]);

        setLeagues(leagueData.leagues);
        const matchIds = fixtures.matches.map((m) => m.match_id);

        if (matchIds.length === 0) {
          setPredictions([]);
          setError(
            selectedLeague === "all"
              ? "No upcoming fixtures found in the database."
              : `No upcoming fixtures for ${selectedLeague.replaceAll("_", " ")}.`
          );
          return;
        }

        const { predictions: loaded } = await getBatchPredictions(matchIds);
        setPredictions(loaded);
      } catch (err) {
        setError("Could not load predictions from the model server.");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    loadPredictions();
  }, [selectedLeague]);

  return (
    <div className="animate-rise">
      <SectionHeader
        title="Matches"
        description="Served predictions for the next hundred fixtures, newest kickoff first."
        actions={
          <label className="flex items-center gap-2 text-[13px] text-ink-soft">
            League
            <select
              value={selectedLeague}
              onChange={(event) => setSelectedLeague(event.target.value)}
              className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] text-ink outline-none focus:border-accent/60"
            >
              <option value="all">All leagues</option>
              {leagues.map((item) => (
                <option key={item.league} value={item.league}>
                  {item.league.replaceAll("_", " ")} ({item.match_count})
                </option>
              ))}
            </select>
          </label>
        }
      />

      <div className="mb-6">
        <DataSourceBadge
          label="Live API"
          detail="fixtures from the ingestion tables, probabilities from the model server"
          tone="live"
        />
      </div>

      {error ? <ErrorNote>{error}</ErrorNote> : null}

      {loading ? (
        <Card className="px-6 py-14 text-center text-[13px] text-ink-soft">
          Scoring fixtures…
        </Card>
      ) : predictions.length === 0 ? (
        <EmptyState
          title="No predictions yet"
          description="The backend returned no predictions for this league. Try another league or wait for the next fixture batch."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {predictions.map((prediction) => (
            <PredictionCard key={prediction.match_id} prediction={prediction} />
          ))}
        </div>
      )}
    </div>
  );
}
