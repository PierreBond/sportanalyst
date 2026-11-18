"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Card, CardHeader, ErrorNote, SectionHeader, StatCard } from "@/components/ui";
import { getBatchPredictions, getModels, getUpcomingMatches, getValueBets } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import type { ModelInfo, PredictionResponse, UpcomingMatch } from "@/types";

export default function HomePage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [upcomingMatches, setUpcomingMatches] = useState<UpcomingMatch[]>([]);
  const [predictions, setPredictions] = useState<PredictionResponse[]>([]);
  const [valueBetCount, setValueBetCount] = useState(0);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);

  useEffect(() => {
    async function loadOverviewData() {
      setLoading(true);
      try {
        const [fixtures, models] = await Promise.all([
          getUpcomingMatches(100),
          getModels(),
        ]);
        setUpcomingMatches(fixtures.matches);
        setModelInfo(models.models[0] || null);

        const { predictions: livePredictions } = await getBatchPredictions(
          fixtures.matches.map((m) => m.match_id)
        );
        setPredictions(livePredictions);

        const valueBets = await getValueBets(undefined, 0.03);
        setValueBetCount(valueBets.value_bets.length);
        setError(null);
      } catch {
        setError("Could not reach the model server. Start the backend and reload.");
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

  const settlement = modelInfo?.settlement;
  const ledger = modelInfo?.value_bets_ledger;

  return (
    <div className="animate-rise">
      <SectionHeader
        title="Overview"
        description="What the model currently believes, how it performs out of sample, and where it disagrees with the market."
        actions={
          <Link
            href="/value-bets"
            className="rounded-lg border border-accent/40 bg-accent/10 px-3.5 py-2 text-[13px] font-medium text-accent transition-colors duration-150 ease-out hover:bg-accent/15"
          >
            Open the board
          </Link>
        }
      />

      {error ? <ErrorNote>{error}</ErrorNote> : null}

      <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="Held-out accuracy"
          value={modelInfo ? `${(modelInfo.accuracy * 100).toFixed(1)}%` : "—"}
          tone="accent"
          note={
            modelInfo
              ? modelInfo.accuracy_base_rate != null
                ? `${(modelInfo.accuracy_base_rate * 100).toFixed(1)}% base rate on the same season`
                : `${modelInfo.n_matches.toLocaleString()} matches, ${modelInfo.n_features} features`
              : "waiting for the model card"
          }
        />
        <StatCard
          label="Brier score"
          value={modelInfo ? modelInfo.brier_score.toFixed(3) : "—"}
          note="lower is better, 0.667 is coin-flip 1X2"
        />
        <StatCard
          label="Fixtures loaded"
          value={upcomingMatches.length}
          note={`${predictions.length} with a served prediction`}
        />
        <StatCard
          label="Market disagreements"
          value={valueBetCount}
          note="edge of 3% or more on the board"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
        <Card className="overflow-hidden">
          <CardHeader
            title="Next fixtures"
            context={modelInfo ? modelInfo.version : undefined}
          />
          {loading ? (
            <p className="px-5 py-10 text-center text-[13px] text-ink-soft">
              Loading fixtures…
            </p>
          ) : upcomingMatches.length === 0 ? (
            <p className="px-5 py-10 text-center text-[13px] text-ink-soft">
              No upcoming fixtures in the database.
            </p>
          ) : (
            <ul className="divide-y divide-white/[0.05]">
              {upcomingMatches.slice(0, 12).map((match) => {
                const prediction = predictionByMatchId.get(match.match_id);
                return (
                  <li
                    key={match.match_id}
                    className="flex flex-wrap items-center justify-between gap-3 px-5 py-3"
                  >
                    <Link
                      href={`/matches/${match.match_id}`}
                      className="text-[13.5px] text-ink underline-offset-4 hover:underline"
                    >
                      {match.home_team}
                      <span className="px-1.5 text-ink-mute">vs</span>
                      {match.away_team}
                    </Link>
                    <div className="flex items-center gap-4">
                      <span className="tnum font-mono text-[11px] text-ink-mute">
                        {formatDateTime(match.scheduled_at)}
                      </span>
                      {prediction ? (
                        <span className="tnum font-mono text-[12px] text-ink-soft">
                          {(prediction.probabilities.home_win * 100).toFixed(0)}/
                          {(prediction.probabilities.draw * 100).toFixed(0)}/
                          {(prediction.probabilities.away_win * 100).toFixed(0)}
                        </span>
                      ) : (
                        <span className="text-[11px] text-ink-mute">no prediction</span>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Model card" />
            <dl className="divide-y divide-white/[0.05] px-5">
              <Row label="Version" value={modelInfo?.version ?? "—"} />
              <Row label="Trained" value={modelInfo?.trained_at?.slice(0, 10) ?? "—"} />
              <Row
                label="Training matches"
                value={modelInfo ? modelInfo.n_matches.toLocaleString() : "—"}
              />
              <Row
                label="Settled predictions"
                value={settlement?.model?.n ? String(settlement.model.n) : "none yet"}
              />
              <Row
                label="Model Brier (settled)"
                value={
                  settlement?.model?.brier != null
                    ? settlement.model.brier.toFixed(3)
                    : "—"
                }
              />
              <Row
                label="Market Brier (same rows)"
                value={
                  settlement?.market_on_model?.brier != null
                    ? settlement.market_on_model.brier.toFixed(3)
                    : "—"
                }
              />
            </dl>
          </Card>

          <Card>
            <CardHeader title="Bet ledger" context="discontinued" />
            <div className="px-5 py-4">
              <p className="text-[13px] leading-relaxed text-ink-soft">
                The forward-test ledger is closed. It settled{" "}
                {ledger?.settled ?? 0} bets for a{" "}
                {((ledger?.bankroll_return_pct ?? 0) * 100).toFixed(2)}% return, so the
                board is for study, not for blind staking.
              </p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5">
      <dt className="text-[13px] text-ink-soft">{label}</dt>
      <dd className="tnum font-mono text-[13px] text-ink">{value}</dd>
    </div>
  );
}
