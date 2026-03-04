from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MatchEvent(BaseModel):
    model_config = {"extra": "ignore"}

    event_id: UUID | None = None
    external_id: str
    provider: str
    match_id: UUID | None = None
    event_type: str
    minute: int | None = None
    second: int | None = None
    team_id: UUID | None = None
    player_id: UUID | None = None
    detail: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GoalEvent(MatchEvent):
    event_type: str = "goal"
    goal_type: str | None = None
    penalty: bool = False
    own_goal: bool = False
    assist_player_id: UUID | None = None


class SubstitutionEvent(MatchEvent):
    event_type: str = "substitution"
    player_in_id: UUID | None = None
    player_out_id: UUID | None = None
    reason: str | None = None


class CardEvent(MatchEvent):
    event_type: str = "card"
    card_type: str
    reason: str | None = None


class ShotEvent(MatchEvent):
    event_type: str = "shot"
    on_target: bool = False
    blocked: bool = False
    missed: bool = False
    xg: float | None = None
