from __future__ import annotations

from pydantic import ValidationError

from sports_common.schemas.events import MatchEvent
from sports_common.logging import get_logger

logger = get_logger(__name__)


def validate_event(raw: dict) -> MatchEvent | None:
    """Validate and return a MatchEvent, or None if invalid."""
    try:
        return MatchEvent.model_validate(raw)
    except ValidationError as e:
        logger.warning(
            "invalid_event",
            errors=e.error_count(),
            raw_keys=list(raw.keys()),
        )
        return None


def validate_events_batch(raw_events: list[dict]) -> list[MatchEvent]:
    """Validate a batch of raw events."""
    validated = []
    for raw in raw_events:
        event = validate_event(raw)
        if event:
            validated.append(event)
    return validated


def validate_odds_snapshot(raw: dict) -> bool:
    """Validate that a raw odds snapshot has required fields."""
    required = ["match_id", "sportsbook", "market_type", "captured_at"]
    return all(field in raw for field in required)


def validate_player_biometric(raw: dict) -> bool:
    """Validate that a raw biometric has required fields."""
    required = ["player_id", "source", "metric_type", "value", "recorded_at"]
    return all(field in raw for field in required)


def validate_sentiment_result(raw: dict) -> bool:
    """Validate that a raw sentiment has required fields."""
    required = ["entity_id", "entity_type", "source", "score", "captured_at"]
    return all(field in raw for field in required)
