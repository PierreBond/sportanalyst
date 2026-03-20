from __future__ import annotations

from fastapi import APIRouter

from sports_common.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/")
async def health_check() -> dict[str, str]:
    """Check ingestion service health status."""
    return {
        "status": "healthy",
        "service": "ingestion",
    }


@router.get("/ready")
async def readiness_check() -> dict[str, bool | str]:
    """Check if the ingestion service is ready to accept requests."""
    return {
        "ready": True,
        "service": "ingestion",
    }


@router.get("/live")
async def liveness_check() -> dict[str, bool]:
    """Check if the ingestion service is alive."""
    return {
        "alive": True,
    }
