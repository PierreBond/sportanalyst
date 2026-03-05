from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import json

from sports_common.config import settings
from sports_common.kafka_client import KafkaProducerWrapper
from sports_common.logging import get_logger
from sports_common.schemas.biometrics import BiometricFeature

logger = get_logger(__name__)


class BiometricPublisher:
    """Publishes biometric features to Kafka for consumption by feature pipeline."""

    def __init__(self) -> None:
        self._producer: KafkaProducerWrapper | None = None

    @property
    def producer(self) -> KafkaProducerWrapper:
        if self._producer is None:
            self._producer = KafkaProducerWrapper()
        return self._producer

    def publish_biometric_features(
        self,
        player_id: str,
        match_id: str | None,
        acwr: float | None = None,
        hrv: float | None = None,
        player_load: float | None = None,
        wellness_score: float | None = None,
        injury_risk: float | None = None,
    ) -> None:
        """Publish biometric features for a player.

        Args:
            player_id: Player UUID
            match_id: Match UUID (optional)
            acwr: Acute:Chronic Workload Ratio
            hrv: Heart rate variability
            player_load: Current player load
            wellness_score: Wellness score (0-1)
            injury_risk: Injury risk probability (0-1)
        """
        feature = BiometricFeature(
            player_id=player_id,
            match_id=match_id,
            acwr=acwr,
            hrv=hrv,
            player_load=player_load,
            wellness_score=wellness_score,
            injury_risk=injury_risk,
            computed_at=datetime.now(timezone.utc),
        )

        message = feature.model_dump(mode="json")

        self.producer.publish(
            topic=settings.kafka_topics["processed_biometric_features"],
            value=message,
            key=player_id,
        )

        logger.info(
            "biometric_features_published",
            player_id=player_id,
            match_id=match_id,
            acwr=acwr,
            hrv=hrv,
            wellness_score=wellness_score,
            injury_risk=injury_risk,
        )

    def publish_team_biometrics(
        self,
        team_id: str,
        player_features: list[dict[str, Any]],
    ) -> None:
        """Publish aggregated team biometric features.

        Args:
            team_id: Team UUID
            player_features: List of player biometric feature dicts
        """
        if not player_features:
            logger.warning("no_player_features_to_publish", team_id=team_id)
            return

        total_acwr = sum(p.get("acwr", 0) or 0 for p in player_features if p.get("acwr") is not None)
        count_acwr = sum(1 for p in player_features if p.get("acwr") is not None)
        avg_acwr = total_acwr / count_acwr if count_acwr > 0 else None

        total_wellness = sum(p.get("wellness_score", 0) or 0 for p in player_features if p.get("wellness_score") is not None)
        count_wellness = sum(1 for p in player_features if p.get("wellness_score") is not None)
        avg_wellness = total_wellness / count_wellness if count_wellness > 0 else None

        total_injury_risk = sum(p.get("injury_risk", 0) or 0 for p in player_features if p.get("injury_risk") is not None)
        count_injury_risk = sum(1 for p in player_features if p.get("injury_risk") is not None)
        avg_injury_risk = total_injury_risk / count_injury_risk if count_injury_risk > 0 else None

        high_risk_count = sum(
            1 for p in player_features
            if p.get("injury_risk") is not None and p.get("injury_risk", 0) >= 0.7
        )

        message = {
            "team_id": team_id,
            "avg_acwr": avg_acwr,
            "avg_wellness_score": avg_wellness,
            "avg_injury_risk": avg_injury_risk,
            "high_risk_players": high_risk_count,
            "player_count": len(player_features),
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

        self.producer.publish(
            topic=settings.kafka_topics["processed_biometric_features"],
            value=message,
            key=team_id,
        )

        logger.info(
            "team_biometrics_published",
            team_id=team_id,
            player_count=len(player_features),
            avg_acwr=avg_acwr,
            avg_wellness=avg_wellness,
            avg_injury_risk=avg_injury_risk,
            high_risk_count=high_risk_count,
        )

    def close(self) -> None:
        """Close the Kafka producer."""
        if self._producer:
            self._producer.close()
            self._producer = None


biometric_publisher = BiometricPublisher()
