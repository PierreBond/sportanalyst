from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FeatureMetadata(BaseModel):
    name: str
    description: str
    feature_type: str
    data_type: str
    training_eligible: bool = True


class FeatureVector(BaseModel):
    model_config = {"extra": "ignore"}

    feature_id: UUID | None = None
    match_id: UUID
    team_id: UUID | None = None
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    features: dict[str, float]
    version: str = "v1.0"


class TeamFeatureVector(BaseModel):
    model_config = {"extra": "ignore"}

    match_id: UUID
    team_id: UUID
    home_or_away: str
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    features: dict[str, float]
    version: str = "v1.0"


class MatchFeatureVector(BaseModel):
    model_config = {"extra": "ignore"}

    match_id: UUID
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    home_features: dict[str, float]
    away_features: dict[str, float]
    market_features: dict[str, float] | None = None
    biometric_features: dict[str, float] | None = None
    sentiment_features: dict[str, float] | None = None
    version: str = "v1.0"
