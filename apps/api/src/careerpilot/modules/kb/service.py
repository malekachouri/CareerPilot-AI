"""RAG pipeline: ingest (chunk + embed) and hybrid retrieval (full-text + vector, fused with RRF).

Retrieval never invents sources: every passage handed to a model carries its document's title, URL and
licence, and agents may only cite passages from this list (see coach/rag.py).
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.llm import Embedder, LLMUnavailableError, get_embedder
from careerpilot.modules.content.models import Question, QuestionVersion, question_categories
from careerpilot.modules.kb.models import KbChunk, KbDocument
from careerpilot.modules.taxonomy.models import Category

CHUNK_CHARS = 1200
RRF_K = 60


@dataclass(frozen=True)
class Passage:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    heading: str
    text: str
    url: str | None
    license_spdx: str | None
    attribution: str
    kind: str
    score: float

    def reference(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "heading": self.heading or None,
            "url": self.url,
            "license": self.license_spdx,
            "attribution": self.attribution or None,
            "kind": self.kind,
        }


def chunk_markdown(text: str, max_chars: int = CHUNK_CHARS) -> list[tuple[str, str]]:
    """Split on headings, then on paragraphs, keeping each chunk under `max_chars` with its heading."""
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in text.splitlines():
        m = re.match(r"^#{1,6}\s+(.*)", line)
        if m:
            sections.append((m.group(1).strip(), []))
        else:
            sections[-1][1].append(line)
    chunks: list[tuple[str, str]] = []
    for heading, lines in sections:
        body = "\n".join(lines).strip()
        if not body:
            continue
        current = ""
        for para in re.split(r"\n\s*\n", body):
            if current and len(current) + len(para) + 2 > max_chars:
                chunks.append((heading, current.strip()))
                current = ""
            current += para + "\n\n"
            while len(current) > max_chars:  # a single very long paragraph
                chunks.append((heading, current[:max_chars].strip()))
                current = current[max_chars:]
        if current.strip():
            chunks.append((heading, current.strip()))
    return chunks


async def index_document(
    db: AsyncSession,
    *,
    title: str,
    text: str,
    kind: str,
    url: str | None = None,
    license_spdx: str | None = None,
    attribution: str = "",
    categories: list[str] | None = None,
    owner_id: uuid.UUID | None = None,
    source_id: uuid.UUID | None = None,
    question_id: uuid.UUID | None = None,
    language: str = "en",
    embedder: Embedder | None = None,
) -> tuple[KbDocument, bool]:
    """Create or refresh a document. Returns (document, changed). Embeddings are optional."""
    digest = hashlib.sha256(f"{title}\n{text}".encode()).hexdigest()
    key = select(KbDocument).where(
        KbDocument.owner_id.is_(None) if owner_id is None else KbDocument.owner_id == owner_id
    )
    if question_id:
        existing = await db.scalar(key.where(KbDocument.question_id == question_id))
    elif url:
        existing = await db.scalar(key.where(KbDocument.url == url, KbDocument.kind == kind))
    else:
        existing = await db.scalar(key.where(KbDocument.title == title, KbDocument.kind == kind))
    if existing and existing.content_hash == digest:
        return existing, False
    doc = existing or KbDocument(kind=kind, owner_id=owner_id, source_id=source_id, question_id=question_id)
    doc.title, doc.url, doc.license_spdx, doc.attribution = title[:300], url, license_spdx, attribution
    doc.categories, doc.language, doc.content_hash = categories or [], language, digest
    if existing is None:
        db.add(doc)
    await db.flush()
    await db.execute(delete(KbChunk).where(KbChunk.document_id == doc.id))
    pieces = chunk_markdown(text)
    vectors: list[list[float] | None] = [None] * len(pieces)
    try:
        emb = embedder or get_embedder()
        vectors = list(await emb.embed([f"{title} — {h}\n{t}" for h, t in pieces]))
    except LLMUnavailableError:
        pass  # full-text search still works; `reindex` adds embeddings later
    for i, ((heading, chunk), vec) in enumerate(zip(pieces, vectors, strict=True)):
        db.add(KbChunk(document_id=doc.id, position=i, heading=heading, text=chunk, embedding=vec))
    await db.flush()
    return doc, True


async def embed_missing(db: AsyncSession, *, batch: int = 32, embedder: Embedder | None = None) -> int:
    emb = embedder or get_embedder()
    done = 0
    while True:
        rows = list(await db.scalars(select(KbChunk).where(KbChunk.embedding.is_(None)).limit(batch)))
        if not rows:
            break
        vectors = await emb.embed([r.text for r in rows])
        for r, v in zip(rows, vectors, strict=True):
            r.embedding = v
        done += len(rows)
        await db.commit()
    return done


def _visible(user_id: uuid.UUID | None) -> Any:
    return (
        KbDocument.owner_id.is_(None)
        if user_id is None
        else or_(KbDocument.owner_id.is_(None), KbDocument.owner_id == user_id)
    )


async def search(
    db: AsyncSession,
    query: str,
    *,
    user_id: uuid.UUID | None,
    k: int = 5,
    categories: list[str] | None = None,
    exclude_question_id: uuid.UUID | None = None,
    embedder: Embedder | None = None,
) -> list[Passage]:
    """Hybrid retrieval. Full-text always; vector similarity when embeddings are available. RRF fusion."""
    query = query.strip()[:2000]
    if not query:
        return []
    base = select(KbChunk.id).join(KbDocument, KbDocument.id == KbChunk.document_id).where(_visible(user_id))
    if (
        exclude_question_id
    ):  # never retrieve the question's own explanation as "evidence" before it is answered
        base = base.where(
            or_(KbDocument.question_id.is_(None), KbDocument.question_id != exclude_question_id)
        )
    if categories:
        base = base.where(
            or_(KbDocument.categories.overlap(categories), func.cardinality(KbDocument.categories) == 0)
        )

    words = [w for w in re.findall(r"[\w-]{3,}", query.lower())][:24]
    ranked: dict[uuid.UUID, float] = {}
    if words:
        tsq = func.to_tsquery(
            "simple", " | ".join(re.sub(r"[^\w]", "", w) for w in words if re.sub(r"[^\w]", "", w))
        )
        rank = func.ts_rank_cd(KbChunk.tsv, tsq)
        fts = list(await db.scalars(base.where(KbChunk.tsv.op("@@")(tsq)).order_by(rank.desc()).limit(20)))
        for i, cid in enumerate(fts):
            ranked[cid] = ranked.get(cid, 0.0) + 1.0 / (RRF_K + i + 1)
    try:
        emb = embedder or get_embedder()
        (qvec,) = await emb.embed([query])
        dist = KbChunk.embedding.cosine_distance(qvec)
        vec = list(await db.scalars(base.where(KbChunk.embedding.is_not(None)).order_by(dist).limit(20)))
        for i, cid in enumerate(vec):
            ranked[cid] = ranked.get(cid, 0.0) + 1.0 / (RRF_K + i + 1)
    except LLMUnavailableError:
        pass
    best = sorted(ranked.items(), key=lambda x: -x[1])[:k]
    if not best:
        return []
    rows = {
        c.id: (c, d)
        for c, d in (
            await db.execute(
                select(KbChunk, KbDocument)
                .join(KbDocument, KbDocument.id == KbChunk.document_id)
                .where(KbChunk.id.in_([b[0] for b in best]))
            )
        ).all()
    }
    out = []
    for cid, score in best:
        c, d = rows[cid]
        out.append(
            Passage(
                cid, d.id, d.title, c.heading, c.text, d.url, d.license_spdx, d.attribution, d.kind, score
            )
        )
    return out


# --- seeding -------------------------------------------------------------------------------------------


def _front_matter(text: str) -> tuple[dict[str, Any], str]:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end > 0:
            return yaml.safe_load(text[4:end]) or {}, text[end + 4 :].lstrip()
    return {}, text


async def seed_notes(db: AsyncSession, root: Path) -> int:
    """Curated notes in content/kb/*.md (front matter: title, url, license, attribution, categories)."""
    changed = 0
    for path in sorted((root / "kb").glob("*.md")):
        meta, body = _front_matter(path.read_text(encoding="utf-8"))
        _, did = await index_document(
            db,
            title=str(meta.get("title") or path.stem),
            text=body,
            kind="note",
            url=meta.get("url"),
            license_spdx=meta.get("license", "CC-BY-4.0"),
            attribution=meta.get("attribution", "CareerPilot AI contributors"),
            categories=list(meta.get("categories") or []),
        )
        changed += int(did)
    await db.commit()
    return changed


async def index_question_explanations(db: AsyncSession) -> int:
    """Published public questions with an explanation become knowledge-base passages (with their source)."""
    rows = await db.execute(
        select(Question, QuestionVersion)
        .join(QuestionVersion, QuestionVersion.id == Question.current_version_id)
        .where(
            Question.visibility == "public",
            Question.status == "published",
            QuestionVersion.explanation.is_not(None),
        )
    )
    cats: dict[uuid.UUID, list[str]] = {}
    for qid, slug in (
        await db.execute(
            select(question_categories.c.question_id, Category.slug).join(
                Category, Category.id == question_categories.c.category_id
            )
        )
    ).all():
        cats.setdefault(qid, []).append(slug)
    changed = 0
    for q, v in rows.all():
        key = {o["id"]: o["text"] for o in v.options}
        answer = "; ".join(key[a] for a in (v.answer_key or []) if a in key)
        text = (
            f"{v.stem}\n\nAnswer: {answer}\n\n{v.explanation}" if answer else f"{v.stem}\n\n{v.explanation}"
        )
        _, did = await index_document(
            db,
            title=f"Q: {v.stem[:120]}",
            text=text,
            kind="question",
            question_id=q.id,
            url=q.source_ref if (q.source_ref or "").startswith("http") else None,
            license_spdx=None,
            categories=cats.get(q.id, []),
        )
        changed += int(did)
    await db.commit()
    return changed
