from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProbabilityDistribution(BaseModel):
    home_win: float
    draw: float
    away_win: float


class ScoreDistribution(BaseModel):
    home_score: int
    away_score: int
    probability: float


class MatchPrediction(BaseModel):
    model_config = {"extra": "ignore"}

    prediction_id: UUID | None = None
    match_id: str
    model_name: str
    model_version: str
    predicted_at: datetime = Field(default_factory=datetime.utcnow)
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    predicted_home_score: float | None = None
    predicted_away_score: float | None = None
    score_distribution: list[ScoreDistribution] | None = None
    shap_values: dict[str, float] | None = None
    is_live: bool = False


class BettingRecommendation(BaseModel):
    model_config = {"extra": "ignore"}

    match_id: str
    model_name: str
    market_type: str
    selection: str
    model_probability: float
    implied_probability: float
    odds: float
    expected_value: float
    kelly_fraction: float | None = None
    recommended_stake: float | None = None
    confidence: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ValueBet(BaseModel):
    model_config = {"extra": "ignore"}

    bet_id: UUID | None = None
    match_id: str
    model_name: str
    sportsbook: str
    market_type: str
    selection: str
    model_probability: float
    odds: float
    expected_value: float
    stake: float | None = None
    potential_payout: float | None = None
    placed: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
