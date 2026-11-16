from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from careerpilot.modules.auth.deps import DbSession, require_role
from careerpilot.modules.auth.schemas import UserOut
from careerpilot.modules.users.models import Role, User
from careerpilot.modules.users.repository import list_users

router = APIRouter(prefix="/admin", tags=["admin"])

AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]


@router.get("/users", response_model=list[UserOut])
async def admin_list_users(
    _: AdminUser, db: DbSession, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)
) -> list[User]:
    return await list_users(db, limit=limit, offset=offset)
