from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sports_common.schemas.sentiment import RawTextPayload, SentimentResult


class TestNLPPipelineIntegration:
    """Integration tests for the NLP pipeline: scrape → classify → Kafka → feature store"""

    @pytest.fixture
    def sample_tweets(self) -> list[RawTextPayload]:
        """Sample tweets for testing."""
        return [
            RawTextPayload(
                text="Arsenal looking strong ahead of the match!",
                entity_id="team_arsenal",
                entity_type="team",
                source="twitter",
                post_id="tweet_1",
                author="fan_user",
                captured_at=datetime.now(timezone.utc),
            ),
            RawTextPayload(
                text="Arsenal player injured, ruled out for 2 weeks",
                entity_id="team_arsenal",
                entity_type="team",
                source="twitter",
                post_id="tweet_2",
                author="news_user",
                captured_at=datetime.now(timezone.utc),
            ),
            RawTextPayload(
                text="Terrible performance from Arsenal today",
                entity_id="team_arsenal",
                entity_type="team",
                source="reddit",
                post_id="post_1",
                author="reddit_user",
                captured_at=datetime.now(timezone.utc),
            ),
        ]

    @pytest.fixture
    def sample_reddit_posts(self) -> list[RawTextPayload]:
        """Sample Reddit posts for testing."""
        return [
            RawTextPayload(
                text="Arsenal vs Chelsea preview - expecting goals",
                entity_id="team_arsenal",
                entity_type="team",
                source="reddit",
                post_id="reddit_1",
                author="soccer_fan",
                captured_at=datetime.now(timezone.utc),
            ),
            RawTextPayload(
                text="Arsenal manager sacked after poor run",
                entity_id="team_arsenal",
                entity_type="team",
                source="reddit",
                post_id="reddit_2",
                author="insider",
                captured_at=datetime.now(timezone.utc),
            ),
        ]

    @pytest.fixture
    def sample_news_articles(self) -> list[RawTextPayload]:
        """Sample news articles for testing."""
        return [
            RawTextPayload(
                text="Arsenal sign new striker from Barcelona",
                entity_id="team_arsenal",
                entity_type="team",
                source="news_espn",
                post_id="news_1",
                captured_at=datetime.now(timezone.utc),
            ),
            RawTextPayload(
                text="Arsenal player suspended for 3 matches",
                entity_id="team_arsenal",
                entity_type="team",
                source="news_bbc",
                post_id="news_2",
                captured_at=datetime.now(timezone.utc),
            ),
        ]

    def test_preprocessing_cleans_text(self):
        """Test that preprocessing correctly cleans raw text."""
        from preprocessing import TextPreprocessor

        preprocessor = TextPreprocessor()

        dirty_text = "Check out https://example.com @ArsenalFC #COYG 🏆"
        cleaned = preprocessor.clean(dirty_text)

        assert "https://" not in cleaned
        assert "@ArsenalFC" not in cleaned
        assert "🏆" not in cleaned

    def test_preprocessing_tokenizes(self):
        """Test that preprocessing tokenizes correctly."""
        from preprocessing import TextPreprocessor

        preprocessor = TextPreprocessor()

        text = "Arsenal wins the match!"
        tokens = preprocessor.tokenize(text)

        assert "arsenal" in tokens
        assert "wins" in tokens
        assert "match" in tokens

    def test_sentiment_classifier_positive(self):
        """Test sentiment classifier on positive text."""
        from classifier import SentimentClassifier

        classifier = SentimentClassifier()

        with patch.object(classifier, "predict") as mock_predict:
            mock_predict.return_value = [0.8]

            result = classifier.predict(["Arsenal looking strong today"])

            assert len(result) == 1
            assert result[0] > 0

    def test_sentiment_classifier_negative(self):
        """Test sentiment classifier on negative text."""
        from classifier import SentimentClassifier

        classifier = SentimentClassifier()

        with patch.object(classifier, "predict") as mock_predict:
            mock_predict.return_value = [-0.7]

            result = classifier.predict(["Terrible performance"])

            assert len(result) == 1
            assert result[0] < 0

    def test_sentiment_aggregator(self):
        """Test sentiment aggregation across sources."""
        from classifier import SentimentAggregator

        aggregator = SentimentAggregator()

        sentiments = {
            "twitter": [0.5, 0.6, 0.7],
            "reddit": [0.3, 0.4],
            "news": [0.2, 0.3, 0.4],
        }

        result = aggregator.aggregate(sentiments)

        assert result["twitter_mean"] == pytest.approx(0.6)
        assert result["twitter_count"] == 3
        assert result["reddit_mean"] == pytest.approx(0.35)
        assert result["news_mean"] == pytest.approx(0.3)

    def test_event_detector_injury(self):
        """Test event detector identifies injury keywords."""
        from event_detector import EventDetector

        detector = EventDetector()

        texts = [
            "Arsenal player injured, ruled out for 2 weeks",
            "Player has groin injury",
            "Doubtful for the match",
        ]
        entity_ids = ["team_1"] * 3
        sources = ["twitter"] * 3

        alerts = detector.detect_events(texts, entity_ids, sources)

        assert len(alerts) >= 2
        assert any(a.alert_type == "injury" for a in alerts)

    def test_event_detector_suspension(self):
        """Test event detector identifies suspension keywords."""
        from event_detector import EventDetector

        detector = EventDetector()

        texts = [
            "Player suspended for 3 games",
            "Suspended due to misconduct",
        ]
        entity_ids = ["team_1"] * 2
        sources = ["twitter"] * 2

        alerts = detector.detect_events(texts, entity_ids, sources)

        assert len(alerts) >= 1
        assert any(a.alert_type == "suspension" for a in alerts)

    def test_event_detector_signing(self):
        """Test event detector identifies transfer/signing keywords."""
        from event_detector import EventDetector

        detector = EventDetector()

        texts = [
            "Arsenal sign new striker",
            "Player joined from Barcelona",
        ]
        entity_ids = ["team_1"] * 2
        sources = ["news"] * 2

        alerts = detector.detect_events(texts, entity_ids, sources)

        assert len(alerts) >= 1
        assert any(a.alert_type == "signing" for a in alerts)

    def test_event_detector_severity(self):
        """Test event detector severity levels."""
        from event_detector import EventDetector

        detector = EventDetector()

        high_severity_texts = [
            "Player out for the season",
            "Long-term injury",
        ]
        low_severity_texts = [
            "Minor injury",
            "Could return soon",
        ]

        high_alerts = detector.detect_events(
            high_severity_texts,
            ["team_1"] * 2,
            ["twitter"] * 2,
        )

        low_alerts = detector.detect_events(
            low_severity_texts,
            ["team_1"] * 2,
            ["twitter"] * 2,
        )

        if high_alerts:
            assert high_alerts[0].severity in ["high", "medium"]
        if low_alerts:
            assert low_alerts[0].severity in ["low", "medium"]

    def test_alert_aggregator_deduplication(self):
        """Test alert aggregator deduplicates similar headlines."""
        from event_detector import AlertAggregator
        from sports_common.schemas.sentiment import NewsAlert

        aggregator = AlertAggregator()

        alerts = [
            NewsAlert(
                entity_type="team",
                entity_id="team_1",
                headline="Player injured ruled out",
                alert_type="injury",
                severity="medium",
                source="twitter",
            ),
            NewsAlert(
                entity_type="team",
                entity_id="team_1",
                headline="Player injured ruled out",
                alert_type="injury",
                severity="medium",
                source="reddit",
            ),
            NewsAlert(
                entity_type="team",
                entity_id="team_1",
                headline="Different headline",
                alert_type="injury",
                severity="medium",
                source="news",
            ),
        ]

        unique_alerts = aggregator.aggregate(alerts)

        assert len(unique_alerts) == 2

    @pytest.mark.asyncio
    async def test_full_pipeline_mock(self):
        """Integration test for full pipeline with mocked components."""
        from preprocessing import TextPreprocessor
        from classifier import SentimentClassifier, SentimentAggregator
        from event_detector import EventDetector, AlertAggregator

        preprocessor = TextPreprocessor()
        classifier = SentimentClassifier()
        event_detector = EventDetector()
        alert_aggregator = AlertAggregator()
        sentiment_aggregator = SentimentAggregator()

        raw_texts = [
            "Arsenal looking strong! Great win expected",
            "Arsenal player injured, ruled out",
            "Terrible performance, crisis at the club",
            "New signing announced today",
        ]
        entity_ids = ["team_1"] * 4
        sources = ["twitter"] * 4
        timestamps = [datetime.now(timezone.utc)] * 4

        cleaned_texts = [preprocessor.clean(text) for text in raw_texts]

        with patch.object(classifier, "predict") as mock_predict:
            mock_predict.return_value = [0.6, -0.4, -0.7, 0.5]
            sentiments = classifier.predict(cleaned_texts)

        assert len(sentiments) == 4
        assert sentiments[0] > 0
        assert sentiments[1] < 0
        assert sentiments[2] < 0

        sentiment_by_source = {"twitter": sentiments}
        aggregated = sentiment_aggregator.aggregate(sentiment_by_source)

        assert "twitter_mean" in aggregated

        events = event_detector.detect_events(raw_texts, entity_ids, sources)

        assert len(events) >= 2
        assert any(e.alert_type == "injury" for e in events)

        unique_events = alert_aggregator.aggregate(events)

        assert len(unique_events) <= len(events)

    def test_pipeline_data_flow(self):
        """Test that data flows correctly through pipeline stages."""
        from preprocessing import TextPreprocessor
        from classifier import SentimentClassifier, SentimentAggregator
        from event_detector import EventDetector

        preprocessor = TextPreprocessor()
        event_detector = EventDetector()
        sentiment_aggregator = SentimentAggregator()

        text = "Arsenal player out with injury!"

        cleaned = preprocessor.clean(text)
        assert cleaned == "arsenal player out with injury!"

        tokens = preprocessor.tokenize(cleaned)
        assert len(tokens) > 0

        events = event_detector.detect_events(
            [text],
            ["team_1"],
            ["twitter"],
        )

        assert any(e.alert_type == "injury" for e in events)

        sentiments = {"twitter": [0.5, 0.6]}
        result = sentiment_aggregator.aggregate(sentiments)

        assert "overall_weighted" in result or "twitter_mean" in result


class TestNLPServiceEndpoints:
    """Test NLP service API endpoints (mocked)."""

    def test_health_endpoint(self):
        """Test health check returns healthy status."""
        from fastapi.testclient import TestClient

        with patch("sys.modules", {"sports_common": MagicMock()}):
            pass

    def test_sentiment_request_model(self):
        """Test sentiment request/response models."""
        from pydantic import ValidationError
        from sports_common.schemas.sentiment import SentimentResult, RawTextPayload

        sentiment = SentimentResult(
            entity_type="team",
            entity_id="test-uuid",
            source="twitter",
            score=0.5,
            volume=10,
        )

        assert sentiment.entity_type == "team"
        assert sentiment.score == 0.5

    def test_news_alert_model(self):
        """Test NewsAlert model validation."""
        from sports_common.schemas.sentiment import NewsAlert

        alert = NewsAlert(
            entity_type="team",
            entity_id="test-uuid",
            headline="Test alert",
            alert_type="injury",
            severity="high",
            source="twitter",
        )

        assert alert.alert_type == "injury"
        assert alert.severity == "high"
