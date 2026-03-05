from __future__ import annotations

import httpx
from datetime import datetime, timezone
from typing import AsyncIterator

from sports_common.config import settings
from sports_common.schemas.biometrics import PlayerBiometric
from sports_common.logging import get_logger

from .base_adapter import BaseAdapter

logger = get_logger(__name__)


class WhoopAdapter(BaseAdapter):
    """WHOOP biometric data adapter.

    WHOOP provides wearable health and recovery data including:
    - Heart rate variability (HRV)
    - Resting heart rate (RHR)
    - Sleep performance
    - Recovery score
    - Strain

    Reference: https://developer.whoop.com/
    """

    provider_name = "whoop"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._client_id = client_id or settings.whoop_client_id
        self._client_secret = client_secret or settings.whoop_client_secret
        self._base_url = "https://api.prod.whoop.com"
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        super().__init__(base_url=self._base_url, api_key=None, timeout=timeout)

    def _get_headers(self) -> dict[str, str]:
        headers = super()._get_headers()
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    async def _ensure_token(self) -> None:
        """Ensure we have a valid OAuth access token."""
        if self._access_token and self._token_expires_at:
            if datetime.now(timezone.utc) < self._token_expires_at:
                return

        await self._refresh_token()

    async def _refresh_token(self) -> None:
        """Refresh the OAuth access token."""
        token_url = "https://api.prod.whoop.com/oauth/token"
        data = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "client_credentials",
        }

        try:
            response = await httpx.AsyncClient().post(token_url, data=data, timeout=self._timeout)
            response.raise_for_status()
            token_data = response.json()

            self._access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)

            self._token_expires_at = datetime.now(timezone.utc) + datetime.timedelta(
                seconds=expires_in - 60
            )

            logger.info("whoop_token_refreshed", expires_in=expires_in)
        except Exception as e:
            logger.error("whoop_token_refresh_failed", error=str(e))
            raise

    async def health_check(self) -> bool:
        """Verify connectivity to the WHOOP API."""
        try:
            await self._ensure_token()
            response = await self.client.get("/developer/health")
            return response.status_code == 200
        except Exception as e:
            logger.error("whoop_health_check_failed", error=str(e))
            return False

    async def fetch_user_profile(self) -> dict:
        """Fetch the authenticated user's profile."""
        await self._ensure_token()
        endpoint = "/v1/user"

        try:
            response = await self.fetch_with_retry("GET", endpoint)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("fetch_user_profile_failed", error=str(e))
            return {}

    async def fetch_cycles(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict]:
        """Fetch sleep/recovery cycles for a date range.

        Args:
            start_date: Start of the date range
            end_date: End of the date range

        Returns:
            List of cycle records with sleep and recovery data
        """
        await self._ensure_token()
        endpoint = "/v1/cycle"
        params = {
            "start": int(start_date.timestamp() * 1000),
            "end": int(end_date.timestamp() * 1000),
        }

        try:
            response = await self.fetch_with_retry("GET", endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("records", [])
        except Exception as e:
            logger.error("fetch_cycles_failed", error=str(e))
            return []

    async def fetch_cycles_stream(
        self,
        start_date: datetime,
    ) -> AsyncIterator[dict]:
        """Stream cycle data from start_date to now.

        Args:
            start_date: Start streaming from this date

        Yields:
            Cycle records as they become available
        """
        end_date = datetime.now(timezone.utc)
        page_size = 50

        cursor = None
        while True:
            cycles = await self._fetch_cycles_page(start_date, end_date, cursor, page_size)
            if not cycles:
                break

            for cycle in cycles:
                yield cycle

            if len(cycles) < page_size:
                break

            cursor = cycles[-1].get("id")

    async def _fetch_cycles_page(
        self,
        start_date: datetime,
        end_date: datetime,
        cursor: str | None,
        limit: int,
    ) -> list[dict]:
        """Fetch a page of cycles."""
        await self._ensure_token()
        endpoint = "/v1/cycle"
        params = {
            "start": int(start_date.timestamp() * 1000),
            "end": int(end_date.timestamp() * 1000),
            "limit": limit,
        }
        if cursor:
            params["cursor"] = cursor

        try:
            response = await self.fetch_with_retry("GET", endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("records", [])
        except Exception as e:
            logger.error("fetch_cycles_page_failed", error=str(e), cursor=cursor)
            return []

    async def fetch_recovery(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[PlayerBiometric]:
        """Fetch recovery data for a date range.

        Args:
            start_date: Start of the date range
            end_date: End of the date range

        Returns:
            List of PlayerBiometric records (HRV, RHR, recovery score)
        """
        cycles = await self.fetch_cycles(start_date, end_date)
        return self._map_recovery_data(cycles)

    async def fetch_strain(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[PlayerBiometric]:
        """Fetch strain/sleep data for a date range.

        Args:
            start_date: Start of the date range
            end_date: End of the date range

        Returns:
            List of PlayerBiometric records (sleep, strain)
        """
        cycles = await self.fetch_cycles(start_date, end_date)
        return self._map_strain_data(cycles)

    def _map_recovery_data(self, cycles: list[dict]) -> list[PlayerBiometric]:
        """Map WHOOP recovery data to PlayerBiometric schema."""
        biometrics = []

        for cycle in cycles:
            sleep = cycle.get("sleep", {})
            recovery = cycle.get("recovery", {})

            if not sleep and not recovery:
                continue

            cycle_id = cycle.get("id", "")
            player_uuid = self._get_player_uuid(cycle_id)

            timestamp = cycle.get("created_at")
            if timestamp:
                recorded_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            else:
                recorded_at = datetime.now(timezone.utc)

            hrv = recovery.get("hrv")
            if hrv is not None:
                biometrics.append(
                    PlayerBiometric(
                        player_id=player_uuid,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        metric_type="hrv",
                        value=hrv,
                        unit="ms",
                    )
                )

            resting_hr = recovery.get("resting_heart_rate")
            if resting_hr is not None:
                biometrics.append(
                    PlayerBiometric(
                        player_id=player_uuid,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        metric_type="resting_hr",
                        value=resting_hr,
                        unit="bpm",
                    )
                )

            recovery_score = recovery.get("score")
            if recovery_score is not None:
                biometrics.append(
                    PlayerBiometric(
                        player_id=player_uuid,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        metric_type="recovery_score",
                        value=recovery_score,
                        unit="percent",
                    )
                )

        return biometrics

    def _map_strain_data(self, cycles: list[dict]) -> list[PlayerBiometric]:
        """Map WHOOP strain/sleep data to PlayerBiometric schema."""
        biometrics = []

        for cycle in cycles:
            sleep = cycle.get("sleep", {})
            strain = cycle.get("strain", {})

            if not sleep and not strain:
                continue

            cycle_id = cycle.get("id", "")
            player_uuid = self._get_player_uuid(cycle_id)

            timestamp = cycle.get("created_at")
            if timestamp:
                recorded_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            else:
                recorded_at = datetime.now(timezone.utc)

            sleep_perf = sleep.get("performance")
            if sleep_perf is not None:
                biometrics.append(
                    PlayerBiometric(
                        player_id=player_uuid,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        metric_type="sleep_performance",
                        value=sleep_perf,
                        unit="percent",
                    )
                )

            sleep_duration = sleep.get("total_duration")
            if sleep_duration is not None:
                biometrics.append(
                    PlayerBiometric(
                        player_id=player_uuid,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        metric_type="sleep_duration",
                        value=sleep_duration / 3600,
                        unit="hours",
                    )
                )

            strain_score = strain.get("score")
            if strain_score is not None:
                biometrics.append(
                    PlayerBiometric(
                        player_id=player_uuid,
                        source=self.provider_name,
                        recorded_at=recorded_at,
                        metric_type="strain_score",
                        value=strain_score,
                        unit="au",
                    )
                )

        return biometrics

    def _get_player_uuid(self, external_id: str) -> str:
        """Convert external WHOOP ID to internal UUID.

        In production, this would look up from the players table.
        For now, generates a deterministic UUID from the external ID.
        """
        import uuid
        namespace = uuid.NAMESPACE_DNS
        return str(uuid.uuid5(namespace, f"whoop_{external_id}"))
