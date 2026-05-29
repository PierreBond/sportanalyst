export interface PredictionResponse {
  match_id: string;
  home_team: string;
  away_team: string;
  league: string;
  scheduled_at: string;
  model: string;
  model_version: string;
  probabilities: {
    home_win: number;
    draw: number;
    away_win: number;
  };
  predicted_score: {
    home: number;
    away: number;
  };
  calibrated: boolean;
  brier_score_trailing_100: number;
  value_bets: ValueBet[];
  shap_explanation: SHAPExplanation;
  generated_at: string;
}

export interface ValueBet {
  match_id: string;
  selection: string;
  model_prob: number;
  best_odds: number;
  implied_prob: number;
  edge: number;
  kelly_stake_pct: number;
  sportsbook: string;
}

export interface SHAPExplanation {
  positive_drivers: SHAPDriver[];
  negative_drivers: SHAPDriver[];
}

export interface SHAPDriver {
  feature: string;
  impact: number;
  impact_pct: number;
  label: string;
}

export interface BiometricData {
  player_id: string;
  player_name: string;
  acwr: number;
  hrv: number;
  resting_hr: number;
  sleep_score: number;
  injury_risk: number;
}

export interface SentimentData {
  entity_type: "team" | "player";
  entity_id: string;
  score: number;
  volume: number;
  source: string;
  captured_at: string;
}

export interface LineMovement {
  timestamp: string;
  spread: number;
  total: number;
  home_odds: number;
  away_odds: number;
}

export interface WebSocketMessage {
  type: "prediction_update" | "error";
  match_id?: string;
  timestamp: string;
  probabilities?: {
    home_win: number;
    draw: number;
    away_win: number;
  };
  error?: string;
}

export interface HealthResponse {
  status: "healthy" | "unhealthy";
  service: string;
  version?: string;
}

export interface ModelInfo {
  name: string;
  version: string;
  created_at: string;
  status: "staging" | "production";
}

export interface MatchResearchSnapshot {
  match_id: string;
  home_team: string;
  away_team: string;
  league: string;
  scheduled_at: string;
  generated_at: string;
  home_win_prob: number;
  draw_prob: number;
  away_win_prob: number;
  predicted_home_score: number;
  predicted_away_score: number;
  value_bets: ValueBet[];
  shap_explanation: SHAPExplanation;
}

export interface UpcomingMatch {
  match_id: string;
  home_team: string;
  away_team: string;
  league: string;
  scheduled_at: string;
  status: string;
}
