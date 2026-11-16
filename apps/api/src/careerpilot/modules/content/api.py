"""Questions, sources, imports, review queue and background jobs."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import get_settings
from careerpilot.core.errors import ProblemError
from careerpilot.core.jobs import enqueue
from careerpilot.modules.assessments.service import not_found, search_questions, visible_questions
from careerpilot.modules.auth.deps import CurrentUser, DbSession, require_role
from careerpilot.modules.content.adapters import AdapterError, GitHubAdapter, adapter_for
from careerpilot.modules.content.canonical import OptionIn, QuestionIn
from careerpilot.modules.content.licensing import decide
from careerpilot.modules.content.models import (
    BackgroundJob,
    Provenance,
    Question,
    QuestionType,
    QuestionVersion,
    Source,
    SourceStatus,
    question_categories,
    question_companies,
)
from careerpilot.modules.content.service import (
    CategoryResolver,
    _version_from,
    create_question,
    import_upload,
)
from careerpilot.modules.taxonomy.models import Category, Company
from careerpilot.modules.users.models import Role, User

router = APIRouter(tags=["content"])
admin = APIRouter(prefix="/admin", tags=["content-admin"])

Reviewer = Annotated[User, Depends(require_role(Role.REVIEWER))]
Admin = Annotated[User, Depends(require_role(Role.ADMIN))]

PROVENANCE_LABELS = {
    "official_public": "Official practice material published by the organisation",
    "community_licensed": "Open resource, reused under its licence",
    "original": "Written for CareerPilot",
    "ai_generated": "AI-generated, unverified",
    "user_created": "Created by a user",
    "personal_capture": "Your private notes",
}


# --- schemas -------------------------------------------------------------------------------------------


class SourceRef(BaseModel):
    slug: str
    name: str
    url: str | None
    license_spdx: str | None
    attribution: str


class QuestionOut(BaseModel):
    id: uuid.UUID
    version: int
    type: str
    stem: str
    context: str | None
    options: list[dict[str, str]]
    difficulty: int
    language: str
    categories: list[dict[str, str]]
    companies: list[dict[str, str]]
    provenance: str
    provenance_label: str
    label: str | None
    visibility: str
    status: str
    verification: str
    has_answer_key: bool
    source: SourceRef | None
    source_ref: str | None


class QuestionWithKey(QuestionOut):
    answer_key: list[str] | None
    explanation: str | None
    distractor_explanations: dict[str, str]


class QuestionPage(BaseModel):
    items: list[QuestionOut]
    total: int


class ReviewPage(BaseModel):
    items: list[QuestionWithKey]
    total: int


class QuestionCreate(BaseModel):
    type: QuestionType = QuestionType.MCQ_SINGLE
    stem: str = Field(min_length=3, max_length=8000)
    context: str | None = None
    options: list[OptionIn] = Field(default_factory=list)
    answer: list[str] | None = None
    explanation: str | None = None
    difficulty: int = Field(default=2, ge=1, le=4)
    categories: list[str] = Field(min_length=1)
    visibility: str = Field(default="private", pattern="^(private|public)$")


class AnswerKeyIn(BaseModel):
    answer: list[str] = Field(min_length=1)
    explanation: str | None = Field(default=None, max_length=8000)


class SourceIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}$")
    name: str = Field(min_length=2, max_length=200)
    kind: str = Field(pattern="^(github_repo|url|file|directory|website)$")
    url: str | None = None
    description: str = ""
    license_spdx: str | None = None
    attribution: str = ""
    categories: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    default_provenance: Provenance = Provenance.COMMUNITY_LICENSED


class SourceOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    kind: str
    url: str | None
    description: str
    license_spdx: str | None
    license_url: str | None
    attribution: str
    status: str
    licence_decision: str
    share_alike: bool
    commercial_use_allowed: bool | None
    derivatives_allowed: bool | None
    categories: list[str]
    default_provenance: str
    metadata: dict[str, Any]
    last_imported_at: datetime | None
    question_count: int


class JobOut(BaseModel):
    id: uuid.UUID
    kind: str
    status: str
    params: dict[str, Any]
    result: dict[str, Any]
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ReviewDecision(BaseModel):
    question_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    action: str = Field(pattern="^(publish|reject)$")


# --- helpers -------------------------------------------------------------------------------------------


async def question_details(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, Any]]:
    out: dict[uuid.UUID, dict[str, Any]] = {i: {"categories": [], "companies": []} for i in ids}
    for qid, slug, name in (
        await db.execute(
            select(question_categories.c.question_id, Category.slug, Category.name)
            .join(Category, Category.id == question_categories.c.category_id)
            .where(question_categories.c.question_id.in_(ids))
        )
    ).all():
        out[qid]["categories"].append({"slug": slug, "name": name})
    for qid, slug, name in (
        await db.execute(
            select(question_companies.c.question_id, Company.slug, Company.name)
            .join(Company, Company.id == question_companies.c.company_id)
            .where(question_companies.c.question_id.in_(ids))
        )
    ).all():
        out[qid]["companies"].append({"slug": slug, "name": name})
    return out


def serialize_question(
    q: Question, v: QuestionVersion, details: dict[str, Any], source: Source | None, *, with_key: bool = False
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": q.id,
        "version": v.version,
        "type": v.type,
        "stem": v.stem,
        "context": v.context,
        "options": v.options,
        "difficulty": v.difficulty,
        "language": v.language,
        "categories": details.get("categories", []),
        "companies": details.get("companies", []),
        "provenance": q.provenance,
        "provenance_label": PROVENANCE_LABELS.get(q.provenance, q.provenance),
        "label": q.label,
        "visibility": q.visibility,
        "status": q.status,
        "verification": q.verification,
        "has_answer_key": bool(v.answer_key),
        "source_ref": q.source_ref,
        "source": None
        if source is None or source.kind == "upload"
        else {
            "slug": source.slug,
            "name": source.name,
            "url": source.url,
            "license_spdx": source.license_spdx,
            "attribution": source.attribution,
        },
    }
    if with_key:
        data |= {
            "answer_key": v.answer_key,
            "explanation": v.explanation,
            "distractor_explanations": v.distractor_explanations or {},
        }
    return data


async def _load_questions(
    db: AsyncSession, ids: list[uuid.UUID]
) -> list[tuple[Question, QuestionVersion, Source | None]]:
    rows = await db.execute(
        select(Question, QuestionVersion, Source)
        .join(QuestionVersion, QuestionVersion.id == Question.current_version_id)
        .outerjoin(Source, Source.id == Question.source_id)
        .where(Question.id.in_(ids))
    )
    by_id = {q.id: (q, v, s) for q, v, s in rows.all()}
    return [by_id[i] for i in ids if i in by_id]


def _csv(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


# --- questions -----------------------------------------------------------------------------------------


@router.get("/questions", response_model=QuestionPage)
async def list_questions(
    db: DbSession,
    user: CurrentUser,
    q: str | None = Query(None, max_length=200),
    category: str | None = None,
    difficulty: str | None = None,
    type: str | None = None,
    provenance: str | None = None,
    company: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Search the question bank. Answer keys are never included here."""
    stmt = await search_questions(
        db,
        user.id,
        q=q,
        categories=_csv(category),
        difficulties=[int(d) for d in _csv(difficulty) if d.isdigit()],
        types=_csv(type),
        provenance=_csv(provenance),
        company=company,
        require_key=False,
    )
    total = int(await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    ids = list(await db.scalars(stmt.order_by(Question.created_at.desc()).limit(limit).offset(offset)))
    rows = await _load_questions(db, ids)
    details = await question_details(db, ids)
    return {"items": [serialize_question(q_, v, details[q_.id], s) for q_, v, s in rows], "total": total}


@router.get("/questions/{question_id}", response_model=QuestionOut)
async def get_question(question_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    exists = await db.scalar(
        select(Question.id).where(Question.id == question_id, visible_questions(user.id))
    )
    if exists is None:
        raise not_found("Question")
    q, v, s = (await _load_questions(db, [question_id]))[0]
    return serialize_question(q, v, (await question_details(db, [q.id]))[q.id], s)


@router.post("/questions", response_model=QuestionWithKey, status_code=status.HTTP_201_CREATED)
async def create_my_question(body: QuestionCreate, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    """Learners create private questions. Contributors may propose public ones, which go to review."""
    if body.visibility == "public" and not user.role_enum.includes(Role.CONTRIBUTOR):
        raise ProblemError(403, "Only contributors can propose public questions")
    item = QuestionIn.model_validate(body.model_dump() | {"categories": body.categories})
    resolver = await CategoryResolver.load(db)
    cat_ids, unknown = resolver.resolve(item.categories)
    if unknown or not cat_ids:
        raise ProblemError(422, "Unknown category", f"Unknown: {unknown or item.categories}")
    public = body.visibility == "public"
    q = await create_question(
        db,
        item,
        provenance=Provenance.USER_CREATED,
        category_ids=cat_ids,
        owner_id=None if public else user.id,
        visibility=body.visibility,
        status="in_review" if public else "published",
    )
    if public:
        q.owner_id = None
    await db.commit()
    q_, v, s = (await _load_questions(db, [q.id]))[0]
    return serialize_question(q_, v, (await question_details(db, [q.id]))[q.id], s, with_key=True)


@router.put("/questions/{question_id}/answer-key", response_model=QuestionWithKey)
async def set_answer_key(
    question_id: uuid.UUID, body: AnswerKeyIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    """Owners set the key of their private questions (e.g. captured tests with no answers); reviewers any."""
    q = await db.get(Question, question_id)
    if q is None or not (q.owner_id == user.id or user.role_enum.includes(Role.REVIEWER)):
        raise not_found("Question")
    v = await db.get(QuestionVersion, q.current_version_id)
    assert v is not None
    item = QuestionIn.model_validate(
        {
            "type": v.type,
            "stem": v.stem,
            "context": v.context,
            "options": v.options,
            "answer": body.answer,
            "explanation": body.explanation if body.explanation is not None else v.explanation,
            "distractor_explanations": v.distractor_explanations,
            "difficulty": v.difficulty,
            "language": v.language,
            "time_limit_s": v.time_limit_s,
        }
    )
    new = _version_from(item, q.id, v.version + 1)
    db.add(new)
    await db.flush()
    q.current_version_id = new.id
    await db.commit()
    q_, v2, s = (await _load_questions(db, [q.id]))[0]
    return serialize_question(q_, v2, (await question_details(db, [q.id]))[q.id], s, with_key=True)


@router.post("/me/imports/upload", status_code=status.HTTP_201_CREATED)
async def upload_my_questions(
    db: DbSession,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    kind: str = Form("user_created", pattern="^(user_created|personal_capture)$"),
    category: str = Form(""),
) -> dict[str, Any]:
    """Import your own JSON / YAML / CSV / Markdown / PDF file. Everything stays private to you."""
    max_bytes = get_settings().import_max_file_bytes
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ProblemError(413, "File too large", f"Maximum {max_bytes // (1024 * 1024)} MB")
    name = re.sub(r"[^\w.\-]", "_", file.filename or "upload")[:120]
    try:
        report = await import_upload(
            db,
            owner_id=user.id,
            filename=name,
            data=data,
            provenance=Provenance(kind),
            default_categories=_csv(category),
        )
    except AdapterError as exc:
        raise ProblemError(422, "Import failed", str(exc)) from None
    return report.as_dict()


# --- jobs ----------------------------------------------------------------------------------------------


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, db: DbSession, user: CurrentUser) -> BackgroundJob:
    job = await db.get(BackgroundJob, job_id)
    if job is None or not (job.requested_by == user.id or user.role_enum.includes(Role.ADMIN)):
        raise not_found("Job")
    return job


# --- sources & imports (admin) -------------------------------------------------------------------------


async def _source_out(db: AsyncSession, s: Source) -> dict[str, Any]:
    count = await db.scalar(select(func.count()).select_from(Question).where(Question.source_id == s.id))
    return {
        **{k: getattr(s, k) for k in SourceOut.model_fields if hasattr(s, k) and k != "metadata"},
        "metadata": s.metadata_ or {},
        "question_count": int(count or 0),
    }


@admin.get("/sources", response_model=list[SourceOut])
async def list_sources(db: DbSession, _: Reviewer) -> list[dict[str, Any]]:
    rows = await db.scalars(select(Source).where(Source.kind != "upload").order_by(Source.name))
    return [await _source_out(db, s) for s in rows]


@admin.post("/sources", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
async def create_source(body: SourceIn, db: DbSession, _: Admin) -> dict[str, Any]:
    if await db.scalar(select(Source.id).where(Source.slug == body.slug)):
        raise ProblemError(409, "A source with this slug already exists")
    if body.default_provenance in (
        Provenance.PERSONAL_CAPTURE,
        Provenance.AI_GENERATED,
        Provenance.USER_CREATED,
    ):
        raise ProblemError(422, "Use the personal import for private content")
    decision = decide(body.license_spdx, commercial_mode=get_settings().commercial_mode)
    source = Source(
        **body.model_dump(),
        status=SourceStatus.LINK_ONLY.value if body.kind == "website" else decision.status.value,
        licence_decision=decision.reason,
    )
    db.add(source)
    await db.commit()
    return await _source_out(db, source)


@admin.post("/sources/{source_id}/inspect")
async def inspect_source(source_id: uuid.UUID, db: DbSession, _: Reviewer) -> dict[str, Any]:
    """Dry run: metadata, licence decision and (GitHub) README / question-bank detection.

    Nothing is imported.
    """
    source = await db.get(Source, source_id)
    if source is None:
        raise not_found("Source")
    try:
        adapter = adapter_for(source.kind)
        description = await adapter.describe(source)
        spdx = description.license_spdx if source.kind == "github_repo" else source.license_spdx
        decision = decide(spdx, commercial_mode=get_settings().commercial_mode)
        scan: dict[str, Any] = {}
        if isinstance(adapter, GitHubAdapter) and decision.status == SourceStatus.APPROVED:
            scan = {
                k: v
                for k, v in (await adapter.list_candidates(source, description)).items()
                if not k.startswith("_")
            }
    except AdapterError as exc:
        raise ProblemError(422, "Source could not be inspected", str(exc)) from None
    return {
        "license_spdx": spdx,
        "decision": decision.status.value,
        "reason": decision.reason,
        "metadata": description.metadata,
        "revision": description.revision,
        "scan": scan,
    }


@admin.post("/sources/{source_id}/import", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
async def import_source(
    source_id: uuid.UUID, db: DbSession, user: Admin, publish: bool = False
) -> BackgroundJob:
    source = await db.get(Source, source_id)
    if source is None:
        raise not_found("Source")
    job = BackgroundJob(
        kind="import", requested_by=user.id, params={"source": source.slug, "publish": publish}
    )
    db.add(job)
    await db.commit()
    await enqueue("content.import_source", source_id=str(source.id), job_id=str(job.id), publish=publish)
    await db.refresh(job)
    return job


@admin.get("/review", response_model=ReviewPage)
async def review_queue(db: DbSession, _: Reviewer, limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
    ids = list(
        await db.scalars(
            select(Question.id)
            .where(Question.status == "in_review")
            .order_by(Question.created_at)
            .limit(limit)
        )
    )
    total = int(
        await db.scalar(select(func.count()).select_from(Question).where(Question.status == "in_review")) or 0
    )
    rows = await _load_questions(db, ids)
    details = await question_details(db, ids)
    return {
        "items": [serialize_question(q, v, details[q.id], s, with_key=True) for q, v, s in rows],
        "total": total,
    }


@admin.post("/review/decision")
async def review_decision(body: ReviewDecision, db: DbSession, user: Reviewer) -> dict[str, int]:
    new_status = "published" if body.action == "publish" else "retired"
    result = await db.execute(
        update(Question)
        .where(
            Question.id.in_(body.question_ids),
            Question.status == "in_review",
            Question.visibility == "public",
        )
        .values(
            status=new_status, verification="reviewed" if body.action == "publish" else Question.verification
        )
    )
    await db.commit()
    return {"updated": int(result.rowcount or 0)}  # type: ignore[attr-defined]
