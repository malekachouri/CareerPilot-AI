"""Valkey (Redis-protocol) client: sessions, rate limits, cache.

The `redis` Python client (MIT) speaks the protocol Valkey implements; no Redis server is required.
"""

from __future__ import annotations

from redis.asyncio import Redis

from careerpilot.core.config import get_settings

_client: Redis | None = None


def get_valkey() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(get_settings().valkey_url, decode_responses=True)
    return _client


async def close_valkey() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def hit_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """Fixed-window counter. Returns True when the caller is over the limit."""
    client = get_valkey()
    count = await client.incr(key)
    if count == 1:
        await client.expire(key, window_seconds)
    return int(count) > limit
