"""Integration test setup: real PostgreSQL (+pgvector) and Valkey.

Locally: `docker compose up -d postgres valkey`. In CI: service containers. A dedicated `<db>_test`
database and Valkey DB 15 are used and wiped, so development data is never touched.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pytest

_base_db = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://careerpilot:careerpilot@localhost:5432/careerpilot"
)
TEST_DB_URL = _base_db.rsplit("/", 1)[0] + "/careerpilot_test"
_valkey = os.environ.get("VALKEY_URL", "redis://localhost:6379/0")
os.environ.update(
    ENV="test",
    DATABASE_URL=TEST_DB_URL,
    VALKEY_URL=_valkey.rsplit("/", 1)[0] + "/15",
    LOG_JSON="false",
    LOG_LEVEL="WARNING",
    REGISTRATION_OPEN="true",
)

import httpx  # noqa: E402
from httpx import ASGITransport  # noqa: E402

API_DIR = Path(__file__).resolve().parents[1]


async def _recreate_database() -> None:
    dsn = TEST_DB_URL.replace("+asyncpg", "").rsplit("/", 1)[0] + "/postgres"
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("DROP DATABASE IF EXISTS careerpilot_test WITH (FORCE)")
        await conn.execute("CREATE DATABASE careerpilot_test")
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
async def _database() -> AsyncIterator[None]:
    await _recreate_database()
    # Run the real migrations: this also tests that they apply cleanly on an empty database.
    cmd = ["alembic", "upgrade", "head"]
    await asyncio.to_thread(subprocess.run, cmd, cwd=API_DIR, check=True, env=os.environ.copy())
    yield


@pytest.fixture(autouse=True)
async def _clean_state() -> AsyncIterator[None]:
    from sqlalchemy import text

    import careerpilot.models  # noqa: F401
    from careerpilot.core.db import Base, SessionFactory
    from careerpilot.core.jobs import set_dispatcher
    from careerpilot.core.llm import set_llm_override
    from careerpilot.core.valkey import get_valkey
    from careerpilot.tasks import TASKS

    await get_valkey().flushdb()
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with SessionFactory() as db:
        await db.execute(text(f"TRUNCATE {tables} CASCADE"))
        await db.commit()

    async def inline(name: str, kwargs: dict[str, object]) -> None:
        await TASKS[name](**kwargs)  # type: ignore[operator]

    set_dispatcher(inline)  # background jobs run in-process, deterministically
    yield
    set_dispatcher(None)
    set_llm_override(None)


@pytest.fixture
async def taxonomy() -> None:
    from careerpilot.core.db import SessionFactory
    from careerpilot.modules.taxonomy.seed import seed_taxonomy

    async with SessionFactory() as db:
        await seed_taxonomy(db)


@pytest.fixture
async def content(taxonomy: None) -> None:
    """Taxonomy + the repository's original questions and curated tests (content/)."""
    from careerpilot.core.db import SessionFactory
    from careerpilot.modules.content.seed import seed_content

    async with SessionFactory() as db:
        await seed_content(db)


async def login_as(client: httpx.AsyncClient, email: str, role: str = "learner") -> None:
    """Register (if needed) and log in; optionally promote the user."""
    from sqlalchemy import update

    from careerpilot.core.db import SessionFactory
    from careerpilot.modules.users.models import User

    client.cookies.clear()
    r = await register(client, email=email)
    if r.status_code == 409:
        r = await client.post("/api/v1/auth/login", json={"email": email, "password": STRONG_PASSWORD})
    assert r.status_code in (200, 201), r.text
    if role != "learner":
        async with SessionFactory() as db:
            await db.execute(update(User).where(User.email == email).values(role=role))
            await db.commit()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    from careerpilot.main import app

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


STRONG_PASSWORD = "correct-horse-battery-staple"


async def register(
    client: httpx.AsyncClient, email: str = "ada@example.org", password: str = STRONG_PASSWORD
) -> httpx.Response:
    return await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password, "display_name": "Ada"}
    )


def csrf(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("cp_csrf") or ""}
