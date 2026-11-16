"""Authentication & authorization dependencies."""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import get_settings
from careerpilot.core.db import get_db
from careerpilot.core.errors import ProblemError
from careerpilot.modules.auth.sessions import SessionData, load_session
from careerpilot.modules.users.models import Role, User
from careerpilot.modules.users.repository import get_by_id

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _unauthorized() -> ProblemError:
    return ProblemError(401, "Not authenticated", code="https://careerpilot.dev/problems/unauthenticated")


@dataclass(frozen=True)
class AuthContext:
    user: User
    session_id: str
    session: SessionData


async def get_auth(request: Request, db: DbSession) -> AuthContext:
    settings = get_settings()
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        raise _unauthorized()
    session = await load_session(session_id)
    if session is None:
        raise _unauthorized()
    if request.method not in SAFE_METHODS:
        sent = request.headers.get(settings.csrf_header_name, "")
        if not secrets.compare_digest(sent, session.csrf_token):
            raise ProblemError(
                403, "CSRF token missing or invalid", code="https://careerpilot.dev/problems/csrf"
            )
    user = await get_by_id(db, session.uid)
    if user is None or not user.is_active:
        raise _unauthorized()
    return AuthContext(user=user, session_id=session_id, session=session)


Auth = Annotated[AuthContext, Depends(get_auth)]


async def get_current_user(auth: Auth) -> User:
    return auth.user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(minimum: Role) -> Callable[[User], Awaitable[User]]:
    async def _check(user: CurrentUser) -> User:
        if not user.role_enum.includes(minimum):
            raise ProblemError(
                403,
                "Insufficient role",
                f"Requires role '{minimum.value}' or higher",
                code="https://careerpilot.dev/problems/forbidden",
            )
        return user

    return _check
