from __future__ import annotations

import abc
from typing import AsyncIterator

import httpx

from sports_common.logging import get_logger

logger = get_logger(__name__)


class BaseAdapter(abc.ABC):
    """Abstract base for all external data-provider adapters."""

    provider_name: str = "base"

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = self._get_headers()
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=httpx.Timeout(connect=5.0, read=self._timeout),
            )
        return self._client

    def _get_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    async def __aenter__(self) -> "BaseAdapter":
        return self

    async def __aexit__(self, exc_type: any, exc_val: any, exc_tb: any) -> None:
        await self.close()

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Verify connectivity to the provider."""
        ...

    @abc.abstractmethod
    async def fetch_live_events(self, **kwargs: any) -> list[dict[str, any]]:
        """Fetch live events from the provider."""
        ...

    @abc.abstractmethod
    async def fetch_historical_matches(self, **kwargs: any) -> list[dict[str, any]]:
        """Fetch historical match data from the provider."""
        ...

    @abc.abstractmethod
    async def fetch_odds(self, **kwargs: any) -> list[dict[str, any]]:
        """Fetch odds data from the provider."""
        ...

    async def fetch_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs: any,
    ) -> httpx.Response:
        """Fetch with exponential backoff and jitter."""
        import asyncio
        import random

        last_exception: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = await self.client.request(method, url, **kwargs)
                if response.status_code == 200:
                    return response
                elif response.status_code in (429, 502, 503):
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        "api_request_failed",
                        provider=self.provider_name,
                        status=response.status_code,
                        attempt=attempt + 1,
                        wait_time=wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    response.raise_for_status()
            except httpx.TimeoutException as e:
                last_exception = e
                wait_time = (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    "api_timeout",
                    provider=self.provider_name,
                    attempt=attempt + 1,
                    wait_time=wait_time,
                )
                await asyncio.sleep(wait_time)
            except httpx.HTTPStatusError as e:
                last_exception = e
                wait_time = (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    "api_error",
                    provider=self.provider_name,
                    error=str(e),
                    attempt=attempt + 1,
                )
                await asyncio.sleep(wait_time)

        if last_exception:
            raise last_exception
        raise Exception("Max retries exceeded")
