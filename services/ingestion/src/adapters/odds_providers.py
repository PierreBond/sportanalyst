from __future__ import annotations

from typing import AsyncIterator

import httpx

from sports_common.schemas.events import MatchEvent
from sports_common.schemas.odds import OddsSnapshot
from sports_common.logging import get_logger

from .base_adapter import BaseAdapter

logger = get_logger(__name__)


class MySportsFeedsAdapter(BaseAdapter):
    """Adapter for MySportsFeeds API."""

    provider_name = "mysportsfeeds"

    def __init__(self, username: str, password: str) -> None:
        import base64
        super().__init__(
            base_url="https://api.mysportsfeeds.com/v2.1/",
            api_key=None,
            timeout=15.0,
        )
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._headers["Authorization"] = f"Basic {credentials}"

    async def fetch_live_events(self, league: str) -> AsyncIterator[MatchEvent]:
        logger.info("fetch_live_not_supported", provider=self.provider_name)
        return
        yield

    async def fetch_historical_matches(
        self, league: str, season: str
    ) -> list[MatchEvent]:
        return []

    async def fetch_odds(self, match_external_id: str) -> list[OddsSnapshot]:
        return []

    async def health_check(self) -> bool:
        return True


class SportmonksAdapter(BaseAdapter):
    """Adapter for Sportmonks API."""

    provider_name = "sportmonks"

    def __init__(self, api_token: str) -> None:
        super().__init__(
            base_url="https://api.sportmonks.com/v3/",
            api_key=api_token,
            timeout=15.0,
        )

    async def fetch_live_events(self, league: str) -> AsyncIterator[MatchEvent]:
        return
        yield

    async def fetch_historical_matches(
        self, league: str, season: str
    ) -> list[MatchEvent]:
        return []

    async def fetch_odds(self, match_external_id: str) -> list[OddsSnapshot]:
        return []

    async def health_check(self) -> bool:
        return True


class OddsJamAdapter(BaseAdapter):
    """Adapter for OddsJam API."""

    provider_name = "oddsjam"

    def __init__(self, api_key: str) -> None:
        super().__init__(
            base_url="https://api.oddsjam.com/v2/",
            api_key=api_key,
            timeout=15.0,
        )
        self._headers["x-api-key"] = api_key

    async def fetch_live_events(self, league: str) -> AsyncIterator[MatchEvent]:
        return
        yield

    async def fetch_historical_matches(
        self, league: str, season: str
    ) -> list[MatchEvent]:
        return []

    async def fetch_odds(self, match_external_id: str) -> list[OddsSnapshot]:
        return []

    async def health_check(self) -> bool:
        return True


class OpticOddsAdapter(BaseAdapter):
    """Adapter for OpticOdds API."""

    provider_name = "opticodds"

    def __init__(self, api_key: str) -> None:
        super().__init__(
            base_url="https://api.opticodds.com/api/v3/",
            api_key=api_key,
            timeout=15.0,
        )
        self._headers["x-api-key"] = api_key

    async def fetch_live_events(self, league: str) -> AsyncIterator[MatchEvent]:
        return
        yield

    async def fetch_historical_matches(
        self, league: str, season: str
    ) -> list[MatchEvent]:
        return []

    async def fetch_odds(self, match_external_id: str) -> list[OddsSnapshot]:
        return []

    async def health_check(self) -> bool:
        return True
