from __future__ import annotations

import hashlib
from datetime import datetime, timezone, timedelta
from typing import AsyncIterator

import httpx

from sports_common.config import settings
from sports_common.logging import get_logger
from sports_common.schemas.sentiment import RawTextPayload

logger = get_logger(__name__)


class RedditScraper:
    """Reddit PRAW-style scraper for sports subreddits.

    Reference: https://www.reddit.com/dev/api/
    """

    SUBREDDITS = {
        "soccer": "soccer",
        "nfl": "nfl",
        "nba": "nba",
        "baseball": "baseball",
        "hockey": "hockey",
        "fantasyfootball": "fantasyfootball",
        "sportsbook": "sportsbook",
    }

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str = "SportsPredictionSystem/1.0",
        timeout: float = 30.0,
    ) -> None:
        self._client_id = client_id or settings.reddit_client_id
        self._client_secret = client_secret or settings.reddit_client_secret
        self._user_agent = user_agent
        self._base_url = "https://oauth.reddit.com"
        self._timeout = timeout
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._client: httpx.AsyncClient | None = None
        self._seen_hashes: set[str] = set()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10.0, read=self._timeout),
            )
        return self._client

    async def _ensure_token(self) -> None:
        """Ensure we have a valid OAuth access token."""
        if self._access_token and self._token_expires_at:
            if datetime.now(timezone.utc) < self._token_expires_at:
                return

        await self._refresh_token()

    async def _refresh_token(self) -> None:
        """Refresh the OAuth access token."""
        auth = httpx.BasicAuth(self._client_id, self._client_secret)
        data = {"grant_type": "client_credentials"}

        try:
            response = await self.client.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=auth,
                data=data,
            )
            response.raise_for_status()
            token_data = response.json()

            self._access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)

            self._token_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=expires_in - 60
            )

            logger.info("reddit_token_refreshed", expires_in=expires_in)
        except Exception as e:
            logger.error("reddit_token_refresh_failed", error=str(e))
            raise

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": self._user_agent,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    async def health_check(self) -> bool:
        """Verify connectivity to Reddit API."""
        try:
            await self._ensure_token()
            response = await self.client.get(
                f"{self._base_url}/api/v1/me",
                headers=self._get_headers(),
            )
            return response.status_code == 200
        except Exception as e:
            logger.error("reddit_health_check_failed", error=str(e))
            return False

    def _normalize_text(self, text: str) -> str:
        """Normalize post/comment text for deduplication."""
        normalized = text.lower().strip()
        normalized = " ".join(normalized.split())
        return normalized

    def _compute_hash(self, text: str) -> str:
        """Compute SHA-256 hash for deduplication."""
        normalized = self._normalize_text(text)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _is_seen(self, text: str) -> bool:
        """Check if text has been seen before."""
        h = self._compute_hash(text)
        if h in self._seen_hashes:
            return True
        self._seen_hashes.add(h)
        return False

    async def fetch_subreddit_posts(
        self,
        subreddit: str,
        limit: int = 100,
        time_filter: str = "day",
    ) -> list[RawTextPayload]:
        """Fetch posts from a subreddit.

        Args:
            subreddit: Subreddit name (without r/)
            limit: Number of posts to fetch (max 100)
            time_filter: Time filter (hour, day, week, month, year, all)

        Returns:
            List of RawTextPayload objects
        """
        await self._ensure_token()

        endpoint = f"{self._base_url}/r/{subreddit}/new"
        params = {
            "limit": min(limit, 100),
            "time_filter": time_filter,
        }

        try:
            response = await self.client.get(
                endpoint,
                headers=self._get_headers(),
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            return self._parse_posts(data, "reddit")
        except Exception as e:
            logger.error("reddit_fetch_failed", subreddit=subreddit, error=str(e))
            return []

    async def fetch_team_posts(
        self,
        team_name: str,
        subreddits: list[str] | None = None,
        limit: int = 50,
    ) -> list[RawTextPayload]:
        """Fetch posts mentioning a team.

        Args:
            team_name: Team name to search
            subreddits: List of subreddits to search (defaults to all)
            limit: Max posts per subreddit

        Returns:
            List of RawTextPayload objects
        """
        if subreddits is None:
            subreddits = list(self.SUBREDDITS.values())

        query = f"title:{team_name} OR selftext:{team_name}"
        return await self._search_posts(query, subreddits, limit)

    async def fetch_player_posts(
        self,
        player_name: str,
        subreddits: list[str] | None = None,
        limit: int = 50,
    ) -> list[RawTextPayload]:
        """Fetch posts mentioning a player.

        Args:
            player_name: Player name to search
            subreddits: List of subreddits to search
            limit: Max posts per subreddit

        Returns:
            List of RawTextPayload objects
        """
        if subreddits is None:
            subreddits = list(self.SUBREDDITS.values())

        query = f'title:"{player_name}" OR selftext:"{player_name}"'
        return await self._search_posts(query, subreddits, limit)

    async def _search_posts(
        self,
        query: str,
        subreddits: list[str],
        limit: int,
    ) -> list[RawTextPayload]:
        """Search posts across multiple subreddits."""
        all_payloads = []

        for subreddit in subreddits:
            endpoint = f"{self._base_url}/r/{subreddit}/search"
            params = {
                "q": query,
                "limit": min(limit, 100),
                "sort": "new",
                "type": "link",
            }

            try:
                await self._ensure_token()
                response = await self.client.get(
                    endpoint,
                    headers=self._get_headers(),
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                payloads = self._parse_posts(data, "reddit")
                all_payloads.extend(payloads)
            except Exception as e:
                logger.warning(
                    "reddit_search_subreddit_failed",
                    subreddit=subreddit,
                    error=str(e),
                )

        return all_payloads

    async def fetch_posts_stream(
        self,
        subreddits: list[str] | None = None,
        interval_minutes: int = 15,
    ) -> AsyncIterator[RawTextPayload]:
        """Stream posts continuously from subreddits.

        Args:
            subreddits: List of subreddits (defaults to all)
            interval_minutes: How often to poll

        Yields:
            RawTextPayload objects as they are collected
        """
        if subreddits is None:
            subreddits = list(self.SUBREDDITS.values())

        import asyncio
        while True:
            for subreddit in subreddits:
                posts = await self.fetch_subreddit_posts(subreddit)
                for post in posts:
                    if not self._is_seen(post.text):
                        yield post

            await asyncio.sleep(interval_minutes * 60)

    def _parse_posts(
        self,
        data: dict,
        source: str,
    ) -> list[RawTextPayload]:
        """Parse Reddit API response into RawTextPayload objects."""
        posts = data.get("data", {}).get("children", [])

        payloads = []
        for item in posts:
            post = item.get("data", {})
            text = post.get("selftext", "") or post.get("title", "")
            title = post.get("title", "")

            full_text = f"{title}. {text}" if text else title

            if not full_text or self._is_seen(full_text):
                continue

            created_utc = post.get("created_utc", 0)
            if created_utc:
                captured_at = datetime.fromtimestamp(created_utc, tz=timezone.utc)
            else:
                captured_at = datetime.now(timezone.utc)

            payload = RawTextPayload(
                text=full_text,
                entity_id=post.get("subreddit", "unknown"),
                entity_type="team",
                source=source,
                post_id=post.get("id"),
                author=post.get("author"),
                captured_at=captured_at,
            )
            payloads.append(payload)

        return payloads

    def clear_deduplication_cache(self) -> None:
        """Clear the deduplication cache."""
        self._seen_hashes.clear()
        logger.info("reddit_dedupe_cache_cleared")
