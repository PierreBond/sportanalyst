from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from sports_common.logging import setup_logging, get_logger
from sports_common.schemas.biometrics import ACWR, WellnessScore
from sports_common.security import setup_security

setup_logging("biometric-service")
logger = get_logger(__name__)

# --- Named constants (RULE-10) ---
WELLNESS_HRV_BASELINE = 60
WELLNESS_RESTING_HR_LOW = 45
WELLNESS_RESTING_HR_RANGE = 30
WELLNESS_DEFAULT = 0.5
WELLNESS_READY_THRESHOLD = 0.7
WELLNESS_MODERATE_THRESHOLD = 0.4
ACWR_DANGER_ZONE_THRESHOLD = 1.5
DEFAULT_TEAM_AVG_ACWR = 1.1
DEFAULT_TEAM_AVG_WELLNESS = 0.75


class BiometricRequest(BaseModel):
    """Request body for biometric calculations."""

    player_id: str
    player_load: float | None = None
    hrv: float | None = None
    resting_hr: float | None = None
    sleep_score: float | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down the biometric service."""
    logger.info("biometric_service_starting")
    yield
    logger.info("biometric_service_shutting_down")


app = FastAPI(
    title="Biometric Integration Service",
    description="Player biometric data processing and injury risk",
    version="0.1.0",
    lifespan=lifespan,
)

setup_security(app)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Inject correlation_id into structlog context for every request (RULE-22)."""
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


@app.exception_handler(HTTPException)
async def structured_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return structured error JSON per RULE-19."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "detail": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "code": exc.status_code,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled errors, returning structured JSON."""
    logger.error("unhandled_exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "code": 500,
        },
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Check biometric service health status."""
    return {"status": "healthy", "service": "biometric"}


@app.post("/biometric/acwr", response_model=ACWR)
async def calculate_acwr(
    player_id: str, acute_load: float = 400, chronic_load: float = 350
) -> ACWR:
    """Calculate Acute:Chronic Workload Ratio for a player."""
    logger.info("calculating_acwr", player_id=player_id)

    acwr = acute_load / chronic_load if chronic_load > 0 else 0
    is_danger_zone = acwr >= ACWR_DANGER_ZONE_THRESHOLD

    return ACWR(
        player_id=player_id,
        acute_load=acute_load,
        chronic_load=chronic_load,
        ratio=round(acwr, 4),
        is_danger_zone=is_danger_zone,
        computed_at=datetime.now(timezone.utc),
    )


@app.post("/biometric/wellness", response_model=WellnessScore)
async def calculate_wellness(request: BiometricRequest) -> WellnessScore:
    """Calculate wellness score from biometric indicators."""
    logger.info("calculating_wellness", player_id=request.player_id)

    scores = []
    if request.hrv:
        scores.append(min(request.hrv / WELLNESS_HRV_BASELINE, 1.0))
    if request.resting_hr:
        scores.append(
            max(0, 1 - (request.resting_hr - WELLNESS_RESTING_HR_LOW) / WELLNESS_RESTING_HR_RANGE)
        )
    if request.sleep_score:
        scores.append(request.sleep_score / 100)

    wellness_score = sum(scores) / len(scores) if scores else WELLNESS_DEFAULT

    return WellnessScore(
        player_id=request.player_id,
        wellness_score=round(wellness_score, 3),
        hrv=request.hrv,
        resting_hr=request.resting_hr,
        sleep_score=request.sleep_score,
        recovery_score=wellness_score * 100,
        computed_at=datetime.now(timezone.utc),
    )


@app.get("/biometric/team/{team_id}")
async def get_team_biometrics(team_id: str) -> dict[str, object]:
    """Get aggregated biometric data for a team."""
    return {
        "team_id": team_id,
        "players": [],
        "team_avg_acwr": DEFAULT_TEAM_AVG_ACWR,
        "team_avg_wellness": DEFAULT_TEAM_AVG_WELLNESS,
    }
