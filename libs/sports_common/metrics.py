from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match


REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0],
)

ACTIVE_REQUESTS = Gauge(
    "http_requests_active",
    "Number of active HTTP requests",
)

PREDICTION_COUNT = Counter(
    "predictions_total",
    "Total predictions made",
    ["model", "outcome"],
)

PREDICTION_LATENCY = Histogram(
    "prediction_duration_seconds",
    "Prediction latency",
    ["model"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

KAFKA_MESSAGES_SENT = Counter(
    "kafka_messages_sent_total",
    "Total Kafka messages sent",
    ["topic", "status"],
)

KAFKA_MESSAGES_CONSUMED = Counter(
    "kafka_messages_consumed_total",
    "Total Kafka messages consumed",
    ["topic", "status"],
)

DATABASE_QUERY_DURATION = Histogram(
    "database_query_duration_seconds",
    "Database query duration",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

MODEL_INFERENCE_COUNT = Counter(
    "model_inference_total",
    "Total model inferences",
    ["model_name", "model_version"],
)

MODEL_INFERENCE_ERRORS = Counter(
    "model_inference_errors_total",
    "Total model inference errors",
    ["model_name", "error_type"],
)

CACHE_HITS = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["cache_name"],
)

CACHE_MISSES = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["cache_name"],
)

DATA_INGESTION_BYTES = Counter(
    "data_ingestion_bytes_total",
    "Total data ingested",
    ["source", "data_type"],
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        ACTIVE_REQUESTS.inc()
        method = request.method
        start_time = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - start_time
        status_code = response.status_code

        endpoint = request.url.path
        for route in request.app.routes:
            match, scope = route.matches(request.scope)
            if match == Match.FULL:
                endpoint = getattr(route, "path", request.url.path)
                break

        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
        ACTIVE_REQUESTS.dec()

        return response


def setup_metrics(app: FastAPI) -> None:
    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def track_prediction(model: str, outcome: str) -> None:
    PREDICTION_COUNT.labels(model=model, outcome=outcome).inc()


def track_prediction_latency(model: str, duration: float) -> None:
    PREDICTION_LATENCY.labels(model=model).observe(duration)


def track_kafka_sent(topic: str, success: bool) -> None:
    status = "success" if success else "error"
    KAFKA_MESSAGES_SENT.labels(topic=topic, status=status).inc()


def track_kafka_consumed(topic: str, success: bool) -> None:
    status = "success" if success else "error"
    KAFKA_MESSAGES_CONSUMED.labels(topic=topic, status=status).inc()


def track_database_query(operation: str, duration: float) -> None:
    DATABASE_QUERY_DURATION.labels(operation=operation).observe(duration)


def track_model_inference(model_name: str, model_version: str) -> None:
    MODEL_INFERENCE_COUNT.labels(model_name=model_name, model_version=model_version).inc()


def track_model_error(model_name: str, error_type: str) -> None:
    MODEL_INFERENCE_ERRORS.labels(model_name=model_name, error_type=error_type).inc()


def track_cache_hit(cache_name: str) -> None:
    CACHE_HITS.labels(cache_name=cache_name).inc()


def track_cache_miss(cache_name: str) -> None:
    CACHE_MISSES.labels(cache_name=cache_name).inc()


def track_data_ingestion(source: str, data_type: str, bytes_count: int) -> None:
    DATA_INGESTION_BYTES.labels(source=source, data_type=data_type).inc(bytes_count)
