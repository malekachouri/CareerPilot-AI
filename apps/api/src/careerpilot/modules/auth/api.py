from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from careerpilot.core.config import get_settings
from careerpilot.core.errors import ProblemError
from careerpilot.core.security import keyed_hash
from careerpilot.core.valkey import hit_rate_limit
from careerpilot.modules.auth import service
from careerpilot.modules.auth.deps import Auth, CurrentUser, DbSession
from careerpilot.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    SessionOut,
    UpdateMeRequest,
    UserOut,
)
from careerpilot.modules.auth.sessions import create_session, delete_all_sessions, delete_session
from careerpilot.modules.users.models import User

router = APIRouter(tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _start_session(response: Response, user: User) -> SessionOut:
    settings = get_settings()
    session_id, data = await create_session(user.id)
    common = {
        "max_age": settings.session_ttl_seconds,
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie(settings.session_cookie_name, session_id, httponly=True, **common)  # type: ignore[arg-type]
    # Readable by the frontend so it can echo it in the X-CSRF-Token header.
    response.set_cookie(settings.csrf_cookie_name, data.csrf_token, httponly=False, **common)  # type: ignore[arg-type]
    return SessionOut(user=UserOut.model_validate(user), csrf_token=data.csrf_token)


def _clear_cookies(response: Response) -> None:
    settings = get_settings()
    for name in (settings.session_cookie_name, settings.csrf_cookie_name):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, samesite="lax")


@router.post("/auth/register", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request, response: Response, db: DbSession) -> SessionOut:
    settings = get_settings()
    if not settings.registration_open:
        raise ProblemError(
            403,
            "Registration is closed",
            "Ask the administrator for an account.",
            code="https://careerpilot.dev/problems/registration-closed",
        )
    ip = _client_ip(request)
    if await hit_rate_limit(f"rl:register:ip:{keyed_hash(ip or 'unknown')}", 10, 3600):
        raise ProblemError(
            429, "Too many registrations", code="https://careerpilot.dev/problems/rate-limited"
        )
    user = await service.register(
        db,
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        locale=body.locale,
        ip=ip,
    )
    return await _start_session(response, user)


@router.post("/auth/login", response_model=SessionOut)
async def login(body: LoginRequest, request: Request, response: Response, db: DbSession) -> SessionOut:
    user = await service.authenticate(db, email=body.email, password=body.password, ip=_client_ip(request))
    # Fixation protection: an existing session cookie is discarded and a brand-new id is issued.
    old = request.cookies.get(get_settings().session_cookie_name)
    if old:
        await delete_session(old)
    return await _start_session(response, user)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(auth: Auth, response: Response) -> Response:
    await delete_session(auth.session_id)
    _clear_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(body: UpdateMeRequest, user: CurrentUser, db: DbSession) -> User:
    if body.display_name is not None:
        user.display_name = body.display_name.strip()
    if body.locale is not None:
        user.locale = body.locale
    await db.commit()
    return user


@router.post("/me/password", response_model=SessionOut)
async def change_password(
    body: ChangePasswordRequest, auth: Auth, request: Request, response: Response, db: DbSession
) -> SessionOut:
    await service.change_password(
        db, auth.user, current=body.current_password, new=body.new_password, ip=_client_ip(request)
    )
    # Revoke every session (other devices too) and issue a fresh one for this browser.
    await delete_all_sessions(auth.user.id)
    return await _start_session(response, auth.user)
