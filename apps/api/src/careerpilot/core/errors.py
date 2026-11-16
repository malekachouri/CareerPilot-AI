"""RFC 9457 problem+json error model."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_MEDIA_TYPE = "application/problem+json"


class ProblemError(Exception):
    def __init__(
        self,
        status: int,
        title: str,
        detail: str | None = None,
        *,
        code: str = "about:blank",
        headers: dict[str, str] | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(detail or title)
        self.status = status
        self.title = title
        self.detail = detail
        self.code = code
        self.headers = headers
        self.errors = errors


def problem(
    status: int,
    title: str,
    detail: str | None = None,
    *,
    code: str = "about:blank",
    request: Request | None = None,
    errors: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {"type": code, "title": title, "status": status}
    if detail:
        body["detail"] = detail
    if request is not None:
        body["instance"] = request.url.path
        request_id = getattr(request.state, "request_id", None)
        if request_id:
            body["request_id"] = request_id
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=PROBLEM_MEDIA_TYPE, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def _problem(request: Request, exc: ProblemError) -> JSONResponse:
        return problem(
            exc.status,
            exc.title,
            exc.detail,
            code=exc.code,
            request=request,
            errors=exc.errors,
            headers=exc.headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(
            exc.status_code, str(exc.detail), request=request, headers=getattr(exc, "headers", None)
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()
        ]
        return problem(
            422,
            "Validation error",
            request=request,
            errors=errors,
            code="https://careerpilot.dev/problems/validation",
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        import structlog

        structlog.get_logger().exception("unhandled_error", path=request.url.path)
        return problem(500, "Internal server error", request=request)
