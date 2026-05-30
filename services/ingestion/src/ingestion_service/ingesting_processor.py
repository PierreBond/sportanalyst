from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import text

from sports_common.config import get_settings
from sports_common.league_config import get_league_config
from sports_common.db import DatabaseClient

from ..adapters.api_sports import APISportsAdapter
from ..adapters.sportsdataio import SportsDataIOAdapter
from ..adapters.thesportsdb import TheSportsDBAdapter

logger = structlog.get_logger(__name__)


class IngestingLeagueProcessor:
    """Concrete league processor that integrates with adapters and DB.

    This processor:
    - Fetches data from configured providers (API-SPORTS, SportsDataIO, etc.)
    - Saves matches with idempotent upsert by external_id
    - Uses batch processing with concurrency and retry logic
    """

    def __init__(
        self,
        batch_size: int = 100,
        max_concurrent_leagues: int = 3,
        max_concurrent_requests: int = 5,
        league_timeout_seconds: int = 300,
        max_retries: int = 3,
    ) -> None:
        from .league_processor import (
            LeagueProcessor,
            DEFAULT_BATCH_SIZE,
            DEFAULT_MAX_CONCURRENT_LEAGUES,
            DEFAULT_MAX_CONCURRENT_REQUESTS,
            DEFAULT_LEAGUE_TIMEOUT_SECONDS,
        )

        self._settings = get_settings()
        self._league_config = get_league_config()
        self._batch_size = batch_size
        self._max_concurrent_leagues = max_concurrent_leagues
        self._max_concurrent_requests = max_concurrent_requests
        self._league_timeout_seconds = league_timeout_seconds
        self._max_retries = max_retries

        self._db: DatabaseClient | None = None
        self._adapters: dict[str, Any] = {}

        self._base_processor = LeagueProcessor(
            batch_size=batch_size,
            max_concurrent_leagues=max_concurrent_leagues,
            max_concurrent_requests=max_concurrent_requests,
            league_timeout_seconds=league_timeout_seconds,
            max_retries=max_retries,
        )

    async def _get_adapter(self, provider: str):
        """Get or create adapter for the specified provider."""
        if provider not in self._adapters:
            if provider == "api_sports":
                api_key = self._settings.api_sports_key
                if not api_key:
                    raise ValueError("API_SPORTS_KEY not configured")
                self._adapters[provider] = APISportsAdapter(api_key)
            elif provider == "sportsdataio":
                api_key = self._settings.sportsdataio_api_key
                if not api_key:
                    raise ValueError("SPORTSDATAIO_API_KEY not configured")
                self._adapters[provider] = SportsDataIOAdapter(api_key)
            elif provider == "thesportsdb":
                api_key = self._settings.thesportsdb_key or "free"
                self._adapters[provider] = TheSportsDBAdapter(api_key)
            else:
                raise ValueError(f"Unknown provider: {provider}")

        return self._adapters[provider]

    async def _get_db(self) -> DatabaseClient:
        """Get or initialize database client."""
        if self._db is None:
            from sports_common.db import db_client

            await db_client.init_db()
            self._db = db_client
        return self._db

    def get_leagues_to_process(self) -> list[str]:
        """Get list of leagues to process based on allowlist/blocklist config."""
        return self._base_processor.get_leagues_to_process()

    def get_provider_league_id(self, league_id: str, provider: str) -> str | None:
        """Get the provider-specific league ID for a given league."""
        return self._base_processor.get_provider_league_id(league_id, provider)

    async def process_leagues(
        self,
        league_ids: list[str] | None = None,
    ) -> dict[str, dict]:
        """Process multiple leagues with actual data fetching and saving."""
        if league_ids is None:
            league_ids = self.get_leagues_to_process()

        if not league_ids:
            logger.warning("no_leagues_to_process")
            return {}

        logger.info(
            "starting_league_ingestion",
            league_count=len(league_ids),
            provider=self._settings.odds_source,
            batch_size=self._batch_size,
        )

        self._league_semaphore = asyncio.Semaphore(self._max_concurrent_leagues)
        self._request_semaphore = asyncio.Semaphore(self._max_concurrent_requests)

        results = {}

        async def process_with_semaphore(league_id: str) -> tuple[str, dict]:
            async with self._league_semaphore:
                return league_id, await self._process_league_with_timeout(league_id)

        tasks = [process_with_semaphore(lid) for lid in league_ids]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for item in completed:
            if isinstance(item, Exception):
                logger.error("task_exception", error=str(item))
                continue
            league_id, stats = item
            results[league_id] = stats

        self._log_summary(results)
        return results

    async def _process_league_with_timeout(self, league_id: str) -> dict:
        """Process a single league with timeout guard."""
        try:
            return await asyncio.wait_for(
                self._process_single_league(league_id),
                timeout=self._league_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error(
                "league_processing_timeout",
                league=league_id,
                timeout_seconds=self._league_timeout_seconds,
            )
            return {
                "status": "timeout",
                "matches_fetched": 0,
                "matches_saved": 0,
                "errors": [f"Processing exceeded {self._league_timeout_seconds}s timeout"],
            }
        except Exception as e:
            logger.error(
                "league_processing_error",
                league=league_id,
                error=str(e),
            )
            return {
                "status": "failed",
                "matches_fetched": 0,
                "matches_saved": 0,
                "errors": [str(e)],
            }

    async def _process_single_league(self, league_id: str) -> dict:
        """Process a single league with actual data fetching."""
        provider = "api_sports"
        provider_league_id = self.get_provider_league_id(league_id, provider)

        if not provider_league_id:
            logger.warning(
                "no_provider_mapping",
                league=league_id,
                provider=provider,
            )
            return {
                "status": "skipped",
                "matches_fetched": 0,
                "matches_saved": 0,
                "errors": [f"No provider mapping for {provider}"],
            }

        logger.info(
            "processing_league",
            league=league_id,
            provider=provider,
            provider_league_id=provider_league_id,
        )

        matches_fetched = 0
        matches_saved = 0
        errors = []

        try:
            batch_data = await self._fetch_batch_from_provider(
                provider=provider,
                provider_league_id=provider_league_id,
                offset=0,
                limit=self._batch_size,
            )

            matches_fetched = len(batch_data)

            if batch_data:
                saved, skipped = await self._save_batch_idempotent(
                    league_id=league_id,
                    provider=provider,
                    matches=batch_data,
                )
                matches_saved = saved

        except Exception as e:
            errors.append(str(e))
            logger.error("league_fetch_failed", league=league_id, error=str(e))

        logger.info(
            "league_complete",
            league=league_id,
            matches_fetched=matches_fetched,
            matches_saved=matches_saved,
        )

        return {
            "status": "success" if matches_saved > 0 else "no_data",
            "matches_fetched": matches_fetched,
            "matches_saved": matches_saved,
            "errors": errors,
        }

    async def _fetch_batch_from_provider(
        self,
        provider: str,
        provider_league_id: str,
        offset: int,
        limit: int,
    ) -> list[dict]:
        """Fetch a batch of matches from the provider."""
        adapter = await self._get_adapter(provider)
        current_year = datetime.now(timezone.utc).year
        current_month = datetime.now(timezone.utc).month
        season = str(current_year if current_month >= 8 else current_year - 1)

        if provider == "api_sports":
            return await self._fetch_api_sports(adapter, provider_league_id, season, offset, limit)
        elif provider == "sportsdataio":
            return await self._fetch_sportsdataio(adapter, provider_league_id, offset, limit)
        elif provider == "thesportsdb":
            return await self._fetch_thesportsdb(adapter, provider_league_id, limit)
        else:
            return []

    async def _fetch_api_sports(
        self,
        adapter: APISportsAdapter,
        league_id: str,
        season: str,
        offset: int,
        limit: int,
    ) -> list[dict]:
        """Fetch from API-SPORTS across multiple seasons."""
        all_fixtures = []
        seasons_to_try = ["2024", "2023", "2022"]
        for s in seasons_to_try:
            try:
                fixtures = await self._try_season(adapter, league_id, s, offset, limit)
                if fixtures:
                    logger.info("season_data_fetched", league=league_id, season=s, count=len(fixtures))
                    all_fixtures.extend(fixtures)
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.warning("season_fetch_skipped", league=league_id, season=s, error=str(e))
        return all_fixtures

    async def _try_season(
        self, adapter: APISportsAdapter, league_id: str, season: str, offset: int, limit: int
    ) -> list[dict]:
        """Try fetching fixtures for a specific season."""
        endpoint = f"fixtures?league={league_id}&season={season}"
        response = await adapter.fetch_with_retry("GET", endpoint)
        data = response.json()
        fixtures = data.get("response", [])
        return self._parse_fixtures(fixtures)

    def _parse_fixtures(self, fixtures: list[dict]) -> list[dict]:
        """Parse raw API-SPORTS fixtures into standard format."""
        return [
            {
                "external_id": f"api_sports_{f.get('fixture', {}).get('id', '')}",
                "season": str(f.get("league", {}).get("season", "")),
                "league": f.get("league", {}).get("name", ""),
                "home_team": f.get("teams", {}).get("home", {}).get("name", ""),
                "away_team": f.get("teams", {}).get("away", {}).get("name", ""),
                "home_team_external_id": f"api_sports_{f.get('teams', {}).get('home', {}).get('id', '')}",
                "away_team_external_id": f"api_sports_{f.get('teams', {}).get('away', {}).get('id', '')}",
                "home_score": f.get("score", {}).get("fulltime", {}).get("home"),
                "away_score": f.get("score", {}).get("fulltime", {}).get("away"),
                "home_halftime_score": f.get("score", {}).get("halftime", {}).get("home"),
                "away_halftime_score": f.get("score", {}).get("halftime", {}).get("away"),
                "scheduled_at": f.get("fixture", {}).get("date", ""),
                "status": f.get("fixture", {}).get("status", {}).get("short", ""),
                "venue": f.get("fixture", {}).get("venue", {}).get("name", ""),
            }
            for f in fixtures
        ]

    async def _fetch_sportsdataio(
        self,
        adapter: SportsDataIOAdapter,
        league_id: str,
        offset: int,
        limit: int,
    ) -> list[dict]:
        """Fetch from SportsDataIO."""
        try:
            endpoint = f"scores/json/ScoresByDate/{league_id}/{offset}"
            response = await adapter.fetch_with_retry("GET", endpoint)
            data = response.json()
            games = data.get("Games", [])
            return [
                {
                    "external_id": f"sportsdataio_{g.get('GameID', '')}",
                    "league": g.get("Season", ""),
                    "home_team": g.get("HomeTeam", ""),
                    "away_team": g.get("AwayTeam", ""),
                    "home_score": g.get("HomeScore"),
                    "away_score": g.get("AwayScore"),
                    "scheduled_at": g.get("DateTime", ""),
                    "status": g.get("Status", ""),
                }
                for g in games
            ]
        except Exception as e:
            logger.error("sportsdataio_fetch_failed", error=str(e))
            return []

    async def _fetch_thesportsdb(
        self,
        adapter: TheSportsDBAdapter,
        league_id: str,
        limit: int,
    ) -> list[dict]:
        """Fetch from TheSportsDB."""
        try:
            endpoint = f"eventslastleague.php?id={league_id}"
            response = await adapter.fetch_with_retry("GET", endpoint)
            data = response.json()
            events = data.get("events", [])
            return [
                {
                    "external_id": f"thesportsdb_{e.get('idEvent', '')}",
                    "league": e.get("strLeague", ""),
                    "home_team": e.get("strHomeTeam", ""),
                    "away_team": e.get("strAwayTeam", ""),
                    "home_score": e.get("intHomeScore"),
                    "away_score": e.get("intAwayScore"),
                    "scheduled_at": e.get("dateEvent", ""),
                    "status": e.get("strStatus", ""),
                }
                for e in events[:limit]
            ]
        except Exception as e:
            logger.error("thesportsdb_fetch_failed", error=str(e))
            return []

    async def _upsert_teams(
        self,
        provider: str,
        matches: list[dict],
    ) -> None:
        """Extract unique teams from matches and upsert into teams table."""
        teams = {}
        for m in matches:
            home_ext = m.get("home_team_external_id")
            away_ext = m.get("away_team_external_id")
            home_name = m.get("home_team", "")
            away_name = m.get("away_team", "")
            league = m.get("league", "")
            if home_ext and home_name:
                teams[home_ext] = (home_name, league)
            if away_ext and away_name:
                teams[away_ext] = (away_name, league)

        if not teams:
            return

        db = await self._get_db()
        async with db.session() as session:
            for ext_id, (name, league_name) in teams.items():
                await session.execute(
                    text("""
                        INSERT INTO teams (team_id, external_id, provider, name, league)
                        VALUES (gen_random_uuid(), :external_id, :provider, :name, :league)
                        ON CONFLICT (external_id, provider) DO UPDATE SET
                            name = EXCLUDED.name,
                            league = EXCLUDED.league
                    """),
                    {
                        "external_id": ext_id,
                        "provider": provider,
                        "name": name,
                        "league": league_name,
                    },
                )

    async def _save_batch_idempotent(
        self,
        league_id: str,
        provider: str,
        matches: list[dict],
    ) -> tuple[int, int]:
        """Save matches with idempotent upsert by external_id."""
        if not matches:
            return 0, 0

        db = await self._get_db()
        saved = 0
        skipped = 0

        await self._upsert_teams(provider, matches)

        async with db.session() as session:
            for match in matches:
                external_id = match.get("external_id")
                if not external_id:
                    skipped += 1
                    continue

                home_ext = match.get("home_team_external_id", "")
                away_ext = match.get("away_team_external_id", "")
                home_team_id = None
                away_team_id = None

                try:
                    if home_ext:
                        row = await session.execute(
                            text("SELECT team_id FROM teams WHERE external_id = :ext AND provider = :prv"),
                            {"ext": home_ext, "prv": provider},
                        )
                        r = row.scalar()
                        if r:
                            home_team_id = r
                    if away_ext:
                        row = await session.execute(
                            text("SELECT team_id FROM teams WHERE external_id = :ext AND provider = :prv"),
                            {"ext": away_ext, "prv": provider},
                        )
                        r = row.scalar()
                        if r:
                            away_team_id = r

                    await session.execute(
                        text("""
                            INSERT INTO matches (
                                match_id, external_id, provider, league, season, round,
                                home_team_id, away_team_id, scheduled_at, venue, status,
                                home_score, away_score, home_halftime_score, away_halftime_score
                            )
                            VALUES (
                                gen_random_uuid(), :external_id, :provider, :league, :season,
                                :round, :home_team_id, :away_team_id, :scheduled_at, :venue,
                                :status, :home_score, :away_score,
                                :home_halftime_score, :away_halftime_score
                            )
                            ON CONFLICT (external_id, provider) DO UPDATE SET
                                status = EXCLUDED.status,
                                home_score = COALESCE(EXCLUDED.home_score, matches.home_score),
                                away_score = COALESCE(EXCLUDED.away_score, matches.away_score),
                                home_halftime_score = COALESCE(EXCLUDED.home_halftime_score, matches.home_halftime_score),
                                away_halftime_score = COALESCE(EXCLUDED.away_halftime_score, matches.away_halftime_score),
                                updated_at = NOW()
                            WHERE matches.status IN ('scheduled', 'postponed')
                        """),
                        {
                            "external_id": external_id,
                            "provider": provider,
                            "league": league_id,
                            "season": match.get("season", ""),
                            "round": match.get("round", ""),
                            "home_team_id": home_team_id,
                            "away_team_id": away_team_id,
                            "scheduled_at": datetime.fromisoformat(match["scheduled_at"]) if match.get("scheduled_at") else None,
                            "venue": match.get("venue", ""),
                            "status": match.get("status", "scheduled"),
                            "home_score": match.get("home_score"),
                            "away_score": match.get("away_score"),
                            "home_halftime_score": match.get("home_halftime_score"),
                            "away_halftime_score": match.get("away_halftime_score"),
                        },
                    )
                    saved += 1
                except Exception as e:
                    logger.warning(
                        "match_upsert_failed",
                        external_id=external_id,
                        error=str(e),
                    )
                    skipped += 1

        return saved, skipped

    def _log_summary(self, results: dict[str, dict]) -> None:
        """Log summary of all league processing results."""
        total = len(results)
        success = sum(1 for r in results.values() if r.get("status") == "success")
        failed = sum(1 for r in results.values() if r.get("status") in ["failed", "timeout"])

        total_matches = sum(r.get("matches_fetched", 0) for r in results.values())
        saved_matches = sum(r.get("matches_saved", 0) for r in results.values())

        logger.info(
            "ingestion_summary",
            total=total,
            success=success,
            failed=failed,
            total_matches=total_matches,
            saved_matches=saved_matches,
        )


def get_ingesting_processor(
    batch_size: int = 100,
    max_concurrent_leagues: int = 3,
    max_concurrent_requests: int = 5,
    league_timeout_seconds: int = 300,
    max_retries: int = 3,
) -> IngestingLeagueProcessor:
    """Get a configured IngestingLeagueProcessor instance."""
    return IngestingLeagueProcessor(
        batch_size=batch_size,
        max_concurrent_leagues=max_concurrent_leagues,
        max_concurrent_requests=max_concurrent_requests,
        league_timeout_seconds=league_timeout_seconds,
        max_retries=max_retries,
    )
