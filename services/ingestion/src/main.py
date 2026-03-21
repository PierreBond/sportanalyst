from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from sports_common.logging import setup_logging, get_logger
from sports_common.security import setup_security

from .health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down the ingestion service."""
    setup_logging("ingestion-service")
    logger = get_logger(__name__)
    logger.info("ingestion_service_starting")
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
    from sports_common.logging import get_logger

    logger = get_logger(__name__)
    logger.error("unhandled_exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "code": 500,
        },
    )


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint returning service status."""
    return {"service": "ingestion", "status": "running"}
