"""User and audit-log tables (owned by the `users` module)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, TimestampMixin, uuid7


class Role(enum.StrEnum):
    """Roles are ordered: each role includes the permissions of the ones before it."""

    LEARNER = "learner"
    CONTRIBUTOR = "contributor"
    REVIEWER = "reviewer"
    ADMIN = "admin"

    @property
    def rank(self) -> int:
        return list(Role).index(self)

    def includes(self, other: Role) -> bool:
        return self.rank >= other.rank


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"role IN ({', '.join(repr(r.value) for r in Role)})", name="role_valid"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(
        String(20), default=Role.LEARNER.value, server_default=Role.LEARNER.value
    )
    locale: Mapped[str] = mapped_column(String(10), default="en", server_default="en")
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(default=None)

    @property
    def role_enum(self) -> Role:
        return Role(self.role)


class AuditLog(Base):
    """Append-only record of security-relevant actions."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_actor_created", "actor_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
