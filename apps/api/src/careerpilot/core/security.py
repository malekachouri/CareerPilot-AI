"""Password hashing (Argon2id) and token helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from careerpilot.core.config import get_settings

_hasher = PasswordHasher()  # argon2id with library defaults (RFC 9106 recommended profile)

# Verified against when the user does not exist, so that response time does not reveal valid emails.
_DUMMY_HASH = _hasher.hash(secrets.token_hex(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def keyed_hash(value: str) -> str:
    """HMAC-SHA256 with the app secret. Used to store lookup keys (session ids, IPs) without the raw value."""
    key = get_settings().secret_key.get_secret_value().encode()
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()
