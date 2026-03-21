from __future__ import annotations

from typing import Any

from sports_common.logging import get_logger

from .base_adapter import BaseAdapter

logger = get_logger(__name__)


class FootballDataOrgAdapter(BaseAdapter):
    """Adapter for football-data.org free/paid API tiers."""

    provider_name = "football_data_org"

    def __init__(self, api_key: str) -> None:
        super().__init__(
            base_url="https://api.football-data.org/v4/",
            api_key=api_key,
            timeout=20.0,
        )

    def _get_headers(self) -> dict[str, str]:
        headers = super()._get_headers()
        if self._api_key:
            headers["X-Auth-Token"] = self._api_key
        return headers

    async def health_check(self) -> bool:
        try:
            response = await self.client.get("competitions")
            return response.status_code == 200
        except Exception as e:
            logger.warning("football_data_org_health_check_failed", error=str(e))
            return False

    async def fetch_live_events(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Stream live/in-play matches for a competition code.

        league should be a football-data competition code like EPL, PD, SA, BL1.
        """
        league = str(kwargs.get("league", ""))
        if not league:
            logger.warning("football_data_org_fetch_live_events_missing_league")
            return []

        endpoint = f"competitions/{league}/matches?status=LIVE"
        try:
            response = await self.fetch_with_retry("GET", endpoint)
            response.raise_for_status()
            payload = response.json()
            matches = payload.get("matches", [])
            return [evt for raw in matches if (evt := self._map_to_event(raw))]
        except Exception as e:
            logger.error(
                "football_data_org_fetch_live_events_failed",
                league=league,
                error=str(e),
            )
            return []

    async def fetch_historical_matches(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Return season matches for a competition code."""
        league = str(kwargs.get("league", ""))
        season = str(kwargs.get("season", ""))
        if not league or not season:
            logger.warning(
                "football_data_org_fetch_historical_missing_params",
                has_league=bool(league),
                has_season=bool(season),
            )
            return []

        endpoint = f"competitions/{league}/matches?season={season}"
        try:
            response = await self.fetch_with_retry("GET", endpoint)
            response.raise_for_status()
            payload = response.json()
            matches = payload.get("matches", [])
            return [evt for raw in matches if (evt := self._map_to_event(raw))]
        except Exception as e:
            logger.error(
                "football_data_org_fetch_historical_failed",
                league=league,
                season=season,
                error=str(e),
            )
            return []

    async def fetch_odds(self, **kwargs: Any) -> list[dict[str, Any]]:
        """football-data.org free tier does not provide broad bookmaker odds."""
        match_external_id = str(kwargs.get("match_external_id", ""))
        logger.info(
            "football_data_org_odds_not_available",
            match_external_id=match_external_id,
        )
        return []

    def _map_to_event(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        try:
            minute = None
            score = raw.get("score") or {}
            duration = score.get("duration")
            if isinstance(duration, str) and duration.endswith("MINUTES"):
                minute = 90

            return {
                "external_id": str(raw.get("id", "")),
                "provider": self.provider_name,
                "event_type": "game",
                "minute": minute,
                "detail": raw,
            }
        except Exception as e:
            logger.warning("football_data_org_map_event_failed", error=str(e))
            return None
