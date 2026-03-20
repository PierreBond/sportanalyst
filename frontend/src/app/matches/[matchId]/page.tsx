"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { SHAPWaterfall } from "@/components/SHAPWaterfall";
import { BiometricGauge } from "@/components/BiometricGauge";
import { SentimentBadge } from "@/components/SentimentBadge";
import { getPrediction, getWebSocketUrl } from "@/lib/api";
import { useWebSocket } from "@/lib/ws";
import type { PredictionResponse, LineMovement } from "@/types";

const sampleLineMovement: LineMovement[] = [
  { timestamp: "2026-03-15T10:00:00Z", spread: -2.5, total: 7.5, home_odds: 1.95, away_odds: 1.95 },
  { timestamp: "2026-03-15T11:00:00Z", spread: -3.0, total: 7.5, home_odds: 1.90, away_odds: 2.00 },
  { timestamp: "2026-03-15T12:00:00Z", spread: -3.0, total: 7.0, home_odds: 1.85, away_odds: 2.05 },
  { timestamp: "2026-03-15T13:00:00Z", spread: -2.5, total: 7.0, home_odds: 1.90, away_odds: 2.00 },
  { timestamp: "2026-03-15T14:00:00Z", spread: -2.5, total: 6.5, home_odds: 1.92, away_odds: 1.98 },
];

export default function MatchDetailPage() {
  const params = useParams();
  const matchId = params.matchId as string;

  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lineMovement] = useState<LineMovement[]>(sampleLineMovement);

  const { connect, disconnect, lastMessage, isConnected } = useWebSocket({
    onMessage: (message) => {
      if (message.type === "prediction_update" && message.probabilities) {
        setPrediction((prev) =>
          prev
            ? {
                ...prev,
                probabilities: message.probabilities!,
              }
            : null
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
      } catch (err) {
        setError("Failed to load prediction");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    loadPrediction();
  }, [matchId]);

  useEffect(() => {
    const wsUrl = getWebSocketUrl(matchId);
    connect(wsUrl);

    return () => {
      disconnect();
    };
  }, [matchId, connect, disconnect]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/2 mb-6"></div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="h-64 bg-gray-200 rounded-lg"></div>
            <div className="h-64 bg-gray-200 rounded-lg"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !prediction) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-red-800 mb-2">
            Error Loading Prediction
          </h2>
          <p className="text-red-600">{error || "Prediction not found"}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              {prediction.home_team} vs {prediction.away_team}
            </h1>
            <p className="text-gray-500 mt-1">
              {prediction.league} • {prediction.model} v{prediction.model_version}
            </p>
          </div>
          <div className="flex items-center space-x-2">
            {isConnected && (
              <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm flex items-center">
                <span className="w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"></span>
                Live
              </span>
            )}
            {prediction.calibrated && (
              <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm">
                Calibrated
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-2">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Probabilistic Forecast
            </h2>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center p-6 bg-gradient-to-b from-blue-50 to-white rounded-lg border-2 border-blue-500">
                <div className="text-sm text-gray-500 mb-2">
                  {prediction.home_team} Win
                </div>
                <div className="text-5xl font-bold text-blue-600">
                  {(prediction.probabilities.home_win * 100).toFixed(1)}%
                </div>
              </div>
              <div className="text-center p-6 bg-gradient-to-b from-gray-50 to-white rounded-lg border-2 border-gray-300">
                <div className="text-sm text-gray-500 mb-2">Draw</div>
                <div className="text-5xl font-bold text-gray-600">
                  {(prediction.probabilities.draw * 100).toFixed(1)}%
                </div>
              </div>
              <div className="text-center p-6 bg-gradient-to-b from-red-50 to-white rounded-lg border-2 border-red-500">
                <div className="text-sm text-gray-500 mb-2">
                  {prediction.away_team} Win
                </div>
                <div className="text-5xl font-bold text-red-600">
                  {(prediction.probabilities.away_win * 100).toFixed(1)}%
                </div>
              </div>
            </div>

            <div className="mt-6 pt-6 border-t border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                Predicted Score
              </h3>
              <div className="text-4xl font-bold text-center">
                {prediction.home_team}{" "}
                <span className="text-blue-600">
                  {prediction.predicted_score.home}
                </span>{" "}
                -{" "}
                <span className="text-red-600">
                  {prediction.predicted_score.away}
                </span>{" "}
                {prediction.away_team}
              </div>
              <p className="text-center text-gray-500 mt-2">
                Brier Score (trailing 100): {prediction.brier_score_trailing_100.toFixed(3)}
              </p>
            </div>
          </div>
        </div>

        <div>
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Team Status
            </h2>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="font-medium">{prediction.home_team}</span>
                <SentimentBadge score={0.3} volume={1250} size="sm" />
              </div>
              <div className="flex justify-between items-center">
                <span className="font-medium">{prediction.away_team}</span>
                <SentimentBadge score={-0.15} volume={980} size="sm" />
              </div>
            </div>

            <div className="mt-6 pt-6 border-t border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Team Biometrics
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <BiometricGauge
                  label="Home ACWR"
                  value={1.2}
                  min={0}
                  max={2}
                  unit=""
                  thresholds={{ low: 0.8, high: 1.5 }}
                />
                <BiometricGauge
                  label="Away ACWR"
                  value={0.9}
                  min={0}
                  max={2}
                  unit=""
                  thresholds={{ low: 0.8, high: 1.5 }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <SHAPWaterfall explanation={prediction.shap_explanation} />

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Strategic Recommendations
          </h2>
          {prediction.value_bets && prediction.value_bets.length > 0 ? (
            <div className="space-y-4">
              {prediction.value_bets.map((bet, index) => (
                <div
                  key={index}
                  className="p-4 bg-green-50 rounded-lg border-l-4 border-green-500"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="text-lg font-bold text-green-700">
                        {bet.selection.toUpperCase()}
                      </span>
                      <p className="text-sm text-gray-600 mt-1">
                        @ {bet.best_odds} from {bet.sportsbook}
                      </p>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold text-green-600">
                        +{(bet.edge * 100).toFixed(1)}%
                      </div>
                      <div className="text-sm text-gray-500">Edge</div>
                    </div>
                  </div>
                  <div className="mt-2 flex justify-between text-sm">
                    <span>
                      Kelly: {bet.kelly_stake_pct.toFixed(2)}% of bankroll
                    </span>
                    <span>
                      Implied: {(bet.implied_prob * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">
              No value bets detected at current threshold
            </p>
          )}
        </div>
      </div>

      {lineMovement.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Line Movement
          </h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Time
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Spread
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Total
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Home Odds
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    Away Odds
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {lineMovement.map((item, index) => (
                  <tr key={index} className={index === lineMovement.length - 1 ? "bg-blue-50" : ""}>
                    <td className="px-4 py-2 text-sm text-gray-900">
                      {new Date(item.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="px-4 py-2 text-sm font-medium text-gray-900">
                      {item.spread}
                    </td>
                    <td className="px-4 py-2 text-sm font-medium text-gray-900">
                      {item.total}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {item.home_odds.toFixed(2)}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {item.away_odds.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
