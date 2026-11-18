"""Content: sources (with licence metadata), versioned questions and background jobs."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, String, Table, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, TimestampMixin, uuid7


class Provenance(enum.StrEnum):
    """Shown on every question (docs/11). Never claims a question is a real company test."""

    OFFICIAL_PUBLIC = "official_public"  # published by the organisation itself as practice material
    COMMUNITY_LICENSED = "community_licensed"  # open resource whose licence allows reuse
    ORIGINAL = "original"  # written for CareerPilot
    AI_GENERATED = "ai_generated"  # produced by the question generator; unverified until reviewed
    USER_CREATED = "user_created"  # written by a platform user
    PERSONAL_CAPTURE = "personal_capture"  # a user's private notes of a test they took (always private)


class QuestionType(enum.StrEnum):
    MCQ_SINGLE = "mcq_single"
    MCQ_MULTI = "mcq_multi"
    TRUE_FALSE = "true_false"
    TRUE_FALSE_UNDETERMINED = "true_false_undetermined"
    SCENARIO = "scenario"  # situation + options ("which action should you take?")
    SITUATIONAL = "situational"  # situational judgment: options, but often no single right answer
    OPEN_ENDED = "open_ended"
    CODING = "coding"
    DEBUGGING = "debugging"
    SURVEY = "survey"  # personality / profile questionnaire: never scored
    SIMULATION = "simulation"  # interactive step-by-step simulation (rendered by later phases)


# Types graded automatically against an answer key.
AUTO_GRADED_TYPES = frozenset(
    {
        QuestionType.MCQ_SINGLE,
        QuestionType.MCQ_MULTI,
        QuestionType.TRUE_FALSE,
        QuestionType.TRUE_FALSE_UNDETERMINED,
        QuestionType.SCENARIO,
    }
)
OPTION_TYPES = AUTO_GRADED_TYPES | {QuestionType.SITUATIONAL, QuestionType.SURVEY}


class Difficulty(enum.IntEnum):
    BEGINNER = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    EXPERT = 4


class SourceStatus(enum.StrEnum):
    APPROVED = "approved"  # content may be imported
    LINK_ONLY = "link_only"  # only the reference and link are stored (licence/terms do not allow copying)
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"


class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(32))  # github_repo | url | file | website | internal | llm
    url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    license_spdx: Mapped[str | None] = mapped_column(String(64))
    license_url: Mapped[str | None] = mapped_column(Text)
    attribution: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default=SourceStatus.PENDING_REVIEW.value)
    licence_decision: Mapped[str] = mapped_column(Text, default="")  # human-readable reason
    commercial_use_allowed: Mapped[bool | None] = mapped_column(default=None)
    derivatives_allowed: Mapped[bool | None] = mapped_column(default=None)
    share_alike: Mapped[bool] = mapped_column(default=False)
    default_provenance: Mapped[str] = mapped_column(String(32), default=Provenance.COMMUNITY_LICENSED.value)
    categories: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, server_default="{}")
    last_imported_at: Mapped[datetime | None] = mapped_column(default=None)


question_categories = Table(
    "question_categories",
    Base.metadata,
    Column("question_id", ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)

question_companies = Table(
    "question_companies",
    Base.metadata,
    Column("question_id", ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
    Column("company_id", ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True),
)


class Question(TimestampMixin, Base):
    """Identity, provenance and visibility. The content lives in versions (attempts keep the version used)."""

    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("provenance <> 'personal_capture' OR visibility = 'private'", name="capture_private"),
        CheckConstraint("visibility <> 'private' OR owner_id IS NOT NULL", name="private_has_owner"),
        Index("ix_questions_status_visibility", "status", "visibility"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    provenance: Mapped[str] = mapped_column(String(32))
    visibility: Mapped[str] = mapped_column(String(16), default="public")  # public | private
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    source_ref: Mapped[str | None] = mapped_column(Text)  # file path + line, commit SHA, page…
    external_id: Mapped[str | None] = mapped_column(String(200))  # stable id inside the source
    status: Mapped[str] = mapped_column(String(16), default="published")  # draft|in_review|published|retired
    verification: Mapped[str] = mapped_column(String(16), default="unverified")  # unverified | reviewed
    # Wording shown on company-related items, e.g. "Practice question inspired by publicly documented
    # recruitment topics". Never "official" unless provenance is official_public.
    label: Mapped[str | None] = mapped_column(Text)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_versions.id", use_alter=True, name="fk_questions_current_version")
    )


class QuestionVersion(Base):
    __tablename__ = "question_versions"
    __table_args__ = (
        Index("ix_question_versions_hash", "content_hash"),
        Index(
            "ix_question_versions_stem_trgm",
            "stem_normalized",
            postgresql_using="gin",
            postgresql_ops={"stem_normalized": "gin_trgm_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    type: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(8), default="en")
    stem: Mapped[str] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(Text)  # scenario text, code snippet, reading passage
    options: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list, server_default="[]")
    answer_key: Mapped[list[str] | None] = mapped_column(JSONB)  # option ids; None = no key known
    explanation: Mapped[str | None] = mapped_column(Text)
    distractor_explanations: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict, server_default="{}")
    difficulty: Mapped[int] = mapped_column(Integer, default=Difficulty.INTERMEDIATE)
    time_limit_s: Mapped[int | None] = mapped_column(Integer)
    stem_normalized: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class BackgroundJob(TimestampMixin, Base):
    """Progress record for long work run by the worker (imports, question generation)."""

    __tablename__ = "background_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    kind: Mapped[str] = mapped_column(String(32))  # import | generate
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|succeeded|failed
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
