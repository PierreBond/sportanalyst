from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import pandas as pd
from pydantic import BaseModel

from sports_common.logging import setup_logging, get_logger

setup_logging("model-serving")
logger = get_logger(__name__)


class PredictionRequest(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    features: dict[str, float]


class PredictionResponse(BaseModel):
    prediction_id: str
    match_id: str
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    predicted_home_score: float | None = None
    predicted_away_score: float | None = None
    confidence: str
    model_name: str
    generated_at: datetime


class BettingRequest(BaseModel):
    match_id: str
    model_probability: float
    odds: float
    kelly_fraction: float = 0.5


class BettingResponse(BaseModel):
    selection: str
    expected_value: float
    recommended_stake: float
    confidence: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("model_serving_starting")
    yield
    logger.info("model_serving_shutting_down")


app = FastAPI(
    title="Model Serving API",
    description="Sports prediction model serving",
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


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "model-serving"}


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    logger.info("prediction_request", match_id=request.match_id)

    home_win_prob = 0.45
    draw_prob = 0.25
    away_win_prob = 0.30

    max_prob = max(home_win_prob, draw_prob, away_win_prob)
    if max_prob >= 0.6:
        confidence = "high"
    elif max_prob >= 0.5:
        confidence = "medium"
    else:
        confidence = "low"

    return PredictionResponse(
        prediction_id=str(uuid4()),
        match_id=request.match_id,
        home_win_prob=home_win_prob,
        draw_prob=draw_prob,
        away_win_prob=away_win_prob,
        predicted_home_score=round(home_win_prob * 3, 1),
        predicted_away_score=round(away_win_prob * 2.5, 1),
        confidence=confidence,
        model_name="xgboost_match_outcome_v1",
        generated_at=datetime.now(timezone.utc),
    )


@app.post("/betting/calculate", response_model=BettingResponse)
async def calculate_betting(request: BettingRequest):
    implied_prob = 1.0 / request.odds
    expected_value = (request.odds * request.model_probability) - (1 - request.model_probability)

    b = request.odds - 1
    q = 1 - request.model_probability
    full_kelly = ((b * request.model_probability) - q) / b if b > 0 else 0
    recommended_stake = max(0, full_kelly * request.kelly_fraction)

    if expected_value > 0.05:
        confidence = "high"
    elif expected_value > 0:
        confidence = "medium"
    else:
        confidence = "low"

    return BettingResponse(
        selection="home" if request.model_probability > implied_prob else "away",
        expected_value=expected_value,
        recommended_stake=recommended_stake,
        confidence=confidence,
    )


@app.websocket("/ws/predictions")
async def websocket_predictions(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({
                "status": "live",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        logger.error("websocket_error", error=str(e))
        await websocket.close()


@app.get("/models")
async def list_models():
    return {
        "models": [
            {
                "name": "xgboost_match_outcome_v1",
                "version": "1.0.0",
                "stage": "production",
                "accuracy": 0.65,
                "brier_score": 0.18,
            },
            {
                "name": "poisson_match_outcome_v1",
                "version": "1.0.0",
                "stage": "staging",
                "accuracy": 0.58,
                "brier_score": 0.22,
            },
        ]
    }
