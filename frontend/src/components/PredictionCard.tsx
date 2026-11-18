"use client";

import Link from "next/link";
import type { PredictionResponse } from "@/types";
import { cn, formatDateTime } from "@/lib/utils";

interface PredictionCardProps {
  prediction: PredictionResponse;
}

export function PredictionCard({ prediction }: PredictionCardProps) {
  const { probabilities } = prediction;

  const outcomes = [
    { label: "Home", prob: probabilities.home_win },
    { label: "Draw", prob: probabilities.draw },
    { label: "Away", prob: probabilities.away_win },
  ];
  const maxProb = Math.max(
    probabilities.home_win,
    probabilities.draw,
    probabilities.away_win
  );

  return (
    <Link
      href={`/matches/${prediction.match_id}`}
      className="group block rounded-xl border border-white/[0.07] bg-surface transition-colors duration-200 ease-out hover:border-white/[0.16] hover:bg-raised/40"
    >
      <div className="flex items-start justify-between gap-4 px-5 pt-4">
        <div className="min-w-0">
          <p className="font-mono text-[11px] uppercase tracking-wide text-ink-mute">
            {prediction.league.replaceAll("_", " ")}
          </p>
          <p className="mt-1.5 text-[15px] font-medium text-ink">
            <span>{prediction.home_team}</span>
            <span className="px-1.5 text-ink-mute">vs</span>
            <span>{prediction.away_team}</span>
          </p>
        </div>
        <span className="tnum shrink-0 font-mono text-[11px] text-ink-mute">
          {formatDateTime(prediction.scheduled_at)}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-1.5 px-5">
        {outcomes.map((outcome) => {
          const leading = outcome.prob === maxProb;
          return (
            <div
              key={outcome.label}
              className={cn(
                "rounded-lg px-2 py-2.5",
                leading ? "bg-raised" : "bg-white/[0.02]"
              )}
            >
              <span
                className={cn(
                  "block text-[11px]",
                  leading ? "text-ink-soft" : "text-ink-mute"
                )}
              >
                {outcome.label}
              </span>
              <span
                className={cn(
                  "tnum mt-1 block font-mono text-[17px] leading-none",
                  leading ? "text-ink" : "text-ink-soft"
                )}
              >
                {(outcome.prob * 100).toFixed(0)}%
              </span>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-white/[0.07] px-5 py-3">
        <span className="tnum font-mono text-[11px] text-ink-soft">
          Predicted: {prediction.predicted_score.home} -{" "}
          {prediction.predicted_score.away}
        </span>
        {prediction.calibrated ? (
          <span className="text-[11px] text-pos">Calibrated</span>
        ) : (
          <span className="text-[11px] text-ink-mute">Raw score</span>
        )}
      </div>
    </Link>
  );
}
