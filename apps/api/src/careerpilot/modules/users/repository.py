from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.security import keyed_hash
from careerpilot.modules.users.models import AuditLog, User


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email.strip().lower()))


async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def count_users(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(User)) or 0)


async def list_users(db: AsyncSession, *, limit: int, offset: int) -> list[User]:
    result = await db.scalars(select(User).order_by(User.created_at).limit(limit).offset(offset))
    return list(result)


def audit(
    db: AsyncSession,
    action: str,
    *,
    actor_id: uuid.UUID | None,
    ip: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_hash=keyed_hash(ip) if ip else None,
            metadata_=metadata or {},
        )
    )
