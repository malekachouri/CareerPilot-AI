from __future__ import annotations

import httpx
from sqlalchemy import select

from careerpilot.core.db import SessionFactory
from careerpilot.modules.users.models import AuditLog, User
from tests.conftest import STRONG_PASSWORD, csrf, register


async def test_register_sets_session_and_returns_user(client: httpx.AsyncClient) -> None:
    r = await register(client, email="Ada@Example.org")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["email"] == "ada@example.org"  # normalised
    assert body["user"]["role"] == "learner"
    assert "password_hash" not in body["user"]
    assert client.cookies.get("cp_session")
    assert client.cookies.get("cp_csrf") == body["csrf_token"]
    set_cookie = ",".join(r.headers.get_list("set-cookie"))
    assert "HttpOnly" in set_cookie.split("cp_csrf")[0]  # session cookie is httpOnly
    assert "SameSite=lax" in set_cookie

    me = await client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.org"


async def test_password_is_hashed_with_argon2id(client: httpx.AsyncClient) -> None:
    await register(client)
    async with SessionFactory() as db:
        user = await db.scalar(select(User))
    assert user is not None
    assert user.password_hash.startswith("$argon2id$")
    assert STRONG_PASSWORD not in user.password_hash


async def test_duplicate_email_conflict(client: httpx.AsyncClient) -> None:
    await register(client)
    r = await register(client)
    assert r.status_code == 409
    assert r.headers["content-type"].startswith("application/problem+json")


async def test_weak_password_rejected(client: httpx.AsyncClient) -> None:
    r = await register(client, password="short")
    assert r.status_code == 422
    assert r.json()["type"].endswith("weak-password")


async def test_invalid_email_rejected(client: httpx.AsyncClient) -> None:
    r = await register(client, email="not-an-email")
    assert r.status_code == 422
    assert r.json()["title"] == "Validation error"


async def test_login_logout_flow(client: httpx.AsyncClient) -> None:
    await register(client)
    client.cookies.clear()
    assert (await client.get("/api/v1/me")).status_code == 401

    r = await client.post(
        "/api/v1/auth/login", json={"email": "ada@example.org", "password": STRONG_PASSWORD}
    )
    assert r.status_code == 200
    assert (await client.get("/api/v1/me")).status_code == 200

    r = await client.post("/api/v1/auth/logout", headers=csrf(client))
    assert r.status_code == 204
    client.cookies.clear()
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_logout_invalidates_session_server_side(client: httpx.AsyncClient) -> None:
    await register(client)
    stolen = client.cookies.get("cp_session")
    await client.post("/api/v1/auth/logout", headers=csrf(client))
    client.cookies.clear()
    client.cookies.set("cp_session", stolen or "")
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_wrong_password_and_unknown_email_look_identical(client: httpx.AsyncClient) -> None:
    await register(client)
    client.cookies.clear()
    a = await client.post(
        "/api/v1/auth/login", json={"email": "ada@example.org", "password": "wrong-password-1"}
    )
    b = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.org", "password": "whatever-123"}
    )
    assert a.status_code == b.status_code == 401
    assert a.json()["title"] == b.json()["title"]


async def test_login_rate_limited_per_email(client: httpx.AsyncClient) -> None:
    await register(client)
    client.cookies.clear()
    statuses = []
    for _ in range(11):
        r = await client.post(
            "/api/v1/auth/login", json={"email": "ada@example.org", "password": "bad-pass-123"}
        )
        statuses.append(r.status_code)
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    # Even the right password is refused while locked.
    r = await client.post(
        "/api/v1/auth/login", json={"email": "ada@example.org", "password": STRONG_PASSWORD}
    )
    assert r.status_code == 429
    assert "retry-after" in r.headers


async def test_csrf_required_for_state_changing_requests(client: httpx.AsyncClient) -> None:
    await register(client)
    r = await client.patch("/api/v1/me", json={"display_name": "Mallory"})
    assert r.status_code == 403
    assert r.json()["type"].endswith("csrf")
    r = await client.patch("/api/v1/me", json={"display_name": "Ada L."}, headers={"X-CSRF-Token": "forged"})
    assert r.status_code == 403
    r = await client.patch(
        "/api/v1/me", json={"display_name": "Ada L.", "locale": "fr"}, headers=csrf(client)
    )
    assert r.status_code == 200
    assert r.json()["display_name"] == "Ada L."
    assert r.json()["locale"] == "fr"


async def test_change_password_revokes_other_sessions(client: httpx.AsyncClient) -> None:
    from careerpilot.main import app

    await register(client)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as other:
        await other.post("/api/v1/auth/login", json={"email": "ada@example.org", "password": STRONG_PASSWORD})
        assert (await other.get("/api/v1/me")).status_code == 200

        new_password = "another-long-passphrase"
        r = await client.post(
            "/api/v1/me/password",
            headers=csrf(client),
            json={"current_password": STRONG_PASSWORD, "new_password": new_password},
        )
        assert r.status_code == 200
        assert (await client.get("/api/v1/me")).status_code == 200  # this browser got a fresh session
        assert (await other.get("/api/v1/me")).status_code == 401  # the other device is logged out

    client.cookies.clear()
    r = await client.post("/api/v1/auth/login", json={"email": "ada@example.org", "password": new_password})
    assert r.status_code == 200


async def test_login_replaces_existing_session_id(client: httpx.AsyncClient) -> None:
    await register(client)
    first = client.cookies.get("cp_session")
    await client.post("/api/v1/auth/login", json={"email": "ada@example.org", "password": STRONG_PASSWORD})
    second = client.cookies.get("cp_session")
    assert first and second and first != second


async def test_security_events_are_audited(client: httpx.AsyncClient) -> None:
    await register(client)
    client.cookies.clear()
    await client.post("/api/v1/auth/login", json={"email": "ada@example.org", "password": "bad-pass-123"})
    await client.post("/api/v1/auth/login", json={"email": "ada@example.org", "password": STRONG_PASSWORD})
    async with SessionFactory() as db:
        actions = [a.action for a in await db.scalars(select(AuditLog).order_by(AuditLog.created_at))]
        ip_hashes = [a.ip_hash for a in await db.scalars(select(AuditLog))]
    assert actions == ["user.register", "auth.login_failed", "auth.login"]
    assert all(h is None or len(h) == 64 for h in ip_hashes)  # IPs are stored as keyed hashes only


async def test_registration_can_be_closed(client: httpx.AsyncClient, monkeypatch: object) -> None:
    from careerpilot.core.config import get_settings

    settings = get_settings()
    original = settings.registration_open
    settings.registration_open = False
    try:
        r = await register(client)
        assert r.status_code == 403
    finally:
        settings.registration_open = original
