"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { SHAPWaterfall } from "@/components/SHAPWaterfall";
import { DataSourceBadge } from "@/components/DataSourceBadge";
import { MarketsPanel } from "@/components/MarketsPanel";
import { Card, CardHeader, ErrorNote, SectionHeader } from "@/components/ui";
import { getPrediction, getMarkets, getWebSocketUrl } from "@/lib/api";
import { useWebSocket } from "@/lib/ws";
import { formatDateTime } from "@/lib/utils";
import type { PredictionResponse, MarketsResponse } from "@/types";

export default function MatchDetailPage() {
  const params = useParams();
  const matchId = params.matchId as string;

  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [markets, setMarkets] = useState<MarketsResponse | null>(null);
  const [marketsError, setMarketsError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { connect, disconnect, isConnected } = useWebSocket({
    onMessage: (message) => {
      if (message.type === "prediction_update" && message.probabilities) {
        setPrediction((prev) =>
          prev ? { ...prev, probabilities: message.probabilities! } : null
        );
      }
    },
  });

  useEffect(() => {
    async function loadPrediction() {
      try {
        const data = await getPrediction(matchId);
        setPrediction(data);
        setError(null);
      } catch {
        setError("Could not load the prediction for this fixture.");
      } finally {
        setLoading(false);
      }

      try {
        setMarkets(await getMarkets(matchId));
      } catch {
        setMarketsError(true);
      }
    }

    loadPrediction();
  }, [matchId]);

  useEffect(() => {
    connect(getWebSocketUrl(matchId));
    return () => disconnect();
  }, [matchId, connect, disconnect]);

  if (loading) {
    return (
      <Card className="px-6 py-14 text-center text-[13px] text-ink-soft">
        Loading the forecast…
      </Card>
    );
  }

  if (error || !prediction) {
    return (
      <ErrorNote>{error || "Prediction not found for this fixture."}</ErrorNote>
    );
  }

  const outcomes = [
    { label: prediction.home_team, prob: prediction.probabilities.home_win },
    { label: "Draw", prob: prediction.probabilities.draw },
    { label: prediction.away_team, prob: prediction.probabilities.away_win },
  ];
  const maxProb = Math.max(
    prediction.probabilities.home_win,
    prediction.probabilities.draw,
    prediction.probabilities.away_win
  );

  return (
    <div className="animate-rise">
      <SectionHeader
        title={`${prediction.home_team} vs ${prediction.away_team}`}
        description={`${prediction.league.replaceAll("_", " ")} · ${formatDateTime(
          prediction.scheduled_at
        )} · ${prediction.model_version}`}
        actions={
          <div className="flex items-center gap-2">
            {isConnected ? (
              <span className="rounded-md border border-pos/30 bg-pos/[0.08] px-2.5 py-1 text-[11px] text-pos">
                Live
              </span>
            ) : null}
            {prediction.calibrated ? (
              <span className="rounded-md border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] text-ink-soft">
                Calibrated
              </span>
            ) : null}
          </div>
        }
      />

      <div className="mb-4">
        <DataSourceBadge
          label="Mixed"
          detail="prediction and websocket are live; sentiment and biometric feeds are unavailable"
          tone="mixed"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader title="Forecast" context="home / draw / away" />
            <div className="grid grid-cols-3 divide-x divide-white/[0.07]">
              {outcomes.map((outcome) => {
                const leading = outcome.prob === maxProb;
                return (
                  <div
                    key={outcome.label}
                    className={leading ? "bg-raised px-5 py-5" : "px-5 py-5"}
                  >
                    <p className="truncate text-[11px] text-ink-mute">{outcome.label}</p>
                    <p className="tnum mt-2 font-mono text-[28px] leading-none text-ink">
                      {(outcome.prob * 100).toFixed(1)}%
                    </p>
                  </div>
                );
              })}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.07] px-5 py-4">
              <p className="tnum font-mono text-[13px] text-ink-soft">
                Predicted score {prediction.predicted_score.home.toFixed(1)} -{" "}
                {prediction.predicted_score.away.toFixed(1)}
              </p>
              <p className="tnum font-mono text-[11px] text-ink-mute">
                Brier {prediction.brier_score?.toFixed(3) ?? "—"}
              </p>
            </div>
          </Card>

          {markets ? (
            <MarketsPanel markets={markets} />
          ) : marketsError ? (
            <Card className="px-5 py-6">
              <h2 className="text-[15px] font-medium text-ink">Goal markets</h2>
              <p className="mt-2 text-[13px] leading-relaxed text-ink-soft">
                The goal model could not produce expectations for this fixture, so the
                totals, BTTS and correct-score markets are unavailable here.
              </p>
            </Card>
          ) : null}

          <SHAPWaterfall explanation={prediction.shap_explanation} />
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Value on this fixture" />
            <div className="px-5 py-4">
              {prediction.value_bets && prediction.value_bets.length > 0 ? (
                <ul className="space-y-3">
                  {prediction.value_bets.map((bet, index) => (
                    <li
                      key={index}
                      className="rounded-lg border-l-2 border-accent bg-accent/[0.06] px-3 py-2"
                    >
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-[13px] font-medium text-ink">
                          {bet.selection.replace("_", " ")}
                        </span>
                        <span className="tnum font-mono text-[13px] text-accent">
                          +{(bet.edge * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p className="tnum mt-1 font-mono text-[11px] text-ink-soft">
                        {bet.best_odds.toFixed(2)} at {bet.sportsbook}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[13px] leading-relaxed text-ink-soft">
                  No price on this fixture clears the edge threshold. Compare it on the
                  board if the fixture is inside the current slate.
                </p>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Feeds" />
            <div className="space-y-3 px-5 py-4">
              <p className="text-[13px] leading-relaxed text-ink-soft">
                Team sentiment is unavailable for this fixture.
              </p>
              <p className="text-[13px] leading-relaxed text-ink-soft">
                Biometric and injury feeds are not part of the free-data setup.
              </p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
