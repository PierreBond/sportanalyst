from contextlib import asynccontextmanager

from fastapi import FastAPI

from sports_common.logging import setup_logging, get_logger

from .health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
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

app.include_router(health_router, prefix="/health", tags=["health"])


@app.get("/")
async def root():
    return {"service": "ingestion", "status": "running"}
