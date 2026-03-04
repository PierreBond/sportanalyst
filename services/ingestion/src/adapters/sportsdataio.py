from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

import httpx

from sports_common.schemas.events import MatchEvent
from sports_common.schemas.odds import OddsSnapshot
from sports_common.logging import get_logger

from .base_adapter import BaseAdapter

logger = get_logger(__name__)


class SportsDataIOAdapter(BaseAdapter):
    """Adapter for SportsDataIO API."""

    provider_name = "sportsdataio"

    def __init__(self, api_key: str) -> None:
        super().__init__(
            base_url="https://api.sportsdata.io/v3/",
            api_key=api_key,
            timeout=15.0,
        )
        self._headers["Ocp-Apim-Subscription-Key"] = api_key

    async def fetch_live_events(self, league: str) -> AsyncIterator[MatchEvent]:
        """Stream live match events for a given league."""
        endpoint = f"{league}/scores/json/LiveGamesBySport/{league}"
        try:
            response = await self.fetch_with_retry("GET", endpoint)
            data = response.json()
            for raw in data:
                event = self._map_to_event(raw, league)
                if event:
                    yield event
        except Exception as e:
            logger.error("fetch_live_events_failed", provider=self.provider_name, error=str(e))

    async def fetch_historical_matches(
        self, league: str, season: str
    ) -> list[MatchEvent]:
        """Return all match events for a completed season."""
        endpoint = f"{league}/scores/json/Games/{season}"
        try:
            response = await self.fetch_with_retry("GET", endpoint)
            data = response.json()
            return [e for raw in data if (e := self._map_to_event(raw, league))]
        except Exception as e:
            logger.error("fetch_historical_failed", provider=self.provider_name, error=str(e))
            return []

    async def fetch_odds(self, match_external_id: str) -> list[OddsSnapshot]:
        """Return current odds snapshots for a specific match."""
        endpoint = f"odds/json/LiveGameOddsByGame/{match_external_id}"
        try:
            response = await self.fetch_with_retry("GET", endpoint)
            data = response.json()
            return [self._map_to_odds(odd, match_external_id) for odd in data]
        except Exception as e:
            logger.error("fetch_odds_failed", provider=self.provider_name, error=str(e))
            return []

    async def health_check(self) -> bool:
        """Verify connectivity to SportsDataIO."""
        try:
            response = await self.client.get("nfl/scores/json/Teams")
            return response.status_code == 200
        except Exception as e:
            logger.warning("health_check_failed", provider=self.provider_name, error=str(e))
            return False

    def _map_to_event(self, raw: dict, league: str) -> MatchEvent | None:
        """Map provider-specific JSON to unified MatchEvent schema."""
        try:
            return MatchEvent(
                external_id=str(raw.get("GameId", "")),
                provider=self.provider_name,
                event_type="game",
                detail=raw,
            )
        except Exception as e:
            logger.warning("map_event_failed", error=str(e), raw_keys=list(raw.keys()))
            return None

    def _map_to_odds(self, raw: dict, match_external_id: str) -> OddsSnapshot:
        """Map provider-specific odds JSON to unified OddsSnapshot schema."""
        return OddsSnapshot(
            match_id=uuid.uuid4(),
            sportsbook=raw.get("Sportsbook", ""),
            market_type=raw.get("BetType", "moneyline"),
            home_odds=raw.get("HomeMoneyLine"),
            away_odds=raw.get("AwayMoneyLine"),
            draw_odds=raw.get("DrawMoneyLine"),
            captured_at=datetime.now(timezone.utc),
        )
