from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from careerpilot.core.config import get_settings
from careerpilot.core.errors import ProblemError
from careerpilot.core.llm import get_embedder, get_llm
from careerpilot.core.valkey import hit_rate_limit
from careerpilot.modules.auth.deps import CurrentUser, DbSession, require_role
from careerpilot.modules.coach import workflow as wf
from careerpilot.modules.coach.agents import AGENTS, PERSONAS
from careerpilot.modules.coach.models import CoachMessage, CoachSession
from careerpilot.modules.coach.ratings import get_profile, user_skills
from careerpilot.modules.kb import service as kb
from careerpilot.modules.kb.models import KbChunk, KbDocument
from careerpilot.modules.users.models import Role, User

router = APIRouter(prefix="/coach", tags=["coach"])
me = APIRouter(prefix="/me", tags=["coach"])
kb_router = APIRouter(tags=["knowledge-base"])

Admin = Annotated[User, Depends(require_role(Role.ADMIN))]


class StartPractice(BaseModel):
    agent: str
    learning_mode: bool = False
    question_id: uuid.UUID | None = None
    topic: str | None = Field(default=None, max_length=64)


class StartInterview(BaseModel):
    persona: str
    duration_minutes: int | None = Field(default=None, ge=10, le=90)


class AnswerIn(BaseModel):
    selected: list[str] | None = Field(default=None, max_length=12)
    text: str | None = Field(default=None, max_length=12000)
    language: str | None = Field(default=None, max_length=32)


class AskIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ProfileIn(BaseModel):
    target_role: str = Field(min_length=2, max_length=120)
    seniority: str = Field(pattern="^(junior|mid|senior)$")
    interview_minutes: int = Field(ge=10, le=90)
    focus_categories: list[str] = Field(default_factory=list, max_length=20)
    language: str = Field(default="en", pattern="^(en|fr)$")


class SessionSummary(BaseModel):
    id: uuid.UUID
    kind: str
    agent: str
    persona: str | None
    title: str
    status: str
    learning_mode: bool
    created_at: datetime
    updated_at: datetime
    overall_score: int | None


def _public_state(s: CoachSession) -> dict[str, Any]:
    """Never expose hidden material (reference answers, keys, interview scores before the report)."""
    cur = s.state.get("current") or {}
    iv = s.state.get("interview") or {}
    return {
        "step": s.state.get("step", "idle"),
        "pending": bool(s.state.get("pending")),
        "current": {
            "type": cur.get("type"),
            "message_id": cur.get("message_id"),
            "hints": cur.get("hints", 0),
            "topic": cur.get("topic"),
            "source": cur.get("source"),
        }
        if cur
        else None,
        "interview": {
            "main_asked": iv.get("main_asked"),
            "total": iv.get("total"),
            "awaiting_answer": bool(iv.get("current_question")) and not s.state.get("pending"),
        }
        if iv
        else None,
    }


def _message_out(m: CoachMessage) -> dict[str, Any]:
    data = {k: v for k, v in (m.data or {}).items() if k != "job"}
    return {
        "id": m.id,
        "role": m.role,
        "kind": m.kind,
        "content": m.content,
        "data": data,
        "status": m.status,
        "created_at": m.created_at,
    }


async def _session_out(db: DbSession, s: CoachSession) -> dict[str, Any]:
    # Background jobs commit from another session: reload instead of serving cached "pending" rows.
    await db.refresh(s)
    messages = await db.scalars(
        select(CoachMessage)
        .where(CoachMessage.session_id == s.id)
        .order_by(CoachMessage.created_at, CoachMessage.id)
        .execution_options(populate_existing=True)
    )
    agent = AGENTS[s.agent]
    return {
        "id": s.id,
        "kind": s.kind,
        "agent": {"slug": agent.slug, "name": agent.name, "disclaimer": agent.disclaimer},
        "persona": s.persona,
        "title": s.title,
        "status": s.status,
        "learning_mode": s.learning_mode,
        "state": _public_state(s),
        "report": s.report,
        "created_at": s.created_at,
        "messages": [_message_out(m) for m in messages],
    }


async def _limit(user: User) -> None:
    if await hit_rate_limit(f"rl:coach:{user.id}", 120, 3600):
        raise ProblemError(429, "Too many coach requests", "Try again later.")


@router.get("/agents")
async def list_agents(_: CurrentUser) -> dict[str, Any]:
    return {
        "agents": [
            {
                "slug": a.slug,
                "name": a.name,
                "description": a.description,
                "categories": list(a.categories),
                "criteria": [c.label for c in a.criteria],
                "answer_format": a.answer_format,
                "disclaimer": a.disclaimer,
            }
            for a in AGENTS.values()
        ],
        "interviews": [
            {"slug": p.slug, "name": p.name, "description": p.description, "agent": p.agent}
            for p in PERSONAS.values()
        ],
    }


@router.get("/status")
async def coach_status(_: CurrentUser) -> dict[str, Any]:
    llm, emb = get_llm(), get_embedder()
    return {
        "llm": {"provider": llm.name, "model": llm.model, "available": await llm.health()},
        "embeddings": {"provider": emb.name, "model": emb.model},
    }


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def start_practice(body: StartPractice, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    await _limit(user)
    s = await wf.start_practice(
        db,
        user.id,
        agent_slug=body.agent,
        learning_mode=body.learning_mode,
        question_id=body.question_id,
        topic=body.topic,
    )
    return await _session_out(db, await wf.get_session(db, user.id, s.id))


@router.post("/interviews", status_code=status.HTTP_201_CREATED)
async def start_interview(body: StartInterview, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    await _limit(user)
    s = await wf.start_interview(
        db, user.id, persona_slug=body.persona, duration_minutes=body.duration_minutes
    )
    return await _session_out(db, await wf.get_session(db, user.id, s.id))


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(
    db: DbSession, user: CurrentUser, limit: int = Query(30, ge=1, le=100)
) -> list[dict[str, Any]]:
    rows = await db.scalars(
        select(CoachSession)
        .where(CoachSession.user_id == user.id)
        .order_by(CoachSession.updated_at.desc())
        .limit(limit)
    )
    return [
        {
            **{
                k: getattr(s, k)
                for k in (
                    "id",
                    "kind",
                    "agent",
                    "persona",
                    "title",
                    "status",
                    "learning_mode",
                    "created_at",
                    "updated_at",
                )
            },
            "overall_score": (s.report or {}).get("overall_score"),
        }
        for s in rows
    ]


@router.get("/sessions/{session_id}")
async def get_session(session_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return await _session_out(db, await wf.get_session(db, user.id, session_id))


async def _act(db: DbSession, user: User, session_id: uuid.UUID) -> CoachSession:
    await _limit(user)
    return await wf.get_session(db, user.id, session_id)


@router.post("/sessions/{session_id}/answer")
async def answer(session_id: uuid.UUID, body: AnswerIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    s = await _act(db, user, session_id)
    await wf.submit_answer(db, s, selected=body.selected, text=body.text, language=body.language)
    return await _session_out(db, s)


@router.post("/sessions/{session_id}/next")
async def next_question(session_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    s = await _act(db, user, session_id)
    if s.kind != "practice" or s.status != "active":
        raise ProblemError(409, "Not available in this session")
    await wf.next_question(db, s)
    await wf.commit(db)
    return await _session_out(db, s)


@router.post("/sessions/{session_id}/reveal")
async def reveal(session_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    s = await _act(db, user, session_id)
    await wf.reveal(db, s)
    return await _session_out(db, s)


@router.post("/sessions/{session_id}/hint")
async def hint(session_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    s = await _act(db, user, session_id)
    await wf.request_hint(db, s)
    return await _session_out(db, s)


@router.post("/sessions/{session_id}/ask")
async def ask(session_id: uuid.UUID, body: AskIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    s = await _act(db, user, session_id)
    await wf.ask_tutor(db, s, body.message)
    return await _session_out(db, s)


@router.post("/sessions/{session_id}/similar")
async def similar(session_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    s = await _act(db, user, session_id)
    await wf.similar_exercise(db, s)
    return await _session_out(db, s)


@router.post("/sessions/{session_id}/end")
async def end(session_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    s = await _act(db, user, session_id)
    await wf.end_session(db, s)
    return await _session_out(db, s)


@router.post("/sessions/{session_id}/messages/{message_id}/retry")
async def retry(
    session_id: uuid.UUID, message_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    s = await _act(db, user, session_id)
    await wf.retry(db, s, message_id)
    return await _session_out(db, s)


# --- personalisation -------------------------------------------------------------------------------------


@me.get("/learning-profile")
async def get_learning_profile(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    p = await get_profile(db, user.id)
    await db.commit()
    return {
        k: getattr(p, k)
        for k in ("target_role", "seniority", "interview_minutes", "focus_categories", "language")
    }


@me.put("/learning-profile")
async def put_learning_profile(body: ProfileIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    p = await get_profile(db, user.id)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    await db.commit()
    return body.model_dump()


@me.get("/skills")
async def my_skills(db: DbSession, user: CurrentUser) -> list[dict[str, Any]]:
    return [s.__dict__ for s in await user_skills(db, user.id)]


# --- knowledge base --------------------------------------------------------------------------------------


@kb_router.get("/kb/search")
async def kb_search(
    db: DbSession,
    user: CurrentUser,
    q: str = Query(min_length=2, max_length=500),
    k: int = Query(5, ge=1, le=20),
) -> list[dict[str, Any]]:
    return [
        {**p.reference(), "text": p.text[:600], "score": round(p.score, 4)}
        for p in await kb.search(db, q, user_id=user.id, k=k)
    ]


@kb_router.post("/me/kb/upload", status_code=status.HTTP_201_CREATED)
async def upload_material(
    db: DbSession,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    title: str = Form("", max_length=300),
) -> dict[str, Any]:
    """Your own learning materials (Markdown, text or PDF): searchable by your coach only."""
    max_bytes = get_settings().import_max_file_bytes
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ProblemError(413, "File too large")
    name = re.sub(r"[^\w.\-]", "_", file.filename or "notes")[:120]
    if name.lower().endswith(".pdf"):
        import io

        from pypdf import PdfReader

        text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
    else:
        text = data.decode("utf-8", errors="replace")
    if not text.strip():
        raise ProblemError(422, "No text found in this file")
    doc, _ = await kb.index_document(db, title=title or name, text=text, kind="upload", owner_id=user.id)
    chunks = await db.scalar(select(func.count()).select_from(KbChunk).where(KbChunk.document_id == doc.id))
    await db.commit()
    return {"id": doc.id, "title": doc.title, "chunks": int(chunks or 0)}


@kb_router.get("/me/kb")
async def my_materials(db: DbSession, user: CurrentUser) -> list[dict[str, Any]]:
    rows = await db.scalars(
        select(KbDocument).where(KbDocument.owner_id == user.id).order_by(KbDocument.created_at.desc())
    )
    return [{"id": d.id, "title": d.title, "created_at": d.created_at} for d in rows]


@kb_router.delete("/me/kb/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(document_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    doc = await db.get(KbDocument, document_id)
    if doc is None or doc.owner_id != user.id:
        raise ProblemError(404, "Document not found")
    await db.delete(doc)
    await db.commit()


@kb_router.post("/admin/kb/reindex")
async def reindex(db: DbSession, _: Admin) -> dict[str, int]:
    """Re-index notes and question explanations, then add missing embeddings (if a model is available)."""
    from careerpilot.core.llm import LLMUnavailableError
    from careerpilot.modules.content.seed import content_root

    notes = await kb.seed_notes(db, content_root())
    questions = await kb.index_question_explanations(db)
    try:
        embedded = await kb.embed_missing(db)
    except LLMUnavailableError:
        embedded = 0
    return {"notes_changed": notes, "questions_changed": questions, "chunks_embedded": embedded}
