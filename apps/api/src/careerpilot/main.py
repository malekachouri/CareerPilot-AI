"""FastAPI application entrypoint: `uvicorn careerpilot.main:app`."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import careerpilot.models  # noqa: F401  (all ORM models registered before first use)
from careerpilot import __version__
from careerpilot.core.config import get_settings
from careerpilot.core.db import engine
from careerpilot.core.errors import install_error_handlers
from careerpilot.core.logging import RequestContextMiddleware, configure_logging
from careerpilot.core.metrics import MetricsMiddleware, metrics_endpoint
from careerpilot.core.valkey import close_valkey
from careerpilot.modules.admin.api import router as admin_router
from careerpilot.modules.assessments.api import router as tests_router
from careerpilot.modules.auth.api import router as auth_router
from careerpilot.modules.coach.api import kb_router
from careerpilot.modules.coach.api import me as coach_me_router
from careerpilot.modules.coach.api import router as coach_router
from careerpilot.modules.content.api import admin as content_admin_router
from careerpilot.modules.content.api import router as content_router
from careerpilot.modules.generator.api import router as generator_router
from careerpilot.modules.health.api import router as health_router
from careerpilot.modules.taxonomy.api import router as taxonomy_router

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await close_valkey()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs" if settings.env != "prod" else None,
        redoc_url=None,
    )
    install_error_handlers(app)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestContextMiddleware)
    if settings.cors_origins:
        # Not needed when the web app proxies /api (same origin). Only for separate-origin deployments.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Content-Type", settings.csrf_header_name],
        )

    app.include_router(health_router)
    app.include_router(auth_router, prefix=API_PREFIX)
    app.include_router(admin_router, prefix=API_PREFIX)
    app.include_router(taxonomy_router, prefix=API_PREFIX)
    app.include_router(content_router, prefix=API_PREFIX)
    app.include_router(content_admin_router, prefix=API_PREFIX)
    app.include_router(tests_router, prefix=API_PREFIX)
    app.include_router(generator_router, prefix=API_PREFIX)
    app.include_router(coach_router, prefix=API_PREFIX)
    app.include_router(coach_me_router, prefix=API_PREFIX)
    app.include_router(kb_router, prefix=API_PREFIX)
    app.add_api_route("/metrics", metrics_endpoint, include_in_schema=False)
    return app


app = create_app()
