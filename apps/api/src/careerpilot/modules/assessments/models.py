"""Tests, test items, attempts and answers (owned by the `assessments` module)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, TimestampMixin, uuid7


class Test(TimestampMixin, Base):
    __tablename__ = "tests"
    __test__ = False  # not a pytest test class

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    slug: Mapped[str | None] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    visibility: Mapped[str] = mapped_column(String(16), default="public")  # public | private
    mode: Mapped[str] = mapped_column(String(16), default="exam")  # practice | exam
    time_limit_s: Mapped[int | None] = mapped_column(Integer)  # None = untimed
    shuffle: Mapped[bool] = mapped_column(default=False)
    kind: Mapped[str] = mapped_column(String(16), default="curated")  # curated | custom | generated | company
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    label: Mapped[str | None] = mapped_column(Text)
    generator_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(16), default="published")


class TestItem(Base):
    __tablename__ = "test_items"
    __test__ = False
    __table_args__ = (UniqueConstraint("test_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    points: Mapped[float] = mapped_column(Float, default=1.0)


class Attempt(TimestampMixin, Base):
    __tablename__ = "attempts"
    __table_args__ = (Index("ix_attempts_user_started", "user_id", "started_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"))
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="in_progress")  # in_progress | submitted
    started_at: Mapped[datetime]
    deadline_at: Mapped[datetime | None]
    submitted_at: Mapped[datetime | None] = mapped_column(default=None)
    score: Mapped[float | None] = mapped_column(Float, default=None)
    max_score: Mapped[float | None] = mapped_column(Float, default=None)
    auto_submitted: Mapped[bool] = mapped_column(default=False)


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    question_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("question_versions.id"))
    points: Mapped[float] = mapped_column(Float, default=1.0)
    selected: Mapped[list[str] | None] = mapped_column(JSONB, default=None)
    text_answer: Mapped[str | None] = mapped_column(Text, default=None)
    flagged: Mapped[bool] = mapped_column(default=False)
    time_spent_ms: Mapped[int] = mapped_column(Integer, default=0)
    answered_at: Mapped[datetime | None] = mapped_column(default=None)
    is_correct: Mapped[bool | None] = mapped_column(default=None)  # None = not auto-graded
    score: Mapped[float | None] = mapped_column(Float, default=None)
    graded_by: Mapped[str | None] = mapped_column(String(16), default=None)  # key | self | none
