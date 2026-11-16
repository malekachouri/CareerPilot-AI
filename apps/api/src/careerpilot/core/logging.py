"""Structured logging (JSON in containers) and per-request context."""

from __future__ import annotations

import logging
import secrets
import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from careerpilot.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    level = logging.getLevelName(settings.log_level.upper())
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer() if settings.log_json else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
    )
    logging.basicConfig(level=level, format="%(message)s")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Adds a request id, binds it to logs and logs one access line per request (no bodies, no cookies)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or secrets.token_hex(8)
        request.state.request_id = request_id[:64]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request.state.request_id)
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        structlog.get_logger("access").info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - start) * 1000, 1),
        )
        return response
