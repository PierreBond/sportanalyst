from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import AsyncIterator
from xml.etree import ElementTree

import httpx

from sports_common.logging import get_logger
from sports_common.schemas.sentiment import RawTextPayload

logger = get_logger(__name__)


class NewsRSSScraper:
    """RSS feed scraper for sports news.

    Supports:
    - ESPN
    - BBC Sport
    - The Athletic
    - Bleacher Report
    """

    RSS_FEEDS = {
        "espn": "https://www.espn.com/espn/rss/news",
        "bbc": "https://feeds.bbci.co.uk/sport/rss.xml",
        "bleacher": "https://bleacherreport.com/articles/feed",
    }

    def __init__(
        self,
        timeout: float = 30.0,
    ) -> None:
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._seen_hashes: set[str] = set()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10.0, read=self._timeout),
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    async def health_check(self) -> bool:
        """Verify connectivity to RSS feeds."""
        try:
            response = await self.client.get(
                self.RSS_FEEDS["espn"],
                timeout=self._timeout,
            )
            return response.status_code == 200
        except Exception as e:
            logger.error("news_health_check_failed", error=str(e))
            return False

    def _normalize_text(self, text: str) -> str:
        """Normalize article text for deduplication."""
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

    async def fetch_feed(
        self,
        source: str,
    ) -> list[RawTextPayload]:
        """Fetch articles from an RSS feed.

        Args:
            source: Feed source name (espn, bbc, bleacher)

        Returns:
            List of RawTextPayload objects
        """
        feed_url = self.RSS_FEEDS.get(source.lower())
        if not feed_url:
            logger.warning("unknown_feed_source", source=source)
            return []

        try:
            response = await self.client.get(feed_url, timeout=self._timeout)
            response.raise_for_status()

            return self._parse_rss(response.text, source)
        except Exception as e:
            logger.error("rss_fetch_failed", source=source, error=str(e))
            return []

    async def fetch_all_feeds(self) -> list[RawTextPayload]:
        """Fetch articles from all configured RSS feeds.

        Returns:
            List of RawTextPayload objects from all sources
        """
        all_payloads = []

        for source in self.RSS_FEEDS.keys():
            payloads = await self.fetch_feed(source)
            all_payloads.extend(payloads)

        return all_payloads

    async def fetch_team_news(
        self,
        team_name: str,
        sources: list[str] | None = None,
    ) -> list[RawTextPayload]:
        """Fetch news articles mentioning a team.

        Args:
            team_name: Team name to search
            sources: List of sources to search (defaults to all)

        Returns:
            List of RawTextPayload objects
        """
        if sources is None:
            sources = list(self.RSS_FEEDS.keys())

        all_payloads = []
        for source in sources:
            payloads = await self.fetch_feed(source)
            for payload in payloads:
                if team_name.lower() in payload.text.lower():
                    all_payloads.append(payload)

        return all_payloads

    async def fetch_player_news(
        self,
        player_name: str,
        sources: list[str] | None = None,
    ) -> list[RawTextPayload]:
        """Fetch news articles mentioning a player.

        Args:
            player_name: Player name to search
            sources: List of sources to search

        Returns:
            List of RawTextPayload objects
        """
        if sources is None:
            sources = list(self.RSS_FEEDS.keys())

        all_payloads = []
        for source in sources:
            payloads = await self.fetch_feed(source)
            for payload in payloads:
                if player_name.lower() in payload.text.lower():
                    all_payloads.append(payload)

        return all_payloads

    async def fetch_news_stream(
        self,
        interval_minutes: int = 15,
    ) -> AsyncIterator[RawTextPayload]:
        """Stream news articles continuously.

        Args:
            interval_minutes: How often to poll

        Yields:
            RawTextPayload objects as they are collected
        """
        import asyncio
        while True:
            articles = await self.fetch_all_feeds()
            for article in articles:
                if not self._is_seen(article.text):
                    yield article

            await asyncio.sleep(interval_minutes * 60)

    def _parse_rss(
        self,
        xml_content: str,
        source: str,
    ) -> list[RawTextPayload]:
        """Parse RSS XML into RawTextPayload objects."""
        try:
            root = ElementTree.fromstring(xml_content)
        except ElementTree.ParseError as e:
            logger.error("rss_parse_error", source=source, error=str(e))
            return []

        payloads = []
        for item in root.findall(".//item"):
            title = self._get_text(item, "title")
            description = self._get_text(item, "description")
            link = self._get_text(item, "link")

            full_text = f"{title}. {description}" if description else title

            if not full_text or self._is_seen(full_text):
                continue

            pub_date = self._get_text(item, "pubDate")
            captured_at = self._parse_date(pub_date) if pub_date else datetime.now(timezone.utc)

            payload = RawTextPayload(
                text=full_text[:5000],
                entity_id=source,
                entity_type="team",
                source=f"news_{source}",
                post_id=link,
                captured_at=captured_at,
            )
            payloads.append(payload)

        return payloads

    def _get_text(self, element: ElementTree.Element, tag: str) -> str:
        """Safely get text from XML element."""
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        return ""

    def _parse_date(self, date_str: str) -> datetime:
        """Parse various date formats from RSS feeds."""
        import email.utils

        try:
            parsed = email.utils.parsedate_to_datetime(date_str)
            return parsed.replace(tzinfo=timezone.utc)
        except Exception:
            pass

        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        return datetime.now(timezone.utc)

    def clear_deduplication_cache(self) -> None:
        """Clear the deduplication cache."""
        self._seen_hashes.clear()
        logger.info("news_dedupe_cache_cleared")
