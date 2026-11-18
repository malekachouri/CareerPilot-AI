"""Coach: per-topic skill ratings, learner profile, sessions, messages and cached AI explanations."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, TimestampMixin, uuid7


class SkillRating(Base):
    """Elo-style rating per user and category, updated by every graded answer (tests and coach)."""

    __tablename__ = "skill_ratings"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    )
    rating: Mapped[float] = mapped_column(Float, default=1000.0)
    answered: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[float] = mapped_column(Float, default=0.0)  # open answers count as fractions
    last_at: Mapped[datetime] = mapped_column(server_default=func.now())


class LearnerProfile(TimestampMixin, Base):
    __tablename__ = "learner_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    target_role: Mapped[str] = mapped_column(String(120), default="DevOps / Cloud / AI Engineer")
    seniority: Mapped[str] = mapped_column(String(16), default="mid")  # junior | mid | senior
    interview_minutes: Mapped[int] = mapped_column(Integer, default=30)
    focus_categories: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list, server_default="{}")
    language: Mapped[str] = mapped_column(String(8), default="en")


class CoachSession(TimestampMixin, Base):
    __tablename__ = "coach_sessions"
    __table_args__ = (Index("ix_coach_sessions_user_updated", "user_id", "updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))  # practice | interview
    agent: Mapped[str] = mapped_column(String(32))
    persona: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    learning_mode: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | ended
    # Workflow state: current question, step, interview plan and counters (see coach/workflow.py).
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    ended_at: Mapped[datetime | None] = mapped_column(default=None)


class CoachMessage(Base):
    __tablename__ = "coach_messages"
    __table_args__ = (Index("ix_coach_messages_session_created", "session_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coach_sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))  # coach | user
    # question | answer | evaluation | insight | recommendation | hint | chat | report | notice
    kind: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(16), default="done")  # pending | done | failed
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class CoachExplanation(Base):
    """AI enrichment of a question version (concepts, example, mistakes), cached: CPU models are slow."""

    __tablename__ = "coach_explanations"

    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="CASCADE"), primary_key=True
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
