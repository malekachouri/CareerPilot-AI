"""Server-side sessions stored in Valkey.

The browser only holds an opaque random id (httpOnly cookie). Valkey stores the session under an HMAC of
that id, so a Valkey dump does not contain usable session cookies.
"""

from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import asdict, dataclass

from careerpilot.core.config import get_settings
from careerpilot.core.security import keyed_hash
from careerpilot.core.valkey import get_valkey


@dataclass(frozen=True)
class SessionData:
    user_id: str
    csrf_token: str

    @property
    def uid(self) -> uuid.UUID:
        return uuid.UUID(self.user_id)


def _key(session_id: str) -> str:
    return f"session:{keyed_hash(session_id)}"


def _user_index(user_id: str) -> str:
    return f"user_sessions:{user_id}"


async def create_session(user_id: uuid.UUID) -> tuple[str, SessionData]:
    ttl = get_settings().session_ttl_seconds
    session_id = secrets.token_urlsafe(32)
    data = SessionData(user_id=str(user_id), csrf_token=secrets.token_urlsafe(32))
    client = get_valkey()
    pipe = client.pipeline()
    pipe.set(_key(session_id), json.dumps(asdict(data)), ex=ttl)
    pipe.sadd(_user_index(data.user_id), _key(session_id))
    pipe.expire(_user_index(data.user_id), ttl)
    await pipe.execute()
    return session_id, data


async def load_session(session_id: str) -> SessionData | None:
    """Return the session and slide its expiry, or None if unknown/expired."""
    client = get_valkey()
    key = _key(session_id)
    raw = await client.get(key)
    if raw is None:
        return None
    await client.expire(key, get_settings().session_ttl_seconds)
    return SessionData(**json.loads(raw))


async def delete_session(session_id: str) -> None:
    client = get_valkey()
    key = _key(session_id)
    raw = await client.get(key)
    await client.delete(key)
    if raw is not None:
        await client.srem(_user_index(json.loads(raw)["user_id"]), key)


async def delete_all_sessions(user_id: uuid.UUID) -> None:
    client = get_valkey()
    index = _user_index(str(user_id))
    keys = await client.smembers(index)
    if keys:
        await client.delete(*keys)
    await client.delete(index)
