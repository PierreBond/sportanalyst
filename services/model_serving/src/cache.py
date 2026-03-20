from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import redis.asyncio as redis
from redis.asyncio import Redis

from sports_common.config import settings


class PredictionCache:
    """Redis-based cache for model predictions.

    Provides caching functionality for predictions with TTL support
    and invalidation capabilities.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        default_ttl: int = 300,
    ) -> None:
        """Initialize the prediction cache.

        Args:
            redis_url: Redis connection URL. Defaults to settings.REDIS_URL.
            default_ttl: Default time-to-live in seconds (default 5 minutes).
        """
        self._redis_url = redis_url or settings.REDIS_URL
        self._default_ttl = default_ttl
        self._client: Redis | None = None
        self._connected = False

    async def connect(self) -> None:
        """Establish connection to Redis."""
        if self._connected:
            return
        self._client = await redis.from_url(
            self._redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self._connected = True

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._connected = False

    async def _ensure_connected(self) -> None:
        """Ensure Redis is connected."""
        if not self._connected:
            await self.connect()

    def _prediction_key(self, match_id: str) -> str:
        """Generate cache key for a prediction.

        Args:
            match_id: Match identifier.

        Returns:
            Cache key string.
        """
        return f"prediction:match:{match_id}"

    def _value_bets_key(self, date: str) -> str:
        """Generate cache key for value bets.

        Args:
            date: Date string (YYYY-MM-DD).

        Returns:
            Cache key string.
        """
        return f"value_bets:date:{date}"

    async def get_prediction(self, match_id: str) -> dict[str, Any] | None:
        """Retrieve cached prediction for a match.

        Args:
            match_id: Match identifier.

        Returns:
            Cached prediction dict or None if not found.
        """
        await self._ensure_connected()
        key = self._prediction_key(match_id)
        data = await self._client.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_prediction(
        self,
        match_id: str,
        prediction: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """Cache a prediction.

        Args:
            match_id: Match identifier.
            prediction: Prediction data to cache.
            ttl: Time-to-live in seconds. Uses default if None.
        """
        await self._ensure_connected()
        key = self._prediction_key(match_id)
        ttl_value = ttl or self._default_ttl
        await self._client.setex(key, ttl_value, json.dumps(prediction))

    async def invalidate_prediction(self, match_id: str) -> None:
        """Invalidate cached prediction for a match.

        Args:
            match_id: Match identifier.
        """
        await self._ensure_connected()
        key = self._prediction_key(match_id)
        await self._client.delete(key)

    async def get_value_bets(self, date: str) -> list[dict[str, Any]] | None:
        """Retrieve cached value bets for a date.

        Args:
            date: Date string (YYYY-MM-DD).

        Returns:
            List of value bet dicts or None if not found.
        """
        await self._ensure_connected()
        key = self._value_bets_key(date)
        data = await self._client.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_value_bets(
        self,
        date: str,
        value_bets: list[dict[str, Any]],
        ttl: int | None = None,
    ) -> None:
        """Cache value bets for a date.

        Args:
            date: Date string (YYYY-MM-DD).
            value_bets: List of value bet dicts to cache.
            ttl: Time-to-live in seconds. Uses default if None.
        """
        await self._ensure_connected()
        key = self._value_bets_key(date)
        ttl_value = ttl or self._default_ttl
        await self._client.setex(key, ttl_value, json.dumps(value_bets))

    async def get_predictions_batch(
        self, match_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Retrieve multiple predictions at once.

        Args:
            match_ids: List of match identifiers.

        Returns:
            Dictionary mapping match_id to prediction (if cached).
        """
        await self._ensure_connected()
        pipeline = self._client.pipeline()
        keys = [self._prediction_key(mid) for mid in match_ids]

        for key in keys:
            pipeline.get(key)

        results = await pipeline.execute()
        predictions = {}
        for match_id, data in zip(match_ids, results):
            if data:
                predictions[match_id] = json.loads(data)

        return predictions

    async def warm_cache(
        self,
        predictions: dict[str, dict[str, Any]],
        ttl: int | None = None,
    ) -> None:
        """Warm cache with multiple predictions.

        Args:
            predictions: Dictionary mapping match_id to prediction data.
            ttl: Time-to-live in seconds. Uses default if None.
        """
        await self._ensure_connected()
        ttl_value = ttl or self._default_ttl
        pipeline = self._client.pipeline()

        for match_id, prediction in predictions.items():
            key = self._prediction_key(match_id)
            pipeline.setex(key, ttl_value, json.dumps(prediction))

        await pipeline.execute()

    async def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics.
        """
        await self._ensure_connected()
        info = await self._client.info("stats")
        memory_info = await self._client.info("memory")

        return {
            "total_connections": info.get("total_connections_received", 0),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
            "used_memory": memory_info.get("used_memory_human", "0"),
        }

    async def clear_expired(self) -> int:
        """Manually trigger cleanup of expired keys.

        Returns:
            Number of keys cleared.
        """
        await self._ensure_connected()
        result = await self._client.execute_command("MEMORY", "PURGE")
        return result if isinstance(result, int) else 0


class CacheManager:
    """Manager for multiple cache instances."""

    def __init__(self) -> None:
        self._caches: dict[str, PredictionCache] = {}

    def get_cache(self, name: str = "default", **kwargs) -> PredictionCache:
        """Get or create a named cache instance.

        Args:
            name: Cache instance name.
            **kwargs: Arguments passed to PredictionCache constructor.

        Returns:
            PredictionCache instance.
        """
        if name not in self._caches:
            self._caches[name] = PredictionCache(**kwargs)
        return self._caches[name]

    async def close_all(self) -> None:
        """Close all cache connections."""
        for cache in self._caches.values():
            await cache.disconnect()
