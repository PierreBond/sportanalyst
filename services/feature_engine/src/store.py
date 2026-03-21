from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "libs"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "alembic"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from models import FeatureStore, Match
from sports_common.config import settings
from sports_common.kafka_client import KafkaProducerWrapper
from sports_common.schemas.features import FeatureVector

logger = structlog.get_logger(__name__)


class FeatureStoreWriter:
    """Writes computed features to Postgres and Kafka."""

    FEATURE_VERSION = "v1.0"
    KAFKA_TOPIC = "processed.features"

    def __init__(
        self,
        database_url: str | None = None,
        kafka_bootstrap_servers: str | None = None,
    ) -> None:
        self._database_url = database_url or settings.database_url
        self._kafka_bootstrap_servers = kafka_bootstrap_servers or settings.kafka_bootstrap_servers
        self._engine = create_async_engine(self._database_url, echo=False)
        self._async_session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._kafka_producer: KafkaProducerWrapper | None = None

    @property
    def kafka_producer(self) -> KafkaProducerWrapper:
        if self._kafka_producer is None:
            self._kafka_producer = KafkaProducerWrapper(
                bootstrap_servers=self._kafka_bootstrap_servers
            )
        return self._kafka_producer

    async def write_features(
        self,
        match_id: str,
        features: dict[str, Any],
        computed_at: datetime | None = None,
    ) -> str:
        """Write features to Postgres and publish to Kafka.

        Args:
            match_id: The match UUID to write features for
            features: Dictionary of feature name -> value
            computed_at: Timestamp when features were computed (defaults to now UTC)

        Returns:
            The feature_id of the inserted record
        """
        if computed_at is None:
            computed_at = datetime.now(timezone.utc)

        feature_id: str | None = None

        async with self._async_session_factory() as session:
            feature_record = FeatureStore(
                match_id=match_id,
                computed_at=computed_at,
                features=features,
                version=self.FEATURE_VERSION,
            )
            session.add(feature_record)
            await session.commit()
            feature_id = str(feature_record.feature_id)
            logger.info(
                "features_written_to_db",
                match_id=match_id,
                feature_id=feature_id,
                feature_count=len(features),
            )

        kafka_payload = {
            "match_id": match_id,
            "feature_id": feature_id,
            "computed_at": computed_at.isoformat(),
            "version": self.FEATURE_VERSION,
            "features": features,
        }
        self.kafka_producer.publish(
            topic=self.KAFKA_TOPIC,
            value=kafka_payload,
            key=match_id,
        )
        logger.info(
            "features_published_to_kafka",
            match_id=match_id,
            topic=self.KAFKA_TOPIC,
        )

        return feature_id

    async def write_features_batch(
        self,
        features_list: list[dict[str, Any]],
    ) -> list[str]:
        """Write multiple feature records in a batch.

        Args:
            features_list: List of dicts with 'match_id' and 'features' keys

        Returns:
            List of feature_ids
        """
        if not features_list:
            return []

        feature_ids: list[str] = []
        computed_at = datetime.now(timezone.utc)

        async with self._async_session_factory() as session:
            for item in features_list:
                feature_record = FeatureStore(
                    match_id=item["match_id"],
                    computed_at=computed_at,
                    features=item["features"],
                    version=self.FEATURE_VERSION,
                )
                session.add(feature_record)
                feature_ids.append(str(feature_record.feature_id))

            await session.commit()
            logger.info(
                "features_batch_written",
                count=len(feature_ids),
            )

        for item in features_list:
            kafka_payload = {
                "match_id": item["match_id"],
                "feature_id": feature_ids[features_list.index(item)],
                "computed_at": computed_at.isoformat(),
                "version": self.FEATURE_VERSION,
                "features": item["features"],
            }
            self.kafka_producer.publish(
                topic=self.KAFKA_TOPIC,
                value=kafka_payload,
                key=item["match_id"],
            )

        return feature_ids

    async def get_features_by_match(
        self,
        match_id: str,
    ) -> FeatureVector | None:
        """Retrieve the latest features for a match."""
        async with self._async_session_factory() as session:
            stmt = (
                select(FeatureStore)
                .where(FeatureStore.match_id == match_id)
                .order_by(FeatureStore.computed_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            feature_record = result.scalar_one_or_none()

            if feature_record:
                return FeatureVector(
                    feature_id=feature_record.feature_id,
                    match_id=feature_record.match_id,
                    computed_at=feature_record.computed_at,
                    features=feature_record.features,
                    version=feature_record.version,
                )
            return None

    async def get_all_features_for_match(
        self,
        match_id: str,
    ) -> list[FeatureVector]:
        """Retrieve all feature records for a match."""
        async with self._async_session_factory() as session:
            stmt = (
                select(FeatureStore)
                .where(FeatureStore.match_id == match_id)
                .order_by(FeatureStore.computed_at.desc())
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

            return [
                FeatureVector(
                    feature_id=r.feature_id,
                    match_id=r.match_id,
                    computed_at=r.computed_at,
                    features=r.features,
                    version=r.version,
                )
                for r in records
            ]

    def close(self) -> None:
        """Close all connections."""
        if self._kafka_producer:
            self._kafka_producer.close()
        if self._engine:
            import asyncio

            try:
                asyncio.get_event_loop().run_until_complete(self._engine.dispose())
            except RuntimeError:
                pass

    def __enter__(self) -> "FeatureStoreWriter":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
