from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SentimentResult(BaseModel):
    model_config = {"extra": "ignore"}

    sentiment_id: UUID | None = None
    entity_type: str
    entity_id: UUID
    source: str
    score: float
    volume: int = 0
    captured_at: datetime = Field(default_factory=datetime.utcnow)


class NewsAlert(BaseModel):
    model_config = {"extra": "ignore"}

    alert_id: UUID | None = None
    entity_type: str
    entity_id: UUID
    headline: str
    alert_type: str
    severity: str
    source: str
    published_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class RawTextPayload(BaseModel):
    model_config = {"extra": "ignore"}

    text: str
    entity_id: UUID
    entity_type: str
    source: str
    post_id: str | None = None
    author: str | None = None
    captured_at: datetime = Field(default_factory=datetime.utcnow)


class AggregatedSentiment(BaseModel):
    model_config = {"extra": "ignore"}

    entity_id: UUID
    entity_type: str
    twitter_sentiment: float | None = None
    reddit_sentiment: float | None = None
    news_sentiment: float | None = None
    total_volume: int = 0
    computed_at: datetime = Field(default_factory=datetime.utcnow)
