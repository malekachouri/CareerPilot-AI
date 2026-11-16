from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from careerpilot.core.db import utcnow
from careerpilot.core.errors import ProblemError
from careerpilot.modules.assessments import service
from careerpilot.modules.assessments.models import Attempt, Test
from careerpilot.modules.auth.deps import CurrentUser, DbSession
from careerpilot.modules.content.api import question_details, serialize_question
from careerpilot.modules.content.models import AUTO_GRADED_TYPES, QuestionType, Source
from careerpilot.modules.taxonomy.models import Company

router = APIRouter(tags=["tests"])


class TestOut(BaseModel):
    __test__ = False
    id: uuid.UUID
    slug: str | None
    title: str
    description: str
    kind: str
    mode: str
    visibility: str
    time_limit_s: int | None
    label: str | None
    company: dict[str, str] | None
    is_mine: bool
    question_count: int
    categories: list[dict[str, str]]
    average_difficulty: float | None
    provenance: list[str]
    types: list[str]


class CustomTestIn(BaseModel):
    title: str = Field(default="My custom test", min_length=2, max_length=200)
    categories: list[str] = Field(default_factory=list, max_length=30)
    difficulties: list[int] = Field(default_factory=list)
    types: list[QuestionType] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)
    company: str | None = None
    count: int = Field(default=10, ge=1, le=100)
    time_limit_minutes: int | None = Field(default=None, ge=1, le=300)
    mode: str = Field(default="exam", pattern="^(exam|practice)$")
    require_key: bool = True


class AnswerIn(BaseModel):
    selected: list[str] | None = Field(default=None, max_length=12)
    text_answer: str | None = Field(default=None, max_length=20000)
    flagged: bool | None = None
    time_spent_ms: int = Field(default=0, ge=0, le=3_600_000)


class SelfGradeIn(BaseModel):
    correct: bool


async def _tests_out(db: DbSession, user_id: uuid.UUID, tests: list[Test]) -> list[dict[str, Any]]:
    summaries = await service.test_summaries(db, tests)
    company_ids = {t.company_id for t in tests if t.company_id}
    companies = (
        {c.id: c for c in await db.scalars(select(Company).where(Company.id.in_(company_ids)))}
        if company_ids
        else {}
    )
    out = []
    for t in tests:
        c = companies.get(t.company_id) if t.company_id else None
        out.append(
            {
                "id": t.id,
                "slug": t.slug,
                "title": t.title,
                "description": t.description,
                "kind": t.kind,
                "mode": t.mode,
                "visibility": t.visibility,
                "time_limit_s": t.time_limit_s,
                "label": t.label,
                "company": {"slug": c.slug, "name": c.name} if c else None,
                "is_mine": t.owner_id == user_id,
                **summaries[t.id],
            }
        )
    return out


@router.get("/tests", response_model=list[TestOut])
async def list_tests(
    db: DbSession,
    user: CurrentUser,
    q: str | None = Query(None, max_length=200),
    category: str | None = None,
    difficulty: int | None = Query(None, ge=1, le=4),
    kind: str | None = None,
    company: str | None = None,
    mine: bool = False,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[dict[str, Any]]:
    tests = await service.list_tests(
        db,
        user.id,
        q=q,
        category=category,
        difficulty=difficulty,
        kind=kind,
        company=company,
        mine=mine,
        limit=limit,
        offset=offset,
    )
    return await _tests_out(db, user.id, tests)


@router.get("/tests/{test_id}", response_model=TestOut)
async def get_test(test_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return (await _tests_out(db, user.id, [await service.get_test(db, user.id, test_id)]))[0]


@router.post("/tests/custom", response_model=TestOut, status_code=status.HTTP_201_CREATED)
async def create_custom_test(body: CustomTestIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    test = await service.build_custom_test(
        db,
        user.id,
        title=body.title,
        categories=body.categories,
        difficulties=body.difficulties,
        types=[t.value for t in body.types],
        provenance=body.provenance,
        company=body.company,
        count=body.count,
        time_limit_minutes=body.time_limit_minutes,
        mode=body.mode,
        require_key=body.require_key,
    )
    return (await _tests_out(db, user.id, [test]))[0]


@router.delete("/tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test(test_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    test = await db.get(Test, test_id)
    if test is None or test.owner_id != user.id:
        raise service.not_found("Test")
    await db.delete(test)
    await db.commit()


# --- attempts ------------------------------------------------------------------------------------------


async def _attempt_state(db: DbSession, attempt: Attempt) -> dict[str, Any]:
    """The player view: questions without answer keys, saved answers and server-side timing."""
    test = await db.get(Test, attempt.test_id)
    rows = await service.attempt_rows(db, attempt)
    details = await question_details(db, [q.id for _, _, q in rows])
    sources = {
        s.id: s
        for s in await db.scalars(
            select(Source).where(Source.id.in_({q.source_id for _, _, q in rows if q.source_id}))
        )
    }
    now = utcnow()
    return {
        "id": attempt.id,
        "status": attempt.status,
        "mode": attempt.mode,
        "test": {"id": test.id, "title": test.title, "time_limit_s": test.time_limit_s} if test else None,
        "started_at": attempt.started_at,
        "deadline_at": attempt.deadline_at,
        "server_time": now,
        "remaining_seconds": max(0, int((attempt.deadline_at - now).total_seconds()))
        if attempt.deadline_at
        else None,
        "questions": [
            {
                "position": a.position,
                "points": a.points,
                "selected": a.selected,
                "text_answer": a.text_answer,
                "flagged": a.flagged,
                "answered": a.selected is not None or bool(a.text_answer),
                "question": serialize_question(
                    q, v, details[q.id], sources.get(q.source_id) if q.source_id else None
                ),
                "auto_graded": QuestionType(v.type) in AUTO_GRADED_TYPES and bool(v.answer_key),
            }
            for a, v, q in rows
        ],
    }


@router.post("/tests/{test_id}/attempts", status_code=status.HTTP_201_CREATED)
async def start_attempt(test_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    attempt = await service.start_attempt(db, user.id, test_id)
    return await _attempt_state(db, attempt)


@router.get("/attempts/{attempt_id}")
async def get_attempt(attempt_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return await _attempt_state(db, await service.get_attempt(db, user.id, attempt_id))


@router.put("/attempts/{attempt_id}/answers/{position}")
async def save_answer(
    attempt_id: uuid.UUID, position: int, body: AnswerIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    a = await service.save_answer(
        db,
        user.id,
        attempt_id,
        position,
        selected=body.selected,
        text_answer=body.text_answer,
        flagged=body.flagged,
        time_spent_ms=body.time_spent_ms,
    )
    return {"position": a.position, "selected": a.selected, "flagged": a.flagged, "saved_at": a.answered_at}


@router.post("/attempts/{attempt_id}/submit")
async def submit(attempt_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    attempt = await service.get_attempt(db, user.id, attempt_id)
    await service.submit_attempt(db, attempt)
    return await results(attempt_id, db, user)


@router.get("/attempts/{attempt_id}/results")
async def results(attempt_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    """Score, breakdowns and, per question, the key and explanations (only after submission)."""
    attempt = await service.get_attempt(db, user.id, attempt_id)
    if attempt.status != "submitted":
        raise ProblemError(
            409,
            "Results are available after submission",
            code="https://careerpilot.dev/problems/attempt-open",
        )
    test = await db.get(Test, attempt.test_id)
    rows = await service.attempt_rows(db, attempt)
    details = await question_details(db, [q.id for _, _, q in rows])
    sources = {
        s.id: s
        for s in await db.scalars(
            select(Source).where(Source.id.in_({q.source_id for _, _, q in rows if q.source_id}))
        )
    }
    by_cat: dict[str, dict[str, Any]] = {}
    by_diff: dict[int, dict[str, int]] = {}
    items: list[dict[str, Any]] = []
    for a, v, q in rows:
        if a.is_correct is not None:
            for c in details[q.id]["categories"]:
                e = by_cat.setdefault(
                    c["slug"], {"slug": c["slug"], "name": c["name"], "answered": 0, "correct": 0}
                )
                e["answered"] += 1
                e["correct"] += int(a.is_correct)
            d = by_diff.setdefault(v.difficulty, {"difficulty": v.difficulty, "answered": 0, "correct": 0})
            d["answered"] += 1
            d["correct"] += int(a.is_correct)
        items.append(
            {
                "position": a.position,
                "selected": a.selected,
                "text_answer": a.text_answer,
                "flagged": a.flagged,
                "is_correct": a.is_correct,
                "score": a.score,
                "points": a.points,
                "graded_by": a.graded_by,
                "time_spent_ms": a.time_spent_ms,
                "question": serialize_question(
                    q, v, details[q.id], sources.get(q.source_id) if q.source_id else None, with_key=True
                ),
            }
        )
    graded = [i for i in items if i["is_correct"] is not None]
    timed = [i["time_spent_ms"] for i in items if i["time_spent_ms"] > 0]
    return {
        "id": attempt.id,
        "status": attempt.status,
        "test": {"id": test.id, "title": test.title} if test else None,
        "started_at": attempt.started_at,
        "submitted_at": attempt.submitted_at,
        "auto_submitted": attempt.auto_submitted,
        "score": attempt.score,
        "max_score": attempt.max_score,
        "percent": round(100 * (attempt.score or 0) / attempt.max_score, 1) if attempt.max_score else None,
        "correct": sum(1 for i in graded if i["is_correct"]),
        "incorrect": sum(1 for i in graded if not i["is_correct"]),
        "ungraded": len(items) - len(graded),
        "unanswered": sum(1 for i in items if not i["selected"] and not i["text_answer"]),
        "average_time_ms": int(sum(timed) / len(timed)) if timed else None,
        "duration_s": int((attempt.submitted_at - attempt.started_at).total_seconds())
        if attempt.submitted_at
        else None,
        "by_category": sorted(
            ({**c, "accuracy": round(c["correct"] / c["answered"], 3)} for c in by_cat.values()),
            key=lambda c: c["accuracy"],
        ),
        "by_difficulty": sorted(
            ({**d, "accuracy": round(d["correct"] / d["answered"], 3)} for d in by_diff.values()),
            key=lambda d: d["difficulty"],
        ),
        "items": items,
    }


@router.post("/attempts/{attempt_id}/answers/{position}/self-grade", status_code=status.HTTP_204_NO_CONTENT)
async def self_grade(
    attempt_id: uuid.UUID, position: int, body: SelfGradeIn, db: DbSession, user: CurrentUser
) -> None:
    await service.self_grade(db, user.id, attempt_id, position, body.correct)


class AttemptSummary(BaseModel):
    id: uuid.UUID
    test_id: uuid.UUID
    test_title: str
    status: str
    started_at: datetime
    submitted_at: datetime | None
    percent: float | None


@router.get("/me/attempts", response_model=list[AttemptSummary])
async def my_attempts(
    db: DbSession, user: CurrentUser, limit: int = Query(30, ge=1, le=100)
) -> list[dict[str, Any]]:
    rows = await db.execute(
        select(Attempt, Test.title)
        .join(Test, Test.id == Attempt.test_id)
        .where(Attempt.user_id == user.id)
        .order_by(Attempt.started_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": a.id,
            "test_id": a.test_id,
            "test_title": title,
            "status": a.status,
            "started_at": a.started_at,
            "submitted_at": a.submitted_at,
            "percent": round(100 * (a.score or 0) / a.max_score, 1) if a.max_score else None,
        }
        for a, title in rows.all()
    ]


@router.get("/me/analytics")
async def my_analytics(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return await service.user_analytics(db, user.id)
