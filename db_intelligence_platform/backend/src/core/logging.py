"""Logging setup.

Replaces the ~30 ``print()`` calls in the old code. Every record carries the active
trace and span id, so a log line can be pivoted straight to its trace.
"""

import logging
import logging.config
from typing import Any

from opentelemetry import trace

_CONFIGURED = False


class TraceContextFilter(logging.Filter):
    """Attaches the current OTel trace/span id to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            record.trace_id = format(context.trace_id, "032x")
            record.span_id = format(context.span_id, "016x")
        else:
            record.trace_id = "-"
            record.span_id = "-"
        return True


def _config(level: str) -> dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"trace": {"()": TraceContextFilter}},
        "formatters": {
            "standard": {
                "format": (
                    "%(asctime)s %(levelname)-8s [%(name)s] "
                    "[trace=%(trace_id)s span=%(span_id)s] %(message)s"
                ),
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "filters": ["trace"],
                "stream": "ext://sys.stdout",
            },
        },
        "root": {"handlers": ["console"], "level": level},
        "loggers": {
            "uvicorn.access": {"handlers": ["console"], "level": level, "propagate": False},
            "httpx": {"level": "WARNING"},
            "neo4j": {"level": "WARNING"},
            "elastic_transport": {"level": "WARNING"},
        },
    }


def setup_logging(level: str = "INFO") -> None:
    """Idempotent -- safe to call from both ``create_app`` and a test fixture."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.config.dictConfig(_config(level))
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Preferred way to obtain a logger anywhere in the codebase."""
    return logging.getLogger(name)
