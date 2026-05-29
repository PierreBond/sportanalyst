from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from sports_common.config import get_settings
from sports_common.logging import setup_logging, get_logger
from sports_common.security import setup_security
from sports_common.league_config import get_league_config

from .health import router as health_router
from .ingestion_service.ingesting_processor import get_ingesting_processor


class IngestionConfig(BaseModel):
    """Configuration for ingestion processing."""

    batch_size: int = 100
    max_concurrent_leagues: int = 3
    max_concurrent_requests: int = 5
    league_timeout_seconds: int = 300
    max_retries: int = 3


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down the ingestion service."""
    setup_logging("ingestion-service")
    logger = get_logger(__name__)
    logger.info("ingestion_service_starting")

    settings = get_settings()
    league_config = get_league_config()
    processor = get_ingesting_processor()

    leagues_to_process = processor.get_leagues_to_process()
    logger.info(
        "configured_leagues",
        allowlist=list(settings.league_allowlist_set),
        blocklist=list(settings.league_blocklist_set),
        leagues_to_process=leagues_to_process,
    )

    yield
    logger.info("ingestion_service_shutting_down")


app = FastAPI(
    title="Data Ingestion Service",
    description="Sports data ingestion from external providers",
    version="0.1.0",
    lifespan=lifespan,
)

setup_security(app, require_auth=False)

app.include_router(health_router, prefix="/health", tags=["health"])


class LeagueStatusResponse(BaseModel):
    """Response for league status endpoint."""

    configured_leagues: list[str]
    leagues_to_process: list[str]
    allowlist: list[str]
    blocklist: list[str]


@app.get("/api/v1/ingestion/leagues/status")
async def get_league_status() -> LeagueStatusResponse:
    """Return current league configuration status."""
    settings = get_settings()
    processor = get_ingesting_processor()
    league_config = get_league_config()

    return LeagueStatusResponse(
        configured_leagues=league_config.get_discovered_league_ids(),
        leagues_to_process=processor.get_leagues_to_process(),
        allowlist=list(settings.league_allowlist_set),
        blocklist=list(settings.league_blocklist_set),
    )


@app.post("/api/v1/ingestion/run")
async def trigger_ingestion(
    leagues: list[str] | None = None,
    batch_size: int = Query(default=100, ge=10, le=500),
    max_concurrent_leagues: int = Query(default=3, ge=1, le=10),
    max_concurrent_requests: int = Query(default=5, ge=1, le=20),
    league_timeout_seconds: int = Query(default=300, ge=60, le=1800),
    max_retries: int = Query(default=3, ge=1, le=10),
) -> dict[str, Any]:
    """Trigger ingestion for specified leagues or all configured leagues.

    All parameters are optional and override the defaults.
    """
    logger = get_logger(__name__)
    processor = get_ingesting_processor(
        batch_size=batch_size,
        max_concurrent_leagues=max_concurrent_leagues,
        max_concurrent_requests=max_concurrent_requests,
        league_timeout_seconds=league_timeout_seconds,
        max_retries=max_retries,
    )

    if leagues:
        results = await processor.process_leagues(league_ids=leagues)
    else:
        results = await processor.process_leagues()

    return {
        "status": "completed",
        "leagues_processed": list(results.keys()),
        "results": results,
    }


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint returning service status."""
    return {"service": "ingestion", "status": "running"}
