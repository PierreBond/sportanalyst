from __future__ import annotations

from typing import Any

from sports_common.logging import get_logger

from .base_adapter import BaseAdapter

logger = get_logger(__name__)


class TheSportsDBAdapter(BaseAdapter):
    """Adapter for TheSportsDB API.

    TheSportsDB supports a free key value of "1" for public endpoints.
    """

    provider_name = "thesportsdb"

    def __init__(self, api_key: str = "1") -> None:
        key = (api_key or "1").strip()
        if key.lower() == "free":
            key = "1"
        super().__init__(
            base_url=f"https://www.thesportsdb.com/api/v1/json/{key}/",
            api_key=None,
            timeout=20.0,
        )

    async def health_check(self) -> bool:
        try:
            response = await self.client.get("all_sports.php")
            return response.status_code == 200
        except Exception as e:
            logger.warning("thesportsdb_health_check_failed", error=str(e))
            return False

    async def fetch_live_events(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Stream live events for a league id (idLeague)."""
        league = str(kwargs.get("league", ""))
        if not league:
            logger.warning("thesportsdb_fetch_live_events_missing_league")
            return []

        endpoint = f"livescore.php?l={league}"
        try:
            response = await self.fetch_with_retry("GET", endpoint)
            response.raise_for_status()
            payload = response.json()
            events = payload.get("events") or []
            return [evt for raw in events if (evt := self._map_to_event(raw))]
        except Exception as e:
            logger.error("thesportsdb_fetch_live_events_failed", league=league, error=str(e))
            return []

    async def fetch_historical_matches(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Return season events for a league id and season (e.g. 2025-2026)."""
        league = str(kwargs.get("league", ""))
        season = str(kwargs.get("season", ""))
        if not league or not season:
            logger.warning(
                "thesportsdb_fetch_historical_missing_params",
                has_league=bool(league),
                has_season=bool(season),
            )
            return []

        endpoint = f"eventsseason.php?id={league}&s={season}"
        try:
            response = await self.fetch_with_retry("GET", endpoint)
            response.raise_for_status()
            payload = response.json()
            events = payload.get("events") or []
            return [evt for raw in events if (evt := self._map_to_event(raw))]
        except Exception as e:
            logger.error(
                "thesportsdb_fetch_historical_failed",
                league=league,
                season=season,
                error=str(e),
            )
            return []

    async def fetch_odds(self, **kwargs: Any) -> list[dict[str, Any]]:
        """TheSportsDB does not expose a stable unified bookmaker-odds endpoint."""
        match_external_id = str(kwargs.get("match_external_id", ""))
        logger.info("thesportsdb_odds_not_available", match_external_id=match_external_id)
        return []

    def _map_to_event(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        try:
            minute = None
            if raw.get("intLiveScore") in ("1", 1, True):
                minute = 45

            return {
                "external_id": str(raw.get("idEvent", "")),
                "provider": self.provider_name,
                "event_type": "game",
                "minute": minute,
                "detail": raw,
            }
        except Exception as e:
            logger.warning("thesportsdb_map_event_failed", error=str(e))
            return None
