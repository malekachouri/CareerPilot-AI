"""Import pipeline and question storage.

source → adapter.describe (metadata, licence) → licence policy → adapter.files → parser → canonical items
→ category mapping → deduplication (exact hash, then trigram similarity) → versioned storage with attribution.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import get_settings
from careerpilot.core.db import utcnow
from careerpilot.modules.content.adapters import AdapterError, adapter_for
from careerpilot.modules.content.canonical import QuestionIn, content_hash, normalize_text
from careerpilot.modules.content.licensing import decide
from careerpilot.modules.content.models import (
    BackgroundJob,
    Provenance,
    Question,
    QuestionVersion,
    Source,
    SourceStatus,
    question_categories,
    question_companies,
)
from careerpilot.modules.content.parsers import ParseContext, parse_bytes
from careerpilot.modules.taxonomy.models import Category, Company

NEAR_DUPLICATE_SIMILARITY = 0.9
COMPANY_PRACTICE_LABEL = "Practice question inspired by publicly documented recruitment topics"
CAPTURE_LABEL = "Your private notes from a test you took"


@dataclass
class ImportReport:
    files: int = 0
    parsed: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    duplicates: int = 0
    near_duplicates: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    unknown_categories: dict[str, int] = field(default_factory=dict)
    link_only: bool = False
    licence: dict[str, Any] = field(default_factory=dict)
    scan: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["errors"] = self.errors[:200]  # keep job rows small
        d["error_count"] = len(self.errors)
        return d


class CategoryResolver:
    """Maps slugs and aliases (as imported banks spell them) to category ids."""

    def __init__(self, categories: list[Category]) -> None:
        self.by_key: dict[str, uuid.UUID] = {}
        for c in categories:
            self.by_key[c.slug] = c.id
            for alias in c.aliases or []:
                self.by_key.setdefault(alias, c.id)

    @classmethod
    async def load(cls, db: AsyncSession) -> CategoryResolver:
        return cls(list(await db.scalars(select(Category))))

    def resolve(self, keys: list[str]) -> tuple[list[uuid.UUID], list[str]]:
        found, unknown = [], []
        for key in keys:
            k = normalize_text(key).replace(" ", "-")
            if k in self.by_key:
                if self.by_key[k] not in found:
                    found.append(self.by_key[k])
            else:
                unknown.append(key)
        return found, unknown


def _scope_filter(owner_id: uuid.UUID | None) -> Any:
    """Duplicates are searched among public items and the owner's private items only."""
    if owner_id is None:
        return Question.visibility == "public"
    return or_(Question.visibility == "public", Question.owner_id == owner_id)


async def find_duplicate(
    db: AsyncSession, item: QuestionIn, owner_id: uuid.UUID | None
) -> tuple[str, uuid.UUID] | None:
    digest = content_hash(item)
    exact = await db.scalar(
        select(Question.id)
        .join(QuestionVersion, QuestionVersion.id == Question.current_version_id)
        .where(QuestionVersion.content_hash == digest, _scope_filter(owner_id), Question.status != "retired")
        .limit(1)
    )
    if exact:
        return "exact", exact
    stem = dedup_text(item)
    if len(stem) < 25:  # short stems ("What is Docker?") are too generic for fuzzy matching
        return None
    near = await db.scalar(
        select(Question.id)
        .join(QuestionVersion, QuestionVersion.id == Question.current_version_id)
        .where(
            func.similarity(QuestionVersion.stem_normalized, stem) >= NEAR_DUPLICATE_SIMILARITY,
            _scope_filter(owner_id),
            Question.status != "retired",
        )
        .limit(1)
    )
    return ("near", near) if near else None


def dedup_text(item: QuestionIn) -> str:
    """Stem + context: scenario questions often share a stem ("Which action should you take?")."""
    return normalize_text(f"{item.stem} {item.context or ''}")


def _version_from(item: QuestionIn, question_id: uuid.UUID, version: int) -> QuestionVersion:
    return QuestionVersion(
        question_id=question_id,
        version=version,
        type=item.type.value,
        language=item.language,
        stem=item.stem.strip(),
        context=item.context,
        options=[o.model_dump() for o in item.options],
        answer_key=item.answer,
        explanation=item.explanation,
        distractor_explanations=item.distractor_explanations,
        difficulty=item.difficulty,
        time_limit_s=item.time_limit_s,
        stem_normalized=dedup_text(item),
        content_hash=content_hash(item),
    )


async def create_question(
    db: AsyncSession,
    item: QuestionIn,
    *,
    provenance: Provenance,
    category_ids: list[uuid.UUID],
    owner_id: uuid.UUID | None = None,
    visibility: str = "public",
    source: Source | None = None,
    status: str = "published",
    company_ids: list[uuid.UUID] | None = None,
    label: str | None = None,
) -> Question:
    question = Question(
        id=uuid.uuid4(),
        provenance=provenance.value,
        visibility=visibility,
        owner_id=owner_id,
        source_id=source.id if source else None,
        source_ref=item.source_ref,
        external_id=item.external_id,
        status=status,
        verification="reviewed" if provenance == Provenance.ORIGINAL else "unverified",
        label=label,
    )
    db.add(question)
    await db.flush()
    version = _version_from(item, question.id, 1)
    db.add(version)
    await db.flush()
    question.current_version_id = version.id
    if category_ids:
        await db.execute(
            insert(question_categories),
            [{"question_id": question.id, "category_id": c} for c in category_ids],
        )
    if company_ids:
        await db.execute(
            insert(question_companies), [{"question_id": question.id, "company_id": c} for c in company_ids]
        )
    return question


async def _start_job(db: AsyncSession, job_id: uuid.UUID | None) -> BackgroundJob | None:
    if job_id is None:
        return None
    job = await db.get(BackgroundJob, job_id)
    if job:
        job.status, job.started_at = "running", utcnow()
        await db.commit()
    return job


async def run_import(
    db: AsyncSession,
    source_id: uuid.UUID,
    *,
    job_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    publish: bool | None = None,
) -> ImportReport:
    """Import one source. Safe to re-run: unchanged items are skipped, changed ones get a new version."""
    job = await _start_job(db, job_id)
    report = ImportReport()
    try:
        source = await db.get(Source, source_id)
        if source is None:
            raise AdapterError("source not found")
        await _import_source(db, source, report, owner_id=owner_id, publish=publish)
        source.last_imported_at = utcnow()
        if job:
            job.status, job.result, job.finished_at = "succeeded", report.as_dict(), utcnow()
        await db.commit()
    except AdapterError as exc:
        await db.rollback()
        if job:
            job = await db.get(BackgroundJob, job_id)
            assert job is not None
            job.status, job.error, job.finished_at = "failed", str(exc), utcnow()
            job.result = report.as_dict()
            await db.commit()
        else:
            raise
    return report


async def _import_source(
    db: AsyncSession,
    source: Source,
    report: ImportReport,
    *,
    owner_id: uuid.UUID | None,
    publish: bool | None,
) -> None:
    provenance = Provenance(source.default_provenance)
    private = provenance == Provenance.PERSONAL_CAPTURE
    if private and owner_id is None:
        raise AdapterError("a personal-capture source needs an owner (the user who took the tests)")

    adapter = adapter_for(source.kind)
    description = await adapter.describe(source)
    if description.license_spdx and source.kind == "github_repo":
        source.license_spdx = description.license_spdx
    source.license_url = description.license_url or source.license_url
    source.metadata_ = {**(source.metadata_ or {}), **description.metadata, "revision": description.revision}

    if private:
        # Never published or shown to anyone else, so redistribution licences do not apply (docs/11 §1.1).
        report.licence = {"status": "private", "reason": "Personal capture: visible to its owner only."}
    elif provenance == Provenance.ORIGINAL:
        source.status = SourceStatus.APPROVED.value
        report.licence = {"status": "approved", "reason": "Original CareerPilot content."}
    else:
        decision = decide(source.license_spdx, commercial_mode=get_settings().commercial_mode)
        if source.status != SourceStatus.REJECTED.value:
            source.status = decision.status.value
        source.licence_decision = decision.reason
        source.commercial_use_allowed = decision.commercial_use_allowed
        source.derivatives_allowed = decision.derivatives_allowed
        source.share_alike = decision.share_alike
        report.licence = {"status": source.status, "spdx": source.license_spdx, "reason": decision.reason}
        if source.status != SourceStatus.APPROVED.value:
            report.link_only = True
            return  # reference and link are kept; no content is copied

    if source.kind == "github_repo":
        from careerpilot.modules.content.adapters import GitHubAdapter

        assert isinstance(adapter, GitHubAdapter)
        scan = await adapter.list_candidates(source, description)
        report.scan = {k: v for k, v in scan.items() if not k.startswith("_")}

    resolver = await CategoryResolver.load(db)
    companies = {c.slug: c.id for c in await db.scalars(select(Company))}
    default_status = "published" if (publish or private or provenance == Provenance.ORIGINAL) else "in_review"
    if publish is False:
        default_status = "in_review"

    async for f in adapter.files(source, description):
        report.files += 1
        ctx = ParseContext(path=f.path, default_categories=tuple(source.categories or []))
        parsed = parse_bytes(f.data, f.fmt, ctx)
        report.errors += parsed.errors
        for item in parsed.items:
            report.parsed += 1
            if f.url:  # attribution: link to the exact file (and line) in the source
                line = (item.source_ref or "").rsplit(":", 1)[-1]
                item.source_ref = f"{f.url}#L{line}" if line.isdigit() else f.url
            await _store_item(
                db,
                source,
                item,
                report,
                resolver,
                companies,
                provenance=provenance,
                owner_id=owner_id if private else None,
                status=default_status,
            )
        await db.flush()


async def _store_item(
    db: AsyncSession,
    source: Source,
    item: QuestionIn,
    report: ImportReport,
    resolver: CategoryResolver,
    companies: dict[str, uuid.UUID],
    *,
    provenance: Provenance,
    owner_id: uuid.UUID | None,
    status: str,
) -> None:
    category_ids, unknown = resolver.resolve(item.categories)
    for u in unknown:
        report.unknown_categories[u] = report.unknown_categories.get(u, 0) + 1
    if not category_ids:
        report.errors.append(
            {"ref": item.source_ref or "", "error": f"no known category in {item.categories}"}
        )
        return

    # Re-import of the same item from the same source: update in place (new version) instead of duplicating.
    if item.external_id:
        existing = await db.scalar(
            select(Question).where(
                Question.source_id == source.id,
                Question.external_id == item.external_id,
                Question.owner_id.is_(owner_id) if owner_id is None else Question.owner_id == owner_id,
            )
        )
        if existing:
            current = await db.get(QuestionVersion, existing.current_version_id)
            if current and current.content_hash == content_hash(item) and current.answer_key == item.answer:
                report.unchanged += 1
                return
            number = (
                await db.scalar(
                    select(func.max(QuestionVersion.version)).where(
                        QuestionVersion.question_id == existing.id
                    )
                )
            ) or 0
            version = _version_from(item, existing.id, number + 1)
            db.add(version)
            await db.flush()
            existing.current_version_id = version.id
            report.updated += 1
            return

    dup = await find_duplicate(db, item, owner_id)
    if dup:
        kind, _ = dup
        if kind == "exact":
            report.duplicates += 1
        else:
            report.near_duplicates += 1
        return

    company_ids = [companies[c] for c in item.companies if c in companies]
    label = None
    if provenance == Provenance.PERSONAL_CAPTURE:
        label = CAPTURE_LABEL
    elif company_ids and provenance != Provenance.OFFICIAL_PUBLIC:
        label = COMPANY_PRACTICE_LABEL
    await create_question(
        db,
        item,
        provenance=provenance,
        category_ids=category_ids,
        owner_id=owner_id,
        visibility="private" if owner_id else "public",
        source=source,
        status=status,
        company_ids=company_ids,
        label=label,
    )
    report.created += 1


async def import_upload(
    db: AsyncSession,
    *,
    owner_id: uuid.UUID,
    filename: str,
    data: bytes,
    provenance: Provenance,
    default_categories: list[str],
) -> ImportReport:
    """A user uploads their own file. Items stay private to them (`user_created` or `personal_capture`)."""
    if provenance not in (Provenance.USER_CREATED, Provenance.PERSONAL_CAPTURE):
        raise AdapterError("uploads can only create your own private questions")
    slug = f"upload-{owner_id}"
    source = await db.scalar(select(Source).where(Source.slug == slug))
    if source is None:
        source = Source(
            slug=slug,
            name="My uploads",
            kind="upload",
            status=SourceStatus.APPROVED.value,
            default_provenance=provenance.value,
            licence_decision="Private uploads of the owner.",
        )
        db.add(source)
        await db.flush()
    report = ImportReport(files=1, licence={"status": "private"})
    fmt = filename.rsplit(".", 1)[-1] if "." in filename else ""
    parsed = parse_bytes(data, fmt, ParseContext(path=filename, default_categories=tuple(default_categories)))
    report.errors += parsed.errors
    resolver = await CategoryResolver.load(db)
    companies = {c.slug: c.id for c in await db.scalars(select(Company))}
    for item in parsed.items:
        report.parsed += 1
        await _store_item(
            db,
            source,
            item,
            report,
            resolver,
            companies,
            provenance=provenance,
            owner_id=owner_id,
            status="published",
        )
    await db.commit()
    return report
