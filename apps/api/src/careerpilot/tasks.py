"""Async bodies of background tasks. The Celery wrappers in `worker.py` run them on a fresh event loop."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from careerpilot.core.config import get_settings


@asynccontextmanager
async def task_session() -> AsyncIterator[AsyncSession]:
    """A session on a NullPool engine: each task runs in its own event loop, so pooled connections

    from another loop cannot be reused.
    """
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            yield session
    finally:
        await engine.dispose()


async def import_source(
    source_id: str, job_id: str, owner_id: str | None = None, publish: bool | None = None
) -> None:
    import careerpilot.models  # noqa: F401
    from careerpilot.modules.content.service import run_import

    async with task_session() as db:
        await run_import(
            db,
            uuid.UUID(source_id),
            job_id=uuid.UUID(job_id),
            owner_id=uuid.UUID(owner_id) if owner_id else None,
            publish=publish,
        )


async def generate_questions(request: dict[str, object], owner_id: str, job_id: str) -> None:
    import careerpilot.models  # noqa: F401
    from careerpilot.modules.generator.service import GenerateRequest, generate

    async with task_session() as db:
        await generate(
            db,
            GenerateRequest.model_validate(request),
            owner_id=uuid.UUID(owner_id),
            job_id=uuid.UUID(job_id),
        )


TASKS = {
    "content.import_source": import_source,
    "generator.generate": generate_questions,
}
