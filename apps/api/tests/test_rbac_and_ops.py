from __future__ import annotations

import httpx
from sqlalchemy import update

from careerpilot.core.db import SessionFactory
from careerpilot.modules.users.models import Role, User
from tests.conftest import register


async def _set_role(email: str, role: Role) -> None:
    async with SessionFactory() as db:
        await db.execute(update(User).where(User.email == email).values(role=role.value))
        await db.commit()


async def test_admin_endpoint_requires_admin(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/users")).status_code == 401
    await register(client)
    r = await client.get("/api/v1/admin/users")
    assert r.status_code == 403
    for role in (Role.CONTRIBUTOR, Role.REVIEWER):
        await _set_role("ada@example.org", role)
        assert (await client.get("/api/v1/admin/users")).status_code == 403
    await _set_role("ada@example.org", Role.ADMIN)
    r = await client.get("/api/v1/admin/users")
    assert r.status_code == 200
    assert [u["email"] for u in r.json()] == ["ada@example.org"]


def test_role_hierarchy() -> None:
    assert Role.ADMIN.includes(Role.REVIEWER)
    assert Role.REVIEWER.includes(Role.LEARNER)
    assert not Role.LEARNER.includes(Role.CONTRIBUTOR)


async def test_deactivated_user_loses_access(client: httpx.AsyncClient) -> None:
    await register(client)
    async with SessionFactory() as db:
        await db.execute(update(User).values(is_active=False))
        await db.commit()
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_health_and_readiness(client: httpx.AsyncClient) -> None:
    assert (await client.get("/healthz")).json() == {"status": "ok"}
    r = await client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["checks"] == {"database": "ok", "valkey": "ok"}


async def test_metrics_and_request_id(client: httpx.AsyncClient) -> None:
    r = await client.get("/healthz", headers={"X-Request-ID": "abc123"})
    assert r.headers["x-request-id"] == "abc123"
    metrics = (await client.get("/metrics")).text
    assert 'http_requests_total{method="GET",route="/healthz",status="200"}' in metrics


async def test_unknown_route_is_problem_json(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")


async def test_openapi_schema_available(client: httpx.AsyncClient) -> None:
    schema = (await client.get("/api/v1/openapi.json")).json()
    assert "/api/v1/auth/login" in schema["paths"]
