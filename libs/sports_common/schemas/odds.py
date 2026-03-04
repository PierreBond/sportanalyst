from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class OddsSnapshot(BaseModel):
    model_config = {"extra": "ignore"}

    snapshot_id: UUID | None = None
    match_id: UUID
    sportsbook: str
    market_type: str
    home_odds: Decimal | None = None
    away_odds: Decimal | None = None
    draw_odds: Decimal | None = None
    spread_value: Decimal | None = None
    total_value: Decimal | None = None
    cash_pct_home: Decimal | None = None
    ticket_pct_home: Decimal | None = None
    captured_at: datetime = Field(default_factory=datetime.utcnow)


class LineMovement(BaseModel):
    model_config = {"extra": "ignore"}

    movement_id: UUID | None = None
    match_id: UUID
    sportsbook: str
    market_type: str
    opening_value: Decimal
    closing_value: Decimal | None = None
    opening_captured_at: datetime
    closing_captured_at: datetime | None = None


class ImpliedProbability(BaseModel):
    model_config = {"extra": "ignore"}

    match_id: UUID
    sportsbook: str
    market_type: str
    home_implied_prob: float
    away_implied_prob: float
    draw_implied_prob: float | None = None
    vigorish: float | None = None
    captured_at: datetime = Field(default_factory=datetime.utcnow)


class MarketFeature(BaseModel):
    model_config = {"extra": "ignore"}

    match_id: UUID
    opening_implied_prob_home: float | None = None
    closing_implied_prob_home: float | None = None
    line_movement_spread: float | None = None
    cash_ticket_divergence: float | None = None
    reverse_line_movement: bool | None = None
    computed_at: datetime = Field(default_factory=datetime.utcnow)
