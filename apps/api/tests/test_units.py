from __future__ import annotations

import pytest

from careerpilot.core.config import Settings
from careerpilot.core.db import uuid7
from careerpilot.core.security import hash_password, verify_password
from careerpilot.worker import ping


def test_uuid7_is_version_7_and_time_ordered() -> None:
    ids = [uuid7() for _ in range(50)]
    assert all(u.version == 7 for u in ids)
    assert [u.int >> 80 for u in ids] == sorted(u.int >> 80 for u in ids)
    assert len(set(ids)) == 50
    # Strictly increasing, even within one millisecond: messages written in one transaction keep their order.
    many = [uuid7() for _ in range(2000)]
    assert many == sorted(many) and len(set(many)) == 2000
    assert all(u.version == 7 and u.variant == "specified in RFC 4122" for u in many)


def test_password_hash_roundtrip() -> None:
    h = hash_password("a-very-long-passphrase")
    assert verify_password(h, "a-very-long-passphrase")
    assert not verify_password(h, "wrong")
    assert not verify_password(None, "anything")
    assert not verify_password("not-a-hash", "anything")


def test_prod_settings_reject_insecure_defaults() -> None:
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(env="prod", cookie_secure=True)
    with pytest.raises(ValueError, match="COOKIE_SECURE"):
        Settings(env="prod", secret_key="x" * 40, cookie_secure=False)  # type: ignore[arg-type]
    assert Settings(env="prod", secret_key="x" * 40, cookie_secure=True).env == "prod"  # type: ignore[arg-type]


def test_celery_task_runs_eagerly() -> None:
    assert ping.apply().get() == "pong"
