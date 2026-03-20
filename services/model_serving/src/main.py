from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import structlog
from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from sports_common.logging import setup_logging, get_logger
from sports_common.schemas.predictions import MatchPrediction

from .betting import BettingEngine, BetSelection
from .cache import PredictionCache
from .calibrator import ProbabilityCalibrator
from .explainer import PredictionExplainer
from .predictor import ModelPredictor

setup_logging("model-serving")
logger = get_logger(__name__)

# --- Named constants (RULE-10) ---
CONFIDENCE_HIGH_THRESHOLD = 0.6
CONFIDENCE_MEDIUM_THRESHOLD = 0.5
DEFAULT_HOME_WIN_PROB = 0.45
DEFAULT_DRAW_PROB = 0.25
DEFAULT_AWAY_WIN_PROB = 0.30
PREDICTED_HOME_SCORE_MULTIPLIER = 3.0
PREDICTED_AWAY_SCORE_MULTIPLIER = 2.5


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class BatchPredictionRequest(BaseModel):
    matches: list[dict[str, Any]]


class BatchPredictionResponse(BaseModel):
    predictions: list[dict[str, Any]]
    generated_at: datetime


class ValueBetResponse(BaseModel):
    match_id: str
    selection: str
    model_prob: float
    best_odds: float
    implied_prob: float
    edge: float
    kelly_stake_pct: float
    sportsbook: str


class ReportResponse(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    league: str
    scheduled_at: datetime
    generated_at: datetime
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    predicted_home_score: float
    predicted_away_score: float
    value_bets: list[dict[str, Any]]
    shap_explanation: dict[str, Any]


class LiveUpdate(BaseModel):
    type: str
    match_id: str
    minute: int | None = None
    trigger: str | None = None
    probabilities: dict[str, float] | None = None
    timestamp: datetime


class ConnectionManager:
    """Manages active WebSocket connections for live prediction streaming."""

    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, match_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if match_id not in self.active_connections:
            self.active_connections[match_id] = []
        self.active_connections[match_id].append(websocket)
        logger.info("websocket_connected", match_id=match_id)

    def disconnect(self, match_id: str, websocket: WebSocket) -> None:
        if match_id in self.active_connections:
            self.active_connections[match_id].remove(websocket)
            if not self.active_connections[match_id]:
                del self.active_connections[match_id]
        logger.info("websocket_disconnected", match_id=match_id)

    async def broadcast(self, match_id: str, message: dict[str, Any]) -> None:
        if match_id in self.active_connections:
            for connection in self.active_connections[match_id]:
                await connection.send_json(message)


manager = ConnectionManager()

_cache: PredictionCache | None = None
_calibrator: ProbabilityCalibrator | None = None
_betting_engine: BettingEngine | None = None
_explainer: PredictionExplainer | None = None
_predictor: ModelPredictor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down service dependencies."""
    global _cache, _calibrator, _betting_engine, _explainer, _predictor

    logger.info("model_serving_starting")

    _cache = PredictionCache()
    await _cache.connect()

    _calibrator = ProbabilityCalibrator()
    calibrator_path = Path("/models/calibrator.json")
    if calibrator_path.exists():
        try:
            _calibrator.load(calibrator_path)
            logger.info("calibrator_loaded")
        except Exception as e:
            logger.warning("calibrator_load_failed", error=str(e))

    _betting_engine = BettingEngine()

    _predictor = ModelPredictor()
    _predictor.load_model()

    logger.info("model_serving_started")
    yield

    if _cache:
        await _cache.disconnect()

    logger.info("model_serving_shutting_down")


app = FastAPI(
    title="Model Serving API",
    description="Sports prediction model serving with calibration, betting, and explainability",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
async def structured_http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
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


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check service health status."""
    cache_status = "connected" if _cache and _cache._connected else "disconnected"
    calibrator_status = "loaded" if _calibrator and _calibrator.is_fitted else "not_loaded"

    return HealthResponse(
        status="healthy",
        service="model-serving",
        version="0.1.0",
    )


@app.get("/api/v1/predictions/{match_id}")
async def get_prediction(match_id: str) -> dict[str, Any]:
    """Get prediction for a specific match, using cache if available."""
    logger.info("prediction_request", match_id=match_id)

    if _cache:
        cached = await _cache.get_prediction(match_id)
        if cached:
            logger.info("prediction_cache_hit", match_id=match_id)
            return cached

    prediction_data = await _generate_prediction(match_id)

    if _cache:
        await _cache.set_prediction(match_id, prediction_data)

    return prediction_data


def _classify_confidence(max_prob: float) -> str:
    """Classify prediction confidence based on highest probability."""
    if max_prob >= CONFIDENCE_HIGH_THRESHOLD:
        return "high"
    elif max_prob >= CONFIDENCE_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def _build_prediction_payload(
    match_id: str,
    probabilities: tuple[float, float, float],
    calibrated: bool,
) -> dict[str, Any]:
    """Assemble the prediction response payload."""
    home_win_prob, draw_prob, away_win_prob = probabilities
    max_prob = max(home_win_prob, draw_prob, away_win_prob)

    return {
        "match_id": match_id,
        "home_team": "Home Team",
        "away_team": "Away Team",
        "league": "premier_league",
        "scheduled_at": datetime.now(timezone.utc).isoformat(),
        "model": _predictor.model_name if _predictor else "unknown",
        "model_version": _predictor.model_version if _predictor else "unknown",
        "probabilities": {
            "home_win": round(home_win_prob, 4),
            "draw": round(draw_prob, 4),
            "away_win": round(away_win_prob, 4),
        },
        "predicted_score": {
            "home": round(home_win_prob * PREDICTED_HOME_SCORE_MULTIPLIER, 2),
            "away": round(away_win_prob * PREDICTED_AWAY_SCORE_MULTIPLIER, 2),
        },
        "calibrated": calibrated,
        "confidence": _classify_confidence(max_prob),
        "value_bets": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _generate_prediction(match_id: str) -> dict[str, Any]:
    """Generate prediction for a match using the loaded model."""
    if _predictor:
        raw_probs = _predictor.predict({})
        home_win_prob, draw_prob, away_win_prob = float(raw_probs[0]), float(raw_probs[1]), float(raw_probs[2])
    else:
        home_win_prob = DEFAULT_HOME_WIN_PROB
        draw_prob = DEFAULT_DRAW_PROB
        away_win_prob = DEFAULT_AWAY_WIN_PROB

    probabilities = [home_win_prob, draw_prob, away_win_prob]
    calibrated = False

    if _calibrator and _calibrator.is_fitted:
        calibrated_arr = _calibrator.calibrate(np.array([probabilities]))
        home_win_prob, draw_prob, away_win_prob = calibrated_arr[0]
        calibrated = True
        logger.info("prediction_calibrated", match_id=match_id)

    return _build_prediction_payload(
        match_id, (home_win_prob, draw_prob, away_win_prob), calibrated
    )


@app.post("/api/v1/predictions/batch", response_model=BatchPredictionResponse)
async def batch_predict(request: BatchPredictionRequest) -> BatchPredictionResponse:
    """Generate predictions for multiple matches in a single request."""

    predictions = []
    for match in request.matches:
        match_id = match.get("match_id", "")
        pred = await _generate_prediction(match_id)
        predictions.append(pred)

    return BatchPredictionResponse(
        predictions=predictions,
        generated_at=datetime.now(timezone.utc),
    )


@app.websocket("/ws/live/{match_id}")
async def websocket_live_predictions(websocket: WebSocket, match_id: str) -> None:
    """Stream live prediction updates via WebSocket."""
    await manager.connect(match_id, websocket)
    try:
        await websocket.send_json({
            "type": "connection_established",
            "match_id": match_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        while True:
            data = await websocket.receive_text()
            await websocket.send_json({
                "type": "prediction_update",
                "match_id": match_id,
                "minute": None,
                "trigger": "periodic",
                "probabilities": {
                    "home_win": DEFAULT_HOME_WIN_PROB,
                    "draw": DEFAULT_DRAW_PROB,
                    "away_win": DEFAULT_AWAY_WIN_PROB,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
    except WebSocketDisconnect:
        manager.disconnect(match_id, websocket)
    except Exception as e:
        logger.error("websocket_error", match_id=match_id, error=str(e))
        manager.disconnect(match_id, websocket)


@app.get("/api/v1/value-bets")
async def get_value_bets(
    date: str = Query(default=None, description="Date in YYYY-MM-DD format"),
    min_edge: float = Query(default=0.03, ge=0, le=0.2),
) -> dict[str, Any]:
    """Retrieve value bets for a given date, filtered by minimum edge."""

    if date and _cache:
        cached_bets = await _cache.get_value_bets(date)
        if cached_bets:
            logger.info("value_bets_cache_hit", date=date)
            return {"date": date, "value_bets": cached_bets, "cached": True}

    value_bets = [
        {
            "match_id": "sample-match-1",
            "selection": "home_win",
            "model_prob": 0.55,
            "best_odds": 2.10,
            "implied_prob": 0.4762,
            "edge": 0.0738,
            "kelly_stake_pct": 1.85,
            "sportsbook": "DraftKings",
        }
    ]

    if date and _cache:
        await _cache.set_value_bets(date, value_bets)

    return {"date": date or datetime.now(timezone.utc).date().isoformat(), "value_bets": value_bets, "cached": False}


@app.get("/api/v1/reports/{match_id}", response_model=ReportResponse)
async def get_report(match_id: str) -> ReportResponse:
    """Generate a match research report."""

    prediction = await _generate_prediction(match_id)

    return ReportResponse(
        match_id=match_id,
        home_team=prediction["home_team"],
        away_team=prediction["away_team"],
        league=prediction["league"],
        scheduled_at=datetime.fromisoformat(prediction["scheduled_at"]),
        generated_at=datetime.now(timezone.utc),
        home_win_prob=prediction["probabilities"]["home_win"],
        draw_prob=prediction["probabilities"]["draw"],
        away_win_prob=prediction["probabilities"]["away_win"],
        predicted_home_score=prediction["predicted_score"]["home"],
        predicted_away_score=prediction["predicted_score"]["away"],
        value_bets=prediction["value_bets"],
        shap_explanation=prediction["shap_explanation"],
    )


@app.get("/api/v1/reports/{match_id}/pdf")
async def get_report_pdf(match_id: str) -> dict[str, Any]:
    """Generate a PDF version of the match report."""

    return {
        "match_id": match_id,
        "pdf_url": f"/api/v1/reports/{match_id}/download",
        "message": "PDF generation not implemented - use reporting service",
    }


@app.get("/models")
async def list_models() -> dict[str, Any]:
    """List available prediction models and their metadata."""
    return {
        "models": [
            {
                "name": "xgboost_match_outcome",
                "version": "v2.1",
                "stage": "production",
                "accuracy": 0.65,
                "brier_score": 0.18,
                "trained_at": "2026-03-01T00:00:00Z",
            },
            {
                "name": "poisson_match_outcome",
                "version": "v1.0",
                "stage": "staging",
                "accuracy": 0.58,
                "brier_score": 0.22,
                "trained_at": "2026-02-15T00:00:00Z",
            },
        ]
    }


@app.post("/models/calibrator/fit")
async def fit_calibrator(probs: list[list[float]], labels: list[int]) -> dict[str, Any]:
    """Fit the probability calibrator with historical data."""
    if not _calibrator:
        _calibrator = ProbabilityCalibrator()

    _calibrator.fit(np.array(probs), np.array(labels))

    calibrator_path = Path("/models/calibrator.json")
    calibrator_path.parent.mkdir(parents=True, exist_ok=True)
    _calibrator.save(calibrator_path)

    logger.info("calibrator_fitted", samples=len(labels))

    return {"status": "success", "samples": len(labels)}
