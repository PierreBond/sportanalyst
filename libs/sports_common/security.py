from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


RATE_LIMIT_STORE: dict[str, list[float]] = {}

RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 60

CORS_ORIGINS = [
    "https://sports-prediction.example.com",
    "https://dashboard.sports-prediction.example.com",
]

AUTH_BYPASS_PATHS = frozenset(
    [
        "/health",
        "/health/",
        "/health/ready",
        "/health/live",
        "/docs",
        "/openapi.json",
        "/redoc",
    ]
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{request.url.path}"

        current_time = time.time()

        if key not in RATE_LIMIT_STORE:
            RATE_LIMIT_STORE[key] = []

        RATE_LIMIT_STORE[key] = [
            t for t in RATE_LIMIT_STORE[key] if current_time - t < RATE_LIMIT_WINDOW
        ]

        if len(RATE_LIMIT_STORE[key]) >= RATE_LIMIT_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds",
                    "code": 429,
                },
            )

        RATE_LIMIT_STORE[key].append(current_time)

        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in AUTH_BYPASS_PATHS or request.url.path.startswith("/health"):
            return await call_next(request)

        api_key = os.environ.get("API_KEY", "")
        provided_key = request.headers.get("X-API-Key", "")

        if not api_key:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service not configured",
                    "detail": "API_KEY environment variable is not set on this server",
                    "code": 503,
                },
            )

        if not provided_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "detail": "Missing X-API-Key header",
                    "code": 401,
                },
            )

        key_valid = hmac.compare_digest(provided_key, api_key) or hmac.compare_digest(
            hashlib.sha256(provided_key.encode()).hexdigest(),
            hashlib.sha256(api_key.encode()).hexdigest(),
        )

        if not key_valid:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "detail": "Invalid API key",
                    "code": 401,
                },
            )

        return await call_next(request)


def setup_security(app: FastAPI, require_auth: bool = True) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-API-Key"],
        max_age=600,
    )

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    if require_auth:
        app.add_middleware(ApiKeyMiddleware)
