from __future__ import annotations

from fastapi import APIRouter

from sports_common.logging import get_logger
from sports_common.config import settings

from .adapters import create_sports_data_adapter

logger = get_logger(__name__)

router = APIRouter()


def _resolve_active_provider() -> str:
    """Resolve active sports data provider from env-backed factory."""
    try:
        adapter = create_sports_data_adapter()
        return adapter.provider_name
    except Exception as e:
        logger.warning("resolve_active_provider_failed", error=str(e))
        return "unknown"


async def _check_active_provider_health() -> tuple[str, bool, str | None]:
    """Run connectivity check against the active sports data provider."""
    try:
        adapter = create_sports_data_adapter()
    except Exception as e:
        logger.warning("create_active_provider_failed", error=str(e))
        return ("unknown", False, str(e))

    provider = adapter.provider_name
    try:
        healthy = await adapter.health_check()
        return (provider, healthy, None)
    except Exception as e:
        logger.warning("active_provider_health_check_failed", provider=provider, error=str(e))
        return (provider, False, str(e))
    finally:
        await adapter.close()


@router.get("/")
async def health_check() -> dict[str, str]:
    """Check ingestion service health status."""
    return {
        "status": "healthy",
        "service": "ingestion",
        "provider": _resolve_active_provider(),
    }


@router.get("/ready")
async def readiness_check() -> dict[str, bool | str]:
    """Check if the ingestion service is ready to accept requests."""
    provider = _resolve_active_provider()
    return {
        "ready": provider != "unknown",
        "service": "ingestion",
        "provider": provider,
        "odds_source": settings.odds_source,
    }


@router.get("/live")
async def liveness_check() -> dict[str, bool]:
    """Check if the ingestion service is alive."""
    return {
        "alive": True,
    }


@router.get("/provider")
async def provider_health_check() -> dict[str, bool | str | None]:
    """Run a live connectivity check for the currently selected data provider."""
    provider, healthy, error = await _check_active_provider_health()
    return {
        "service": "ingestion",
        "provider": provider,
        "odds_source": settings.odds_source,
        "healthy": healthy,
        "error": error,
    }
