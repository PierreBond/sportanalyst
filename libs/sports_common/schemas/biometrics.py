from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class PlayerBiometric(BaseModel):
    model_config = {"extra": "ignore"}

    biometric_id: UUID | None = None
    player_id: UUID
    source: str
    recorded_at: datetime = Field(default_factory=datetime.utcnow)
    metric_type: str
    value: Decimal
    unit: str | None = None


class ACWR(BaseModel):
    model_config = {"extra": "ignore"}

    player_id: UUID
    acute_load: float
    chronic_load: float
    ratio: float
    is_danger_zone: bool = False
    computed_at: datetime = Field(default_factory=datetime.utcnow)


class WellnessScore(BaseModel):
    model_config = {"extra": "ignore"}

    player_id: UUID
    hrv: float | None = None
    resting_hr: float | None = None
    sleep_score: float | None = None
    recovery_score: float | None = None
    wellness_score: float
    computed_at: datetime = Field(default_factory=datetime.utcnow)


class InjuryRisk(BaseModel):
    model_config = {"extra": "ignore"}

    player_id: UUID
    injury_probability: float
    risk_factors: list[str] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=datetime.utcnow)


class BiometricFeature(BaseModel):
    model_config = {"extra": "ignore"}

    player_id: UUID
    match_id: UUID | None = None
    acwr: float | None = None
    hrv: float | None = None
    player_load: float | None = None
    wellness_score: float | None = None
    injury_risk: float | None = None
    computed_at: datetime = Field(default_factory=datetime.utcnow)
