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

    from careerpilot.core.db import SessionFactory
    from careerpilot.core.valkey import get_valkey

    await get_valkey().flushdb()
    async with SessionFactory() as db:
        await db.execute(text("TRUNCATE audit_log, users CASCADE"))
        await db.commit()
    yield


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
