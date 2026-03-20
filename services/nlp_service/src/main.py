from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from sports_common.logging import setup_logging, get_logger

setup_logging("nlp-service")
logger = get_logger(__name__)

# --- Named constants (RULE-10) ---
POSITIVE_SENTIMENT_STEP = 0.2
NEGATIVE_SENTIMENT_STEP = 0.2
SENTIMENT_POSITIVE_THRESHOLD = 0.3
SENTIMENT_NEGATIVE_THRESHOLD = -0.3
SENTIMENT_MIN = -1.0
SENTIMENT_MAX = 1.0
DEFAULT_CONFIDENCE = 0.5


class SentimentRequest(BaseModel):
    """Request body for sentiment analysis."""

    text: str
    entity_id: str
    entity_type: str


class SentimentResponse(BaseModel):
    """Result of a sentiment analysis."""

    score: float
    label: str
    confidence: float


class ScrapedContent(BaseModel):
    """A scraped content item to ingest."""

    text: str
    source: str
    author: str | None = None
    posted_at: datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down the NLP service."""
    logger.info("nlp_service_starting")
    yield
    logger.info("nlp_service_shutting_down")


app = FastAPI(
    title="NLP & Sentiment Service",
    description="Sentiment analysis and news processing",
    version="0.1.0",
    lifespan=lifespan,
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


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Check NLP service health status."""
    return {"status": "healthy", "service": "nlp"}


@app.post("/sentiment/analyze", response_model=SentimentResponse)
async def analyze_sentiment(request: SentimentRequest) -> SentimentResponse:
    """Analyze sentiment of the provided text for a given entity."""
    logger.info("analyzing_sentiment", entity_id=request.entity_id)

    score = 0.0

    positive_words = ["win", "victory", "great", "excellent", "amazing", "strong", "best"]
    negative_words = ["loss", "defeat", "poor", "bad", "terrible", "weak", "worst"]

    text_lower = request.text.lower()

    for word in positive_words:
        if word in text_lower:
            score += POSITIVE_SENTIMENT_STEP

    for word in negative_words:
        if word in text_lower:
            score -= NEGATIVE_SENTIMENT_STEP

    score = max(SENTIMENT_MIN, min(SENTIMENT_MAX, score))

    if score > SENTIMENT_POSITIVE_THRESHOLD:
        label = "positive"
    elif score < SENTIMENT_NEGATIVE_THRESHOLD:
        label = "negative"
    else:
        label = "neutral"

    confidence = abs(score) if score != 0 else DEFAULT_CONFIDENCE

    return SentimentResponse(
        score=score,
        label=label,
        confidence=confidence,
    )


@app.post("/news/ingest")
async def ingest_news(content: ScrapedContent) -> dict[str, object]:
    """Ingest a scraped news article into the system."""
    logger.info("news_ingested", source=content.source)
    return {
        "status": "ingested",
        "text_length": len(content.text),
        "source": content.source,
    }
