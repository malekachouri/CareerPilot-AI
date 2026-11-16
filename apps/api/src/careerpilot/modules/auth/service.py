"""Auth use cases. No HTTP concerns here."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import get_settings
from careerpilot.core.db import utcnow
from careerpilot.core.errors import ProblemError
from careerpilot.core.security import hash_password, keyed_hash, password_needs_rehash, verify_password
from careerpilot.core.valkey import get_valkey, hit_rate_limit
from careerpilot.modules.users.models import Role, User
from careerpilot.modules.users.repository import audit, get_by_email

INVALID_CREDENTIALS = ProblemError(
    401, "Invalid email or password", code="https://careerpilot.dev/problems/invalid-credentials"
)


def validate_password_strength(password: str, *, email: str) -> None:
    settings = get_settings()
    problems = []
    if len(password) < settings.password_min_length:
        problems.append(f"at least {settings.password_min_length} characters")
    if password.lower() == email.lower() or password.lower() in email.lower():
        problems.append("must not contain your email")
    if len(set(password)) < 5:
        problems.append("too repetitive")
    if problems:
        raise ProblemError(
            422,
            "Password too weak",
            "Password: " + ", ".join(problems),
            code="https://careerpilot.dev/problems/weak-password",
        )


async def register(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str,
    locale: str,
    role: Role = Role.LEARNER,
    ip: str | None = None,
) -> User:
    email = email.strip().lower()
    validate_password_strength(password, email=email)
    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name.strip(),
        locale=locale,
        role=role.value,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        # Same message whether or not the email exists would be ideal, but registration must tell the
        # user something actionable; rate limiting on this endpoint limits enumeration.
        raise ProblemError(
            409, "Email already registered", code="https://careerpilot.dev/problems/email-taken"
        ) from None
    audit(db, "user.register", actor_id=user.id, ip=ip, entity_type="user", entity_id=str(user.id))
    await db.commit()
    return user


async def authenticate(db: AsyncSession, *, email: str, password: str, ip: str | None) -> User:
    settings = get_settings()
    email = email.strip().lower()
    email_key = f"rl:login:email:{keyed_hash(email)}"
    over_ip = await hit_rate_limit(
        f"rl:login:ip:{keyed_hash(ip or 'unknown')}",
        settings.login_max_attempts * 3,
        settings.login_window_seconds,
    )
    over_email = await hit_rate_limit(email_key, settings.login_max_attempts, settings.login_window_seconds)
    if over_ip or over_email:
        raise ProblemError(
            429,
            "Too many login attempts",
            "Try again later.",
            code="https://careerpilot.dev/problems/rate-limited",
            headers={"Retry-After": str(settings.login_window_seconds)},
        )
    user = await get_by_email(db, email)
    ok = verify_password(user.password_hash if user else None, password)
    if user is None or not ok or not user.is_active:
        audit(
            db,
            "auth.login_failed",
            actor_id=user.id if user else None,
            ip=ip,
            metadata={"reason": "inactive" if user and ok else "bad_credentials"},
        )
        await db.commit()
        raise INVALID_CREDENTIALS
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = utcnow()
    await get_valkey().delete(email_key)
    audit(db, "auth.login", actor_id=user.id, ip=ip)
    await db.commit()
    return user


async def change_password(db: AsyncSession, user: User, *, current: str, new: str, ip: str | None) -> None:
    if not verify_password(user.password_hash, current):
        raise INVALID_CREDENTIALS
    validate_password_strength(new, email=user.email)
    user.password_hash = hash_password(new)
    audit(db, "auth.password_changed", actor_id=user.id, ip=ip)
    await db.commit()
