from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel

from sports_common.logging import setup_logging, get_logger

setup_logging("biometric-service")
logger = get_logger(__name__)


class BiometricRequest(BaseModel):
    player_id: str
    player_load: float | None = None
    hrv: float | None = None
    resting_hr: float | None = None
    sleep_score: float | None = None


class ACWRResponse(BaseModel):
    player_id: str
    acwr: float
    is_danger_zone: bool
    computed_at: datetime


class WellnessResponse(BaseModel):
    player_id: str
    wellness_score: float
    hrv: float | None = None
    recovery_score: float | None = None
    status: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("biometric_service_starting")
    yield
    logger.info("biometric_service_shutting_down")


app = FastAPI(
    title="Biometric Integration Service",
    description="Player biometric data processing and injury risk",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "biometric"}


@app.post("/biometric/acwr", response_model=ACWRResponse)
async def calculate_acwr(player_id: str, acute_load: float = 400, chronic_load: float = 350):
    logger.info("calculating_acwr", player_id=player_id)

    acwr = acute_load / chronic_load if chronic_load > 0 else 0
    is_danger_zone = acwr >= 1.5

    return ACWRResponse(
        player_id=player_id,
        acwr=round(acwr, 4),
        is_danger_zone=is_danger_zone,
        computed_at=datetime.now(timezone.utc),
    )


@app.post("/biometric/wellness", response_model=WellnessResponse)
async def calculate_wellness(request: BiometricRequest):
    logger.info("calculating_wellness", player_id=request.player_id)

    scores = []
    if request.hrv:
        scores.append(min(request.hrv / 60, 1.0))
    if request.resting_hr:
        scores.append(max(0, 1 - (request.resting_hr - 45) / 30))
    if request.sleep_score:
        scores.append(request.sleep_score / 100)

    wellness_score = sum(scores) / len(scores) if scores else 0.5

    if wellness_score >= 0.7:
        status = "ready"
    elif wellness_score >= 0.4:
        status = "moderate"
    else:
        status = "fatigued"

    return WellnessResponse(
        player_id=request.player_id,
        wellness_score=round(wellness_score, 3),
        hrv=request.hrv,
        recovery_score=wellness_score * 100,
        status=status,
    )


@app.get("/biometric/team/{team_id}")
async def get_team_biometrics(team_id: str):
    return {
        "team_id": team_id,
        "players": [],
        "team_avg_acwr": 1.1,
        "team_avg_wellness": 0.75,
    }
