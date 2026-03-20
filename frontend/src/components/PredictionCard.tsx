"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { PredictionResponse } from "@/types";

interface PredictionCardProps {
  prediction: PredictionResponse;
}

export function PredictionCard({ prediction }: PredictionCardProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="bg-white rounded-lg shadow p-6 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>
        <div className="h-8 bg-gray-200 rounded w-full mb-2"></div>
        <div className="h-8 bg-gray-200 rounded w-3/4"></div>
      </div>
    );
  }

  const { probabilities } = prediction;
  const maxProb = Math.max(
    probabilities.home_win,
    probabilities.draw,
    probabilities.away_win
  );

  const getOutcomeClass = (prob: number) => {
    if (prob === maxProb) {
      return "bg-blue-600 text-white";
    }
    return "bg-gray-100 text-gray-700";
  };

  return (
    <Link href={`/matches/${prediction.match_id}`}>
      <div className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow cursor-pointer">
        <div className="p-4 border-b border-gray-100">
          <div className="flex justify-between items-center">
            <div className="flex items-center space-x-2">
              <span className="font-semibold text-gray-900">
                {prediction.home_team}
              </span>
              <span className="text-gray-400">vs</span>
              <span className="font-semibold text-gray-900">
                {prediction.away_team}
              </span>
            </div>
            <span className="text-xs text-gray-500">
              {prediction.league}
            </span>
          </div>
        </div>

        <div className="p-4">
          <div className="grid grid-cols-3 gap-2 mb-3">
            <div
              className={`rounded-lg p-3 text-center transition-all ${getOutcomeClass(
                probabilities.home_win
              )}`}
            >
              <div className="text-xs opacity-75 mb-1">Home</div>
              <div className="text-xl font-bold">
                {(probabilities.home_win * 100).toFixed(0)}%
              </div>
            </div>
            <div
              className={`rounded-lg p-3 text-center transition-all ${getOutcomeClass(
                probabilities.draw
              )}`}
            >
              <div className="text-xs opacity-75 mb-1">Draw</div>
              <div className="text-xl font-bold">
                {(probabilities.draw * 100).toFixed(0)}%
              </div>
            </div>
            <div
              className={`rounded-lg p-3 text-center transition-all ${getOutcomeClass(
                probabilities.away_win
              )}`}
            >
              <div className="text-xs opacity-75 mb-1">Away</div>
              <div className="text-xl font-bold">
                {(probabilities.away_win * 100).toFixed(0)}%
              </div>
            </div>
          </div>

          <div className="flex justify-between items-center text-xs text-gray-500">
            <span>
              Predicted: {prediction.predicted_score.home} -{" "}
              {prediction.predicted_score.away}
            </span>
            {prediction.calibrated && (
              <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full">
                Calibrated
              </span>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}
