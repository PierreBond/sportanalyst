from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sports_common.config import settings
from sports_common.kafka_client import KafkaProducerWrapper
from sports_common.logging import get_logger
from sports_common.schemas.sentiment import SentimentResult, NewsAlert, AggregatedSentiment
from uuid import UUID

logger = get_logger(__name__)


class NLPPublisher:
    """Publishes NLP/sentiment results to Kafka."""

    def __init__(self) -> None:
        self._producer: KafkaProducerWrapper | None = None

    @property
    def producer(self) -> KafkaProducerWrapper:
        if self._producer is None:
            self._producer = KafkaProducerWrapper()
        return self._producer

    def publish_sentiment(
        self,
        entity_id: str,
        entity_type: str,
        source: str,
        score: float,
        volume: int = 1,
    ) -> None:
        """Publish individual sentiment score.

        Args:
            entity_id: Team or player UUID
            entity_type: 'team' or 'player'
            source: Source (twitter, reddit, news)
            score: Sentiment score (-1.0 to 1.0)
            volume: Number of texts analyzed
        """
        sentiment = SentimentResult(
            entity_type=entity_type,
            entity_id=UUID(entity_id) if entity_id else UUID(int=0),
            source=source,
            score=score,
            volume=volume,
            captured_at=datetime.now(timezone.utc),
        )

        message = sentiment.model_dump(mode="json")

        self.producer.publish(
            topic=settings.kafka_topics["processed_sentiment"],
            value=message,
            key=entity_id,
        )

        logger.info(
            "sentiment_published",
            entity_id=entity_id,
            entity_type=entity_type,
            source=source,
            score=score,
            volume=volume,
        )

    def publish_raw_text(
        self,
        text: str,
        entity_id: str,
        entity_type: str,
        source: str,
        post_id: str | None = None,
        author: str | None = None,
    ) -> None:
        """Publish raw text to Kafka for downstream processing.

        Args:
            text: Raw text content
            entity_id: Entity UUID
            entity_type: 'team' or 'player'
            source: Source platform
            post_id: Optional post ID
            author: Optional author
        """
        from sports_common.schemas.sentiment import RawTextPayload

        raw = RawTextPayload(
            text=text,
            entity_id=UUID(entity_id) if entity_id else UUID(int=0),
            entity_type=entity_type,
            source=source,
            post_id=post_id,
            author=author,
            captured_at=datetime.now(timezone.utc),
        )

        message = raw.model_dump(mode="json")

        self.producer.publish(
            topic=settings.kafka_topics["raw_social_text"],
            value=message,
            key=entity_id,
        )

        logger.debug(
            "raw_text_published",
            entity_id=entity_id,
            source=source,
            text_length=len(text),
        )

    def publish_aggregated_sentiment(
        self,
        entity_id: str,
        entity_type: str,
        twitter_sentiment: float | None = None,
        reddit_sentiment: float | None = None,
        news_sentiment: float | None = None,
        total_volume: int = 0,
    ) -> None:
        """Publish aggregated sentiment across sources.

        Args:
            entity_id: Entity UUID
            entity_type: 'team' or 'player'
            twitter_sentiment: Aggregated Twitter sentiment
            reddit_sentiment: Aggregated Reddit sentiment
            news_sentiment: Aggregated News sentiment
            total_volume: Total texts analyzed
        """
        aggregated = AggregatedSentiment(
            entity_id=UUID(entity_id) if entity_id else UUID(int=0),
            entity_type=entity_type,
            twitter_sentiment=twitter_sentiment,
            reddit_sentiment=reddit_sentiment,
            news_sentiment=news_sentiment,
            total_volume=total_volume,
            computed_at=datetime.now(timezone.utc),
        )

        message = aggregated.model_dump(mode="json")

        self.producer.publish(
            topic=settings.kafka_topics["processed_sentiment"],
            value=message,
            key=entity_id,
        )

        logger.info(
            "aggregated_sentiment_published",
            entity_id=entity_id,
            entity_type=entity_type,
            twitter_sentiment=twitter_sentiment,
            reddit_sentiment=reddit_sentiment,
            news_sentiment=news_sentiment,
            total_volume=total_volume,
        )

    def publish_news_alert(
        self,
        alert: NewsAlert,
    ) -> None:
        """Publish breaking news alert to Kafka.

        Args:
            alert: NewsAlert object
        """
        message = alert.model_dump(mode="json")

        self.producer.publish(
            topic="processed.news-alerts",
            value=message,
            key=str(alert.entity_id),
        )

        logger.info(
            "news_alert_published",
            alert_type=alert.alert_type,
            entity_id=alert.entity_id,
            severity=alert.severity,
        )

    def close(self) -> None:
        """Close the Kafka producer."""
        if self._producer:
            self._producer.close()
            self._producer = None


nlp_publisher = NLPPublisher()
