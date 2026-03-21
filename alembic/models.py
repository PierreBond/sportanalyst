from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"

    team_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    external_id: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(10))
    league: Mapped[str] = mapped_column(String(60), nullable=False)
    country: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (Index("idx_teams_external_provider", "external_id", "provider", unique=True),)


class Player(Base):
    __tablename__ = "players"

    player_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    external_id: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    team_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("teams.team_id"))
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    position: Mapped[str | None] = mapped_column(String(30))
    date_of_birth: Mapped[datetime | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("idx_players_external_provider", "external_id", "provider", unique=True),
    )


class Match(Base):
    __tablename__ = "matches"

    match_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    external_id: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    league: Mapped[str] = mapped_column(String(60), nullable=False)
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    round: Mapped[str | None] = mapped_column(String(30))
    home_team_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("teams.team_id"))
    away_team_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("teams.team_id"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    venue: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    home_score: Mapped[int | None] = mapped_column(SmallInteger)
    away_score: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_matches_scheduled", "scheduled_at"),
        Index("idx_matches_league_season", "league", "season"),
        Index("idx_matches_external_provider", "external_id", "provider", unique=True),
    )


class MatchEvent(Base):
    __tablename__ = "match_events"

    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    match_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("matches.match_id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    minute: Mapped[int | None] = mapped_column(SmallInteger)
    second: Mapped[int | None] = mapped_column(SmallInteger)
    team_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("teams.team_id"))
    player_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("players.player_id"))
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (Index("idx_events_match", "match_id"),)


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    snapshot_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    match_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("matches.match_id"), nullable=False)
    sportsbook: Mapped[str] = mapped_column(String(60), nullable=False)
    market_type: Mapped[str] = mapped_column(String(30), nullable=False)
    home_odds: Mapped[float | None] = mapped_column(Numeric(8, 4))
    away_odds: Mapped[float | None] = mapped_column(Numeric(8, 4))
    draw_odds: Mapped[float | None] = mapped_column(Numeric(8, 4))
    spread_value: Mapped[float | None] = mapped_column(Numeric(6, 2))
    total_value: Mapped[float | None] = mapped_column(Numeric(6, 2))
    cash_pct_home: Mapped[float | None] = mapped_column(Numeric(5, 2))
    ticket_pct_home: Mapped[float | None] = mapped_column(Numeric(5, 2))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "idx_odds_unique",
            "match_id",
            "sportsbook",
            "market_type",
            "captured_at",
            unique=True,
        ),
        Index("idx_odds_match_time", "match_id", "captured_at"),
    )


class PlayerBiometric(Base):
    __tablename__ = "player_biometrics"

    biometric_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    player_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("players.player_id"), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20))

    __table_args__ = (
        Index(
            "idx_bio_unique",
            "player_id",
            "source",
            "metric_type",
            "recorded_at",
            unique=True,
        ),
        Index("idx_bio_player_time", "player_id", "recorded_at"),
    )


class SentimentScore(Base):
    __tablename__ = "sentiment_scores"

    sentiment_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    entity_type: Mapped[str] = mapped_column(String(10), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    volume: Mapped[int] = mapped_column(Integer, default=0)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("idx_sent_entity_time", "entity_type", "entity_id", "captured_at"),)


class FeatureStore(Base):
    __tablename__ = "feature_store"

    feature_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    match_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("matches.match_id"), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    features: Mapped[dict] = mapped_column(JSON, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (Index("idx_features_match", "match_id"),)


class Prediction(Base):
    __tablename__ = "predictions"

    prediction_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    match_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("matches.match_id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(60), nullable=False)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    home_win_prob: Mapped[float | None] = mapped_column(Numeric(5, 4))
    draw_prob: Mapped[float | None] = mapped_column(Numeric(5, 4))
    away_win_prob: Mapped[float | None] = mapped_column(Numeric(5, 4))
    predicted_home_score: Mapped[float | None] = mapped_column(Numeric(4, 2))
    predicted_away_score: Mapped[float | None] = mapped_column(Numeric(4, 2))
    shap_values: Mapped[dict | None] = mapped_column(JSON)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (Index("idx_pred_match", "match_id"),)
