from __future__ import annotations

import httpx
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

from sports_common.config import settings
from sports_common.schemas.biometrics import PlayerBiometric
from sports_common.logging import get_logger

from .base_adapter import BaseAdapter

logger = get_logger(__name__)


class CatapultAdapter(BaseAdapter):
    """Catapult sports technology biometric data adapter.

    Catapult provides wearable sensor data including:
    - Player load (workload)
    - Sprint distance
    - Heart rate metrics
    - GPS position data

    Reference: https://developers.catapultsports.com/
    """

    provider_name = "catapult"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key or settings.catapult_api_key
        self._base_url = base_url or settings.catapult_base_url or "https://api.catapultsports.com/v1"
        super().__init__(base_url=self._base_url, api_key=self._api_key, timeout=timeout)

    def _get_headers(self) -> dict[str, str]:
        headers = super()._get_headers()
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
        return headers

    async def health_check(self) -> bool:
        """Verify connectivity to the Catapult API."""
        try:
            response = await self.client.get("/health")
            return response.status_code == 200
        except Exception as e:
            logger.error("catapult_health_check_failed", error=str(e))
            return False

    async def fetch_athlete_workload(
        self,
        athlete_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[PlayerBiometric]:
        """Fetch athlete workload data for a date range.

        Args:
            athlete_id: Catapult athlete/player ID
            start_date: Start of the date range
            end_date: End of the date range

        Returns:
            List of PlayerBiometric records
        """
        endpoint = f"/athletes/{athlete_id}/metrics"
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "metrics": "player_load,sprint_distance,total_distance",
        }

        try:
            response = await self.fetch_with_retry("GET", endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            return self._map_workload_data(athlete_id, data)
        except Exception as e:
            logger.error(
                "fetch_athlete_workload_failed",
                athlete_id=athlete_id,
                error=str(e),
            )
            return []

    async def fetch_athlete_workload_stream(
        self,
        athlete_id: str,
        start_date: datetime,
    ) -> AsyncIterator[PlayerBiometric]:
        """Stream athlete workload data from start_date to now.

        Args:
            athlete_id: Catapult athlete/player ID
            start_date: Start streaming from this date

        Yields:
            PlayerBiometric records as they become available
        """
        end_date = datetime.now(timezone.utc)
        batch_size = timedelta(days=7)

        current_start = start_date
        while current_start < end_date:
            current_end = min(current_start + batch_size, end_date)
            biometrics = await self.fetch_athlete_workload(
                athlete_id,
                current_start,
                current_end,
            )
            for bio in biometrics:
                yield bio
            current_start = current_end

    async def fetch_team_workloads(
        self,
        team_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, list[PlayerBiometric]]:
        """Fetch workload data for all athletes in a team.

        Args:
            team_id: Catapult team ID
            start_date: Start of the date range
            end_date: End of the date range

        Returns:
            Dictionary mapping athlete_id to list of PlayerBiometric records
        """
        endpoint = f"/teams/{team_id}/athletes"
        try:
            response = await self.fetch_with_retry("GET", endpoint)
            response.raise_for_status()
            athletes = response.json()

            results: dict[str, list[PlayerBiometric]] = {}
            for athlete in athletes:
                athlete_id = athlete.get("id")
                if athlete_id:
                    biometrics = await self.fetch_athlete_workload(
                        athlete_id,
                        start_date,
                        end_date,
                    )
                    results[athlete_id] = biometrics

            return results
        except Exception as e:
            logger.error(
                "fetch_team_workloads_failed",
                team_id=team_id,
                error=str(e),
            )
            return {}

    async def fetch_heart_rate_data(
        self,
        athlete_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[PlayerBiometric]:
        """Fetch heart rate data for an athlete.

        Args:
            athlete_id: Catapult athlete/player ID
            start_date: Start of the date range
            end_date: End of the date range

        Returns:
            List of PlayerBiometric records with HRV/resting HR
        """
        endpoint = f"/athletes/{athlete_id}/heart_rate"
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        try:
            response = await self.fetch_with_retry("GET", endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            return self._map_hr_data(athlete_id, data)
        except Exception as e:
            logger.error(
                "fetch_heart_rate_failed",
                athlete_id=athlete_id,
                error=str(e),
            )
            return []

    def _map_workload_data(
        self,
        athlete_id: str,
        data: dict,
    ) -> list[PlayerBiometric]:
        """Map Catapult workload response to PlayerBiometric schema."""
        biometrics = []
        athlete_uuid = self._get_player_uuid(athlete_id)

        metrics = data.get("metrics", [])
        for record in metrics:
            timestamp = record.get("timestamp")
            if not timestamp:
                continue

            recorded_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

            player_load = record.get("player_load")
            if player_load is not None:
                biometrics.append(
                    PlayerBiometric(
                        player_id=athlete_uuid,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        metric_type="player_load",
                        value=player_load,
                        unit="au",
                    )
                )

            sprint_dist = record.get("sprint_distance")
            if sprint_dist is not None:
                biometrics.append(
                    PlayerBiometric(
                        player_id=athlete_uuid,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        metric_type="sprint_distance",
                        value=sprint_dist,
                        unit="meters",
                    )
                )

            total_dist = record.get("total_distance")
            if total_dist is not None:
                biometrics.append(
                    PlayerBiometric(
                        player_id=athlete_uuid,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        metric_type="total_distance",
                        value=total_dist,
                        unit="meters",
                    )
                )

        return biometrics

    def _map_hr_data(
        self,
        athlete_id: str,
        data: dict,
    ) -> list[PlayerBiometric]:
        """Map Catapult heart rate response to PlayerBiometric schema."""
        biometrics = []
        athlete_uuid = self._get_player_uuid(athlete_id)

        readings = data.get("heart_rate_readings", [])
        for record in readings:
            timestamp = record.get("timestamp")
            if not timestamp:
                continue

            recorded_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

            hrv = record.get("hrv")
            if hrv is not None:
                biometrics.append(
                    PlayerBiometric(
                        player_id=athlete_uuid,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        metric_type="hrv",
                        value=hrv,
                        unit="ms",
                    )
                )

            resting_hr = record.get("resting_heart_rate")
            if resting_hr is not None:
                biometrics.append(
                    PlayerBiometric(
                        player_id=athlete_uuid,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        metric_type="resting_hr",
                        value=resting_hr,
                        unit="bpm",
                    )
                )

            avg_hr = record.get("average_heart_rate")
            if avg_hr is not None:
                biometrics.append(
                    PlayerBiometric(
                        player_id=athlete_uuid,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        metric_type="avg_hr",
                        value=avg_hr,
                        unit="bpm",
                    )
                )

        return biometrics

    def _get_player_uuid(self, external_id: str) -> str:
        """Convert external Catapult ID to internal UUID.

        In production, this would look up from the players table.
        For now, generates a deterministic UUID from the external ID.
        """
        import uuid
        namespace = uuid.NAMESPACE_DNS
        return str(uuid.uuid5(namespace, f"catapult_{external_id}"))
