"""Taxonomy: career tracks, a category tree, and companies (owned by the `taxonomy` module)."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, TimestampMixin, uuid7

track_categories = Table(
    "track_categories",
    Base.metadata,
    Column("track_id", ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class Track(TimestampMixin, Base):
    """A career track (e.g. DevOps / Cloud / AI Engineer). New tracks are data, not code."""

    __tablename__ = "tracks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")


class Category(TimestampMixin, Base):
    """Two-level tree: groups (DevOps, Cloud, AI, …) and categories (Docker, AWS, RAG, …)."""

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Alternative spellings used by imported banks ("k8s", "github-actions", "aws-cloud", …).
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list, server_default="{}")


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    website: Mapped[str | None] = mapped_column(String(300))
    # Only links the company itself publishes (careers / interview-process pages).
    official_prep_links: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    description: Mapped[str] = mapped_column(Text, default="")
