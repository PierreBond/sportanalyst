from fastapi import APIRouter

from sports_common.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/")
async def health_check():
    return {
        "status": "healthy",
        "service": "ingestion",
    }


@router.get("/ready")
async def readiness_check():
    return {
        "ready": True,
        "service": "ingestion",
    }


@router.get("/live")
async def liveness_check():
    return {
        "alive": True,
    }
