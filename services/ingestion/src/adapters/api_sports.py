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


class APISportsAdapter(BaseAdapter):
    """Adapter for API-SPORTS (football-api)."""

    provider_name = "api_sports"

    def __init__(self, api_key: str) -> None:
        super().__init__(
            base_url="https://v3.football.api-sports.io/",
            api_key=api_key,
            timeout=15.0,
        )

    def _get_headers(self) -> dict[str, str]:
        # API-SPORTS uses x-apisports-key instead of bearer tokens.
        headers: dict[str, str] = {}
        if self._api_key:
            headers["x-apisports-key"] = self._api_key
        return headers

    async def fetch_live_events(self, league: str) -> AsyncIterator[MatchEvent]:
        """Stream live match events for a given league."""
        endpoint = f"fixtures?live=all&league={league}"
        try:
            response = await self.fetch_with_retry("GET", endpoint)
            data = response.json()
            fixtures = data.get("response", [])
            for raw in fixtures:
                event = self._map_to_event(raw)
                if event:
                    yield event
        except Exception as e:
            logger.error("fetch_live_events_failed", provider=self.provider_name, error=str(e))

    async def fetch_historical_matches(
        self, league: str, season: str
    ) -> list[MatchEvent]:
        """Return all match events for a completed season."""
        endpoint = f"fixtures?league={league}&season={season}"
        try:
            response = await self.fetch_with_retry("GET", endpoint)
            data = response.json()
            fixtures = data.get("response", [])
            return [e for raw in fixtures if (e := self._map_to_event(raw))]
        except Exception as e:
            logger.error("fetch_historical_failed", provider=self.provider_name, error=str(e))
            return []

    async def fetch_odds(self, match_external_id: str) -> list[OddsSnapshot]:
        """Return current odds snapshots for a specific match."""
        endpoint = f"odds?fixture={match_external_id}"
        try:
            response = await self.fetch_with_retry("GET", endpoint)
            data = response.json()
            return []
        except Exception as e:
            logger.error("fetch_odds_failed", provider=self.provider_name, error=str(e))
            return []

    async def health_check(self) -> bool:
        try:
            response = await self.client.get("status")
            return response.status_code == 200
        except Exception:
            return False

    def _map_to_event(self, raw: dict) -> MatchEvent | None:
        try:
            fixture = raw.get("fixture", {})
            return MatchEvent(
                external_id=str(fixture.get("id", "")),
                provider=self.provider_name,
                event_type="game",
                detail=raw,
            )
        except Exception as e:
            logger.warning("map_event_failed", error=str(e))
            return None
