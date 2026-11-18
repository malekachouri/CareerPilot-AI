"""Knowledge base for RAG: documents (with licence and attribution) split into searchable chunks."""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base, uuid7

EMBEDDING_DIM = 768  # nomic-embed-text (Apache-2.0) via Ollama; see docs/06


class KbDocument(Base):
    __tablename__ = "kb_documents"
    __table_args__ = (Index("ix_kb_documents_hash_owner", "content_hash", "owner_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )  # None = shared
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    question_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))  # note | doc | question | upload
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(Text)
    license_spdx: Mapped[str | None] = mapped_column(String(64))
    attribution: Mapped[str] = mapped_column(Text, default="")
    categories: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list, server_default="{}")
    language: Mapped[str] = mapped_column(String(8), default="en")
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class KbChunk(Base):
    __tablename__ = "kb_chunks"
    __table_args__ = (
        Index("ix_kb_chunks_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_kb_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kb_documents.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text)
    tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', coalesce(heading, '') || ' ' || text)", persisted=True)
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), default=None)
