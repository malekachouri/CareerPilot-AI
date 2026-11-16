from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from careerpilot.core.db import SessionFactory
from careerpilot.core.valkey import get_valkey

router = APIRouter(tags=["ops"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> JSONResponse:
    """Readiness: dependencies reachable. The LLM is optional and not checked here."""
    checks: dict[str, str] = {}
    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    try:
        await get_valkey().ping()
        checks["valkey"] = "ok"
    except Exception:
        checks["valkey"] = "error"
    ready = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "ok" if ready else "degraded", "checks": checks}, status_code=200 if ready else 503
    )
