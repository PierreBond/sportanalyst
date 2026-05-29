from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Any, Callable

import structlog

from sports_common.config import get_settings
from sports_common.league_config import get_league_config

logger = structlog.get_logger(__name__)

DEFAULT_BATCH_SIZE = 100
DEFAULT_MAX_CONCURRENT_LEAGUES = 3
DEFAULT_MAX_CONCURRENT_REQUESTS = 5
DEFAULT_LEAGUE_TIMEOUT_SECONDS = 300
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_BASE = 2.0


def exponential_backoff(attempt: int, base: float = DEFAULT_RETRY_BACKOFF_BASE) -> float:
    """Calculate exponential backoff delay."""
    return min(base**attempt, 60.0)


class ProcessingStats:
    """Track statistics for league processing."""

    def __init__(self) -> None:
        self.status = "pending"
        self.matches_fetched = 0
        self.matches_saved = 0
        self.matches_skipped = 0
        self.batches_processed = 0
        self.errors: list[str] = []
        self.retries = 0
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "matches_fetched": self.matches_fetched,
            "matches_saved": self.matches_saved,
            "matches_skipped": self.matches_skipped,
            "batches_processed": self.batches_processed,
            "errors": self.errors,
            "retries": self.retries,
            "duration_seconds": (
                (self.completed_at - self.started_at).total_seconds()
                if self.started_at and self.completed_at
                else None
            ),
        }


class LeagueProcessor:
    """Orchestrates league-based ingestion with filtering, batching, and error handling.

    Features:
    - Dynamic league discovery from config or DB
    - Allowlist/blocklist filtering
    - Batch processing with configurable batch size
    - Concurrency limits for leagues and API calls
    - Per-league timeout guards
    - Retry with exponential backoff
    - Idempotency via upsert by external_id
    - Comprehensive logging and statistics
    """

    def __init__(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_concurrent_leagues: int = DEFAULT_MAX_CONCURRENT_LEAGUES,
        max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
        league_timeout_seconds: int = DEFAULT_LEAGUE_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._settings = get_settings()
        self._league_config = get_league_config()
        self._batch_size = batch_size
        self._max_concurrent_leagues = max_concurrent_leagues
        self._max_concurrent_requests = max_concurrent_requests
        self._league_timeout_seconds = league_timeout_seconds
        self._max_retries = max_retries

        self._league_semaphore: asyncio.Semaphore | None = None
        self._request_semaphore: asyncio.Semaphore | None = None

    def get_leagues_to_process(self) -> list[str]:
        """Get list of leagues to process based on allowlist/blocklist config.

        Returns:
            List of league IDs that should be processed.
        """
        allowlist = self._settings.league_allowlist_set
        blocklist = self._settings.league_blocklist_set

        if allowlist:
            leagues = allowlist
            logger.info("using_league_allowlist", leagues=list(leagues))
        else:
            leagues = set(self._league_config.get_discovered_league_ids())
            if not leagues:
                logger.warning("no_configured_leagues")
                return []

        if blocklist:
            leagues = leagues - blocklist
            logger.info(
                "applied_league_blocklist",
                removed=list(blocklist),
                remaining=list(leagues),
            )

        return sorted(leagues)

    def get_provider_league_id(self, league_id: str, provider: str) -> str | None:
        """Get the provider-specific league ID for a given league."""
        mapping = self._league_config.get_provider_mapping(league_id)
        return mapping.get(provider)

    async def process_leagues(
        self,
        league_ids: list[str] | None = None,
        on_league_start: Callable[[str], None] | None = None,
        on_league_complete: Callable[[str, dict], None] | None = None,
    ) -> dict[str, dict]:
        """Process multiple leagues with batching, concurrency, and error isolation.

        Args:
            league_ids: Specific leagues to process (None = use config filtering)
            on_league_start: Callback(league_id) when league processing starts
            on_league_complete: Callback(league_id, stats) when league completes

        Returns:
            Dict of league_id -> processing statistics
        """
        if league_ids is None:
            league_ids = self.get_leagues_to_process()

        if not league_ids:
            logger.warning("no_leagues_to_process")
            return {}

        self._league_semaphore = asyncio.Semaphore(self._max_concurrent_leagues)
        self._request_semaphore = asyncio.Semaphore(self._max_concurrent_requests)

        results = {}

        async def process_with_semaphore(league_id: str) -> tuple[str, dict]:
            async with self._league_semaphore:
                return league_id, await self._process_league_with_timeout(
                    league_id, on_league_start, on_league_complete
                )

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

    async def _process_league_with_timeout(
        self,
        league_id: str,
        on_league_start: Callable[[str], None] | None,
        on_league_complete: Callable[[str, dict], None] | None,
    ) -> dict:
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
            stats = ProcessingStats()
            stats.status = "timeout"
            stats.errors.append(f"Processing exceeded {self._league_timeout_seconds}s timeout")
            return stats.to_dict()
        except Exception as e:
            logger.error(
                "league_processing_error",
                league=league_id,
                error=str(e),
            )
            stats = ProcessingStats()
            stats.status = "failed"
            stats.errors.append(str(e))
            return stats.to_dict()

    async def _process_single_league(
        self,
        league_id: str,
    ) -> dict:
        """Process a single league with batching.

        Override this method in subclasses to implement actual data fetching.
        This default implementation demonstrates the batching pattern.
        """
        stats = ProcessingStats()
        stats.started_at = datetime.utcnow()

        logger.info(
            "starting_league_processing",
            league=league_id,
            batch_size=self._batch_size,
            max_retries=self._max_retries,
        )

        try:
            provider = self._settings.odds_source or "api_sports"
            provider_league_id = self.get_provider_league_id(league_id, provider)

            if not provider_league_id:
                logger.warning(
                    "no_provider_mapping",
                    league=league_id,
                    provider=provider,
                )
                stats.status = "skipped"
                stats.errors.append(f"No provider mapping for {provider}")
                return stats.to_dict()

            offset = 0
            has_more = True

            while has_more:
                batch_stats = await self._fetch_and_save_batch(
                    league_id=league_id,
                    provider=provider,
                    provider_league_id=provider_league_id,
                    offset=offset,
                )

                stats.matches_fetched += batch_stats.get("fetched", 0)
                stats.matches_saved += batch_stats.get("saved", 0)
                stats.matches_skipped += batch_stats.get("skipped", 0)
                stats.batches_processed += 1
                stats.retries += batch_stats.get("retries", 0)

                if batch_stats.get("errors"):
                    stats.errors.extend(batch_stats["errors"])

                fetched = batch_stats.get("fetched", 0)
                has_more = fetched >= self._batch_size
                offset += fetched

                logger.debug(
                    "batch_complete",
                    league=league_id,
                    offset=offset,
                    has_more=has_more,
                )

            stats.status = "success"
            logger.info(
                "league_processing_complete",
                league=league_id,
                matches_fetched=stats.matches_fetched,
                matches_saved=stats.matches_saved,
                batches=stats.batches_processed,
            )

        except Exception as e:
            stats.status = "failed"
            stats.errors.append(str(e))
            logger.error(
                "league_processing_failed",
                league=league_id,
                error=str(e),
            )

        stats.completed_at = datetime.utcnow()
        return stats.to_dict()

    async def _fetch_and_save_batch(
        self,
        league_id: str,
        provider: str,
        provider_league_id: str,
        offset: int,
    ) -> dict[str, Any]:
        """Fetch a batch of data with retry logic and save with idempotency."""
        stats: dict[str, Any] = {
            "fetched": 0,
            "saved": 0,
            "skipped": 0,
            "retries": 0,
            "errors": [],
        }

        for attempt in range(self._max_retries):
            try:
                async with self._request_semaphore:
                    data = await self._fetch_batch_from_provider(
                        provider=provider,
                        provider_league_id=provider_league_id,
                        offset=offset,
                        limit=self._batch_size,
                    )

                stats["fetched"] = len(data)

                if not data:
                    return stats

                saved, skipped = await self._save_batch_idempotent(
                    league_id=league_id,
                    provider=provider,
                    matches=data,
                )
                stats["saved"] = saved
                stats["skipped"] = skipped

                return stats

            except Exception as e:
                stats["retries"] = attempt + 1
                if attempt < self._max_retries - 1:
                    delay = exponential_backoff(attempt)
                    logger.warning(
                        "batch_fetch_retry",
                        league=league_id,
                        attempt=attempt + 1,
                        delay=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)
                else:
                    stats["errors"].append(f"Failed after {self._max_retries} retries: {e}")
                    logger.error(
                        "batch_fetch_failed",
                        league=league_id,
                        offset=offset,
                        error=str(e),
                    )

        return stats

    async def _fetch_batch_from_provider(
        self,
        provider: str,
        provider_league_id: str,
        offset: int,
        limit: int,
    ) -> list[dict]:
        """Fetch a batch of matches from a provider.

        Override this method to implement actual API calls.
        """
        logger.debug(
            "fetching_batch",
            provider=provider,
            provider_league_id=provider_league_id,
            offset=offset,
            limit=limit,
        )
        return []

    async def _save_batch_idempotent(
        self,
        league_id: str,
        provider: str,
        matches: list[dict],
    ) -> tuple[int, int]:
        """Save matches with idempotency (upsert by external_id).

        Override this method to implement actual DB operations.

        Returns:
            Tuple of (saved_count, skipped_count)
        """
        saved = 0
        skipped = 0

        for match in matches:
            external_id = match.get("external_id")
            if not external_id:
                skipped += 1
                continue

            logger.debug(
                "upsert_match",
                league=league_id,
                external_id=external_id,
            )
            saved += 1

        return saved, skipped

    def _log_summary(self, results: dict[str, dict]) -> None:
        """Log summary of all league processing results."""
        total = len(results)
        success = sum(1 for r in results.values() if r.get("status") == "success")
        failed = sum(1 for r in results.values() if r.get("status") == "failed")
        timeout = sum(1 for r in results.values() if r.get("status") == "timeout")
        skipped = sum(1 for r in results.values() if r.get("status") == "skipped")

        total_matches = sum(r.get("matches_fetched", 0) for r in results.values())
        saved_matches = sum(r.get("matches_saved", 0) for r in results.values())

        logger.info(
            "league_processing_summary",
            total=total,
            success=success,
            failed=failed,
            timeout=timeout,
            skipped=skipped,
            total_matches=total_matches,
            saved_matches=saved_matches,
            leagues=list(results.keys()),
        )


def get_league_processor(
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_concurrent_leagues: int = DEFAULT_MAX_CONCURRENT_LEAGUES,
    max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
    league_timeout_seconds: int = DEFAULT_LEAGUE_TIMEOUT_SECONDS,
) -> LeagueProcessor:
    """Get a configured LeagueProcessor instance."""
    return LeagueProcessor(
        batch_size=batch_size,
        max_concurrent_leagues=max_concurrent_leagues,
        max_concurrent_requests=max_concurrent_requests,
        league_timeout_seconds=league_timeout_seconds,
    )
