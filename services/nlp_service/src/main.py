from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel

from sports_common.logging import setup_logging, get_logger

setup_logging("nlp-service")
logger = get_logger(__name__)


class SentimentRequest(BaseModel):
    text: str
    entity_id: str
    entity_type: str


class SentimentResponse(BaseModel):
    score: float
    label: str
    confidence: float


class ScrapedContent(BaseModel):
    text: str
    source: str
    author: str | None = None
    posted_at: datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("nlp_service_starting")
    yield
    logger.info("nlp_service_shutting_down")


app = FastAPI(
    title="NLP & Sentiment Service",
    description="Sentiment analysis and news processing",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "nlp"}


@app.post("/sentiment/analyze", response_model=SentimentResponse)
async def analyze_sentiment(request: SentimentRequest):
    logger.info("analyzing_sentiment", entity_id=request.entity_id)

    score = 0.0

    positive_words = ["win", "victory", "great", "excellent", "amazing", "strong", "best"]
    negative_words = ["loss", "defeat", "poor", "bad", "terrible", "weak", "worst"]

    text_lower = request.text.lower()

    for word in positive_words:
        if word in text_lower:
            score += 0.2

    for word in negative_words:
        if word in text_lower:
            score -= 0.2

    score = max(-1.0, min(1.0, score))

    if score > 0.3:
        label = "positive"
    elif score < -0.3:
        label = "negative"
    else:
        label = "neutral"

    confidence = abs(score) if score != 0 else 0.5

    return SentimentResponse(
        score=score,
        label=label,
        confidence=confidence,
    )


@app.post("/news/ingest")
async def ingest_news(content: ScrapedContent):
    logger.info("news_ingested", source=content.source)
    return {
        "status": "ingested",
        "text_length": len(content.text),
        "source": content.source,
    }
