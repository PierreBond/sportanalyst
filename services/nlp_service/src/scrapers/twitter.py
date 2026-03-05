from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import AsyncIterator

from sports_common.config import settings
from sports_common.logging import get_logger
from sports_common.schemas.sentiment import RawTextPayload

logger = get_logger(__name__)


class TwitterScraper:
    """Twitter/X scraper using the bird CLI (GraphQL, no API key required).

    Bypasses Twitter API v2 rate limits and costs by driving the X GraphQL
    API directly via browser session cookies through the bird CLI.
    Credentials are read from TWITTER_AUTH_TOKEN / TWITTER_CT0 env vars,
    or auto-extracted from a logged-in Chrome/Firefox profile by bird.
    """

    def __init__(
        self,
        auth_token: str | None = None,
        ct0: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._auth_token = auth_token or settings.twitter_auth_token
        self._ct0 = ct0 or settings.twitter_ct0
        self._timeout = timeout
        self._seen_hashes: set[str] = set()

    def _build_cmd(self, *args: str) -> list[str]:
        """Build a bird CLI command with credentials injected."""
        cmd = ["bird"]
        if self._auth_token:
            cmd += ["--auth-token", self._auth_token]
        if self._ct0:
            cmd += ["--ct0", self._ct0]
        cmd += list(args)
        return cmd

    async def _run_bird(self, *args: str) -> list[dict]:
        """Execute a bird command and return parsed JSON output."""
        cmd = self._build_cmd(*args)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
            if proc.returncode != 0:
                logger.error(
                    "bird_cmd_failed",
                    args=args,
                    stderr=stderr.decode(errors="replace")[:300],
                )
                return []
            raw = stdout.decode(errors="replace").strip()
            if not raw:
                return []
            result = json.loads(raw)
            # bird returns either a list of tweets or a wrapped object
            return result if isinstance(result, list) else result.get("data", [])
        except asyncio.TimeoutError:
            logger.error("bird_cmd_timeout", args=args)
            return []
        except json.JSONDecodeError as e:
            logger.error("bird_json_parse_failed", error=str(e))
            return []
        except Exception as e:
            logger.error("bird_cmd_error", error=str(e))
            return []

    async def close(self) -> None:
        """No-op — bird uses no persistent connection."""

    async def health_check(self) -> bool:
        """Verify bird credentials work by running whoami."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *self._build_cmd("whoami"),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10.0)
            healthy = proc.returncode == 0
            if not healthy:
                logger.error("twitter_health_check_failed", reason="bad credentials")
            return healthy
        except Exception as e:
            logger.error("twitter_health_check_failed", error=str(e))
            return False

    def _normalize_text(self, text: str) -> str:
        normalized = text.lower().strip()
        return " ".join(normalized.split())

    def _compute_hash(self, text: str) -> str:
        return hashlib.sha256(self._normalize_text(text).encode()).hexdigest()

    def _is_seen(self, text: str) -> bool:
        h = self._compute_hash(text)
        if h in self._seen_hashes:
            return True
        self._seen_hashes.add(h)
        return False

    async def search_tweets(
        self,
        query: str,
        max_results: int = 100,
        start_time: datetime | None = None,  # kept for interface compatibility
    ) -> list[RawTextPayload]:
        """Search tweets matching a query via bird CLI.

        Args:
            query: Search query (e.g., "Arsenal FC #AFC -is:retweet")
            max_results: Maximum tweets to fetch (capped at 100)
            start_time: Unused — bird handles recency internally

        Returns:
            List of RawTextPayload objects
        """
        tweets = await self._run_bird(
            "search", query, "--json", "-n", str(min(max_results, 100))
        )
        return self._parse_tweets(tweets, "twitter")

    async def search_tweets_stream(
        self,
        queries: list[str],
        interval_minutes: int = 15,
    ) -> AsyncIterator[RawTextPayload]:
        """Poll multiple queries on a fixed interval, yielding new tweets.

        Args:
            queries: List of search queries
            interval_minutes: Polling interval

        Yields:
            Deduplicated RawTextPayload objects
        """
        while True:
            for query in queries:
                for tweet in await self.search_tweets(query):
                    if not self._is_seen(tweet.text):
                        yield tweet
            await asyncio.sleep(interval_minutes * 60)

    async def fetch_team_mentions(
        self,
        team_name: str,
        league: str,
        max_results: int = 50,
    ) -> list[RawTextPayload]:
        """Fetch tweets mentioning a team.

        Args:
            team_name: Team name to search
            league: League abbreviation (e.g., "EPL", "NBA")
            max_results: Max tweets to fetch

        Returns:
            List of RawTextPayload objects
        """
        query = f"{team_name} ({league}) -is:retweet lang:en"
        return await self.search_tweets(query, max_results)

    async def fetch_player_mentions(
        self,
        player_name: str,
        max_results: int = 50,
    ) -> list[RawTextPayload]:
        """Fetch tweets mentioning a player.

        Args:
            player_name: Player name to search
            max_results: Max tweets to fetch

        Returns:
            List of RawTextPayload objects
        """
        query = f'"{player_name}" -is:retweet lang:en'
        return await self.search_tweets(query, max_results)

    def _parse_tweets(
        self,
        tweets: list[dict],
        source: str,
    ) -> list[RawTextPayload]:
        """Parse bird JSON output into RawTextPayload objects."""
        payloads = []
        for tweet in tweets:
            text = tweet.get("text", "")
            if not text or self._is_seen(text):
                continue

            # bird nests author info under an "author" object
            author = tweet.get("author") or {}
            author_id = author.get("id") or tweet.get("authorId", "unknown")
            author_username = author.get("username", "unknown")

            created_at = tweet.get("createdAt") or tweet.get("created_at")
            if created_at:
                try:
                    captured_at = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )
                except ValueError:
                    captured_at = datetime.now(timezone.utc)
            else:
                captured_at = datetime.now(timezone.utc)

            payloads.append(
                RawTextPayload(
                    text=text,
                    entity_id=author_id,
                    entity_type="player",
                    source=source,
                    post_id=tweet.get("id"),
                    author=author_username,
                    captured_at=captured_at,
                )
            )

        return payloads

    def clear_deduplication_cache(self) -> None:
        """Clear the in-memory deduplication cache."""
        self._seen_hashes.clear()
        logger.info("twitter_dedupe_cache_cleared")
