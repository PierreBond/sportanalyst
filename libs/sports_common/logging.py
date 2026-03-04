from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from .config import settings


def setup_logging(service_name: str = "sports-common") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.INFO,
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    logger = structlog.get_logger()
    if name:
        logger = logger.bind(component=name)
    return logger


class CorrelationLogger:
    def __init__(self, logger: structlog.BoundLogger) -> None:
        self._logger = logger

    def bind(self, **kwargs: Any) -> CorrelationLogger:
        return CorrelationLogger(self._logger.bind(**kwargs))

    def debug(self, msg: str, **kwargs: Any) -> None:
        self._logger.debug(msg, **kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        self._logger.info(msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        self._logger.warning(msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        self._logger.error(msg, **kwargs)

    def critical(self, msg: str, **kwargs: Any) -> None:
        self._logger.critical(msg, **kwargs)

    def exception(self, msg: str, **kwargs: Any) -> None:
        self._logger.exception(msg, **kwargs)


def get_correlation_logger(service_name: str = "sports-common") -> CorrelationLogger:
    logger = structlog.get_logger()
    logger = logger.bind(service=service_name)
    return CorrelationLogger(logger)
