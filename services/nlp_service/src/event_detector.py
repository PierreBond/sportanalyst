from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sports_common.logging import get_logger
from sports_common.schemas.sentiment import NewsAlert

logger = get_logger(__name__)

INJURY_KEYWORDS = [
    "ruled out",
    "injured",
    "injury",
    "doubtful",
    "out for",
    "sidelined",
    "fitness concern",
    "groin injury",
    "hamstring",
    "knee injury",
    "ankle injury",
    "muscle injury",
    "concussion",
    "fracture",
]

SUSPENSION_KEYWORDS = [
    "suspended",
    "suspension",
    "banned",
    "red card",
    "doping",
    "misconduct",
]

LINEUP_KEYWORDS = [
    "lineup",
    "starting xi",
    "team sheet",
    "formation",
    "call-up",
    "squad",
    "out for",
    "not included",
    "returns from",
]

MANAGER_KEYWORDS = [
    "manager sacked",
    "coach fired",
    "new manager",
    "manager change",
    "head coach",
    "tactical change",
]

SIGNING_KEYWORDS = [
    "signing announced",
    "transfer",
    "signed",
    "joined",
    "new signing",
    "completed transfer",
]

NEGATIVE_SENTIMENT_KEYWORDS = [
    "crisis",
    "disaster",
    "shocking",
    "humiliation",
    "embarrassing",
    "furious",
    "outrage",
    "scandal",
]

ALERT_TYPE_KEYWORDS = {
    "injury": INJURY_KEYWORDS,
    "suspension": SUSPENSION_KEYWORDS,
    "lineup": LINEUP_KEYWORDS,
    "manager": MANAGER_KEYWORDS,
    "signing": SIGNING_KEYWORDS,
    "negative": NEGATIVE_SENTIMENT_KEYWORDS,
}


class EventDetector:
    """Detect breaking news events from text.

    Detects:
    - Injury announcements
    - Suspensions
    - Lineup changes
    - Manager changes
    - Transfer signings
    - Negative sentiment spikes
    """

    def __init__(
        self,
        min_keyword_matches: int = 1,
    ) -> None:
        self.min_keyword_matches = min_keyword_matches

    def detect_events(
        self,
        texts: list[str],
        entity_ids: list[str],
        sources: list[str],
        timestamps: list[datetime] | None = None,
    ) -> list[NewsAlert]:
        """Detect breaking news events from texts.

        Args:
            texts: List of text strings to analyze
            entity_ids: List of entity IDs corresponding to texts
            sources: List of sources (twitter, reddit, news)
            timestamps: Optional list of timestamps

        Returns:
            List of NewsAlert objects
        """
        if timestamps is None:
            timestamps = [datetime.now(timezone.utc)] * len(texts)

        alerts = []
        for i, text in enumerate(texts):
            text_lower = text.lower()

            for alert_type, keywords in ALERT_TYPE_KEYWORDS.items():
                matches = sum(1 for kw in keywords if kw in text_lower)

                if matches >= self.min_keyword_matches:
                    alert = NewsAlert(
                        entity_type="team",
                        entity_id=entity_ids[i],
                        headline=text[:200],
                        alert_type=alert_type,
                        severity=self._determine_severity(alert_type, text_lower),
                        source=sources[i],
                        published_at=timestamps[i],
                        processed_at=datetime.now(timezone.utc),
                    )
                    alerts.append(alert)

                    logger.info(
                        "event_detected",
                        alert_type=alert_type,
                        entity_id=entity_ids[i],
                        source=sources[i],
                    )
                    break

        return alerts

    def detect_injuries(
        self,
        texts: list[str],
        entity_ids: list[str],
    ) -> list[NewsAlert]:
        """Detect injury-related events specifically."""
        alerts = []
        now = datetime.now(timezone.utc)

        for i, text in enumerate(texts):
            text_lower = text.lower()

            matches = sum(1 for kw in INJURY_KEYWORDS if kw in text_lower)

            if matches >= 1:
                alert = NewsAlert(
                    entity_type="team",
                    entity_id=entity_ids[i],
                    headline=text[:200],
                    alert_type="injury",
                    severity=self._determine_severity("injury", text_lower),
                    source="detector",
                    published_at=now,
                    processed_at=now,
                )
                alerts.append(alert)

        return alerts

    def detect_lineup_changes(
        self,
        texts: list[str],
        entity_ids: list[str],
    ) -> list[NewsAlert]:
        """Detect lineup change announcements."""
        alerts = []
        now = datetime.now(timezone.utc)

        for i, text in enumerate(texts):
            text_lower = text.lower()

            matches = sum(1 for kw in LINEUP_KEYWORDS if kw in text_lower)

            if matches >= 1:
                alert = NewsAlert(
                    entity_type="team",
                    entity_id=entity_ids[i],
                    headline=text[:200],
                    alert_type="lineup",
                    severity=self._determine_severity("lineup", text_lower),
                    source="detector",
                    published_at=now,
                    processed_at=now,
                )
                alerts.append(alert)

        return alerts

    def detect_signings(
        self,
        texts: list[str],
        entity_ids: list[str],
    ) -> list[NewsAlert]:
        """Detect transfer/ signing announcements."""
        alerts = []
        now = datetime.now(timezone.utc)

        for i, text in enumerate(texts):
            text_lower = text.lower()

            matches = sum(1 for kw in SIGNING_KEYWORDS if kw in text_lower)

            if matches >= 1:
                alert = NewsAlert(
                    entity_type="team",
                    entity_id=entity_ids[i],
                    headline=text[:200],
                    alert_type="signing",
                    severity="medium",
                    source="detector",
                    published_at=now,
                    processed_at=now,
                )
                alerts.append(alert)

        return alerts

    def _determine_severity(
        self,
        alert_type: str,
        text: str,
    ) -> str:
        """Determine alert severity based on keywords."""
        high_severity_patterns = {
            "injury": [
                "out for the season",
                "long-term",
                "surgery",
                "cruciate",
                "achilles",
            ],
            "suspension": [
                "multi-game",
                "season ban",
                "indefinite",
            ],
            "negative": [
                "crisis",
                "disaster",
                "scandal",
            ],
        }

        low_severity_patterns = {
            "injury": [
                "day-to-day",
                "minor",
                "slight",
                "could return",
            ],
            "lineup": [
                "expected",
                "likely",
                "probably",
            ],
        }

        patterns = high_severity_patterns.get(alert_type, [])
        if any(p in text for p in patterns):
            return "high"

        low_patterns = low_severity_patterns.get(alert_type, [])
        if any(p in text for p in low_patterns):
            return "low"

        return "medium"


class AlertAggregator:
    """Aggregate and deduplicate alerts."""

    def __init__(
        self,
        dedupe_window_minutes: int = 30,
    ) -> None:
        self.dedupe_window_minutes = dedupe_window_minutes
        self._seen_headlines: set[str] = set()

    def aggregate(
        self,
        alerts: list[NewsAlert],
    ) -> list[NewsAlert]:
        """Aggregate and deduplicate alerts.

        Args:
            alerts: List of alerts to aggregate

        Returns:
            Deduplicated list of alerts
        """
        unique_alerts = []
        seen = set()

        for alert in alerts:
            headline_key = self._normalize_headline(alert.headline)
            if headline_key in seen:
                continue

            seen.add(headline_key)
            unique_alerts.append(alert)

        return unique_alerts

    def _normalize_headline(self, headline: str) -> str:
        """Normalize headline for deduplication."""
        normalized = headline.lower()
        normalized = re.sub(r"\d+", "#", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()[:50]

    def filter_by_severity(
        self,
        alerts: list[NewsAlert],
        min_severity: str = "low",
    ) -> list[NewsAlert]:
        """Filter alerts by minimum severity.

        Args:
            alerts: List of alerts
            min_severity: Minimum severity to include (low, medium, high)

        Returns:
            Filtered list of alerts
        """
        severity_order = {"low": 0, "medium": 1, "high": 2}
        min_level = severity_order.get(min_severity, 0)

        filtered = []
        for alert in alerts:
            alert_level = severity_order.get(alert.severity, 0)
            if alert_level >= min_level:
                filtered.append(alert)

        return filtered


def detect_events(
    texts: list[str],
    entity_ids: list[str],
    sources: list[str],
) -> list[NewsAlert]:
    """Convenience function for event detection."""
    detector = EventDetector()
    return detector.detect_events(texts, entity_ids, sources)
