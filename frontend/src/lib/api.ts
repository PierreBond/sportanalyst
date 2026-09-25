import type {
  PredictionResponse,
  ValueBet,
  HealthResponse,
  MatchResearchSnapshot,
  UpcomingMatch,
  ModelsResponse,
} from "@/types";

const INTERNAL_API_BASE = "/api/backend";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY;

async function fetchJSON<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (API_KEY) headers["X-API-Key"] = API_KEY;
  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    let detail = "";
    try {
      const errorBody = await response.json();
      if (errorBody?.detail && typeof errorBody.detail === "string") {
        detail = ` - ${errorBody.detail}`;
      }
    } catch {
      // Ignore parsing errors and keep default HTTP status message.
    }
    throw new Error(`API Error: ${response.status} ${response.statusText}${detail}`);
  }

  return response.json();
}

export async function getPrediction(matchId: string): Promise<PredictionResponse> {
  return fetchJSON<PredictionResponse>(
    `${INTERNAL_API_BASE}/api/v1/predictions/${matchId}`
  );
}

export async function getBatchPredictions(
  matchIds: string[]
): Promise<{ predictions: PredictionResponse[]; generated_at: string }> {
  return fetchJSON<{ predictions: PredictionResponse[]; generated_at: string }>(
    `${INTERNAL_API_BASE}/api/v1/predictions/batch`,
    {
      method: "POST",
      body: JSON.stringify({ matches: matchIds.map((id) => ({ match_id: id })) }),
    }
  );
}

export async function getValueBets(
  date?: string,
  minEdge?: number
): Promise<{ date: string; value_bets: ValueBet[]; cached: boolean }> {
  const params = new URLSearchParams();
  if (date) params.append("date", date);
  if (minEdge !== undefined) params.append("min_edge", String(minEdge));

  return fetchJSON<{ date: string; value_bets: ValueBet[]; cached: boolean }>(
    `${INTERNAL_API_BASE}/api/v1/value-bets?${params.toString()}`
  );
}

export async function getReport(
  matchId: string
): Promise<MatchResearchSnapshot> {
  return fetchJSON<MatchResearchSnapshot>(
    `${INTERNAL_API_BASE}/api/v1/reports/${matchId}`
  );
}

export async function getReportPDF(matchId: string): Promise<Blob> {
  const response = await fetch(`${INTERNAL_API_BASE}/api/v1/reports/${matchId}/pdf`);
  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }
  return response.blob();
}

export async function getHealth(): Promise<HealthResponse> {
  return fetchJSON<HealthResponse>(`${INTERNAL_API_BASE}/health`);
}

export async function getUpcomingMatches(
  limit = 12,
  league?: string
): Promise<{ matches: UpcomingMatch[] }> {
  const params = new URLSearchParams();
  params.append("limit", String(limit));
  if (league) {
    params.append("league", league);
  }

  return fetchJSON<{ matches: UpcomingMatch[] }>(
    `${INTERNAL_API_BASE}/api/v1/matches/upcoming?${params.toString()}`
  );
}

export async function getUpcomingLeagues(): Promise<{
  leagues: { league: string; match_count: number }[];
}> {
  return fetchJSON<{ leagues: { league: string; match_count: number }[] }>(
    `${INTERNAL_API_BASE}/api/v1/leagues/upcoming`
  );
}

export async function getModels(): Promise<ModelsResponse> {
  return fetchJSON<ModelsResponse>(`${INTERNAL_API_BASE}/models`);
}

export function getWebSocketUrl(matchId: string): string {
  // WS bypasses the Next.js HTTP proxy (route handlers can't upgrade), so it
  // hits the backend's published port directly, using the page's own hostname
  // (NEXT_PUBLIC_API_URL is Docker-internal `backend`, unresolvable in browser).
  // Override with NEXT_PUBLIC_WS_URL for TLS-terminated deployments (wss).
  const wsBase =
    process.env.NEXT_PUBLIC_WS_URL ||
    (typeof window !== "undefined"
      ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.hostname}:8005`
      : "ws://127.0.0.1:8005");
  const apiKeyParam = API_KEY ? `?api_key=${encodeURIComponent(API_KEY)}` : "";
  return `${wsBase}/ws/live/${matchId}${apiKeyParam}`;
}
