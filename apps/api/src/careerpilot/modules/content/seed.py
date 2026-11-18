"""Seeding: register sources from `content/sources.yaml`, import original questions, build curated tests,
and import a user's private captures as company collections."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import get_settings
from careerpilot.modules.assessments.models import Test, TestItem
from careerpilot.modules.content.licensing import decide
from careerpilot.modules.content.models import Provenance, Question, Source, SourceStatus, question_companies
from careerpilot.modules.content.service import ImportReport, run_import
from careerpilot.modules.taxonomy.models import Company


def content_root() -> Path:
    for d in get_settings().content_dirs:
        p = Path(d).expanduser().resolve()
        if (p / "sources.yaml").exists():
            return p
    raise FileNotFoundError("content/sources.yaml not found in CONTENT_DIRS")


async def seed_sources(db: AsyncSession, root: Path) -> dict[str, Source]:
    data = yaml.safe_load((root / "sources.yaml").read_text())
    existing = {s.slug: s for s in await db.scalars(select(Source))}
    out = {}
    for entry in data.get("sources", []):
        source = existing.get(entry["slug"])
        if source is None:
            source = Source(slug=entry["slug"])
            db.add(source)
        source.name = entry["name"]
        source.kind = entry["kind"]
        source.url = entry.get("url")
        source.description = (entry.get("description") or "").strip()
        source.attribution = entry.get("attribution", "")
        source.categories = entry.get("categories", [])
        source.config = entry.get("config", {})
        source.default_provenance = entry.get("default_provenance", Provenance.COMMUNITY_LICENSED.value)
        if entry.get("license_spdx"):
            source.license_spdx = entry["license_spdx"]
        if source.kind == "website":
            source.status = SourceStatus.LINK_ONLY.value
            source.licence_decision = "Website: terms not reviewed for copying. Only the link is kept."
        elif (
            source.default_provenance != Provenance.ORIGINAL.value
            and source.status != SourceStatus.REJECTED.value
        ):
            d = decide(source.license_spdx, commercial_mode=get_settings().commercial_mode)
            if (
                source.kind != "github_repo" or source.license_spdx
            ):  # GitHub licences are detected on inspect/import
                source.status, source.licence_decision = d.status.value, d.reason
            else:
                source.status = SourceStatus.PENDING_REVIEW.value
                source.licence_decision = "Licence is read from GitHub on inspect/import."
        out[source.slug] = source
    await db.commit()
    return out


async def seed_tests(db: AsyncSession, root: Path, source: Source) -> int:
    data = yaml.safe_load((root / "tests.yaml").read_text())
    by_ext = {
        q.external_id: q.id for q in await db.scalars(select(Question).where(Question.source_id == source.id))
    }
    count = 0
    for spec in data.get("tests", []):
        test = await db.scalar(select(Test).where(Test.slug == spec["slug"]))
        if test is None:
            test = Test(slug=spec["slug"], title=spec["title"])
            db.add(test)
        test.title, test.description = spec["title"], spec.get("description", "")
        test.mode, test.kind, test.visibility = spec.get("mode", "exam"), "curated", "public"
        test.time_limit_s = spec["time_limit_minutes"] * 60 if spec.get("time_limit_minutes") else None
        test.shuffle = bool(spec.get("shuffle", False))
        test.label = "CareerPilot original practice test"
        await db.flush()
        await db.execute(delete(TestItem).where(TestItem.test_id == test.id))
        missing = [qid for qid in spec["questions"] if qid not in by_ext]
        if missing:
            raise ValueError(f"test {spec['slug']}: unknown question ids {missing}")
        for pos, ext in enumerate(spec["questions"]):
            db.add(TestItem(test_id=test.id, position=pos, question_id=by_ext[ext]))
        count += 1
    await db.commit()
    return count


async def seed_content(db: AsyncSession) -> dict[str, Any]:
    root = content_root()
    sources = await seed_sources(db, root)
    report: ImportReport = await run_import(db, sources["careerpilot-original"].id, publish=True)
    if report.errors:
        raise ValueError(f"original content has errors: {report.errors[:5]}")
    tests = await seed_tests(db, root, sources["careerpilot-original"])
    # Knowledge base for the coach (RAG): curated notes + explanations of published questions.
    from careerpilot.modules.kb.service import index_question_explanations, seed_notes

    kb_notes = await seed_notes(db, root)
    kb_questions = await index_question_explanations(db)
    return {
        "sources": len(sources),
        "questions": report.as_dict(),
        "tests": tests,
        "kb": {"notes": kb_notes, "questions": kb_questions},
    }


async def import_captures(db: AsyncSession, *, owner_id: uuid.UUID, path: str) -> dict[str, Any]:
    """Private captures → private questions plus one private company collection per captured test file."""
    slug = f"captures-{owner_id}"
    source = await db.scalar(select(Source).where(Source.slug == slug))
    if source is None:
        source = Source(
            slug=slug,
            name="My captured tests",
            kind="directory",
            default_provenance=Provenance.PERSONAL_CAPTURE.value,
            status=SourceStatus.APPROVED.value,
            licence_decision="Private notes of the owner: never published or shared.",
        )
        db.add(source)
    source.config = {"path": path, "include": ["*.yaml", "*.yml", "*.json"]}
    await db.commit()
    report = await run_import(db, source.id, owner_id=owner_id)

    # One private, untimed practice collection per captured test file, linked to the company.
    files: dict[str, list[tuple[str, uuid.UUID]]] = {}
    for q in await db.scalars(
        select(Question).where(Question.source_id == source.id, Question.owner_id == owner_id)
    ):
        file = (q.source_ref or "").split("#")[0]
        files.setdefault(file, []).append((q.source_ref or "", q.id))
    created = 0
    for file, items in files.items():
        company_id = await db.scalar(
            select(question_companies.c.company_id).where(question_companies.c.question_id == items[0][1])
        )
        company = await db.get(Company, company_id) if company_id else None
        title = f"{company.name if company else 'Captured test'} · {Path(file).stem.replace('-', ' ')}"
        test = await db.scalar(
            select(Test).where(Test.owner_id == owner_id, Test.kind == "company", Test.title == title)
        )
        if test is None:
            test = Test(
                title=title,
                owner_id=owner_id,
                visibility="private",
                kind="company",
                mode="practice",
                company_id=company_id,
                label="Your private notes from a test you took",
                description="Captured questions without keys: practise, then set the keys you confirm.",
            )
            db.add(test)
            await db.flush()
            created += 1
        await db.execute(delete(TestItem).where(TestItem.test_id == test.id))
        items.sort(key=lambda x: int(x[0].rsplit("#", 1)[-1]) if x[0].rsplit("#", 1)[-1].isdigit() else 0)
        for pos, (_, qid) in enumerate(items):
            db.add(TestItem(test_id=test.id, position=pos, question_id=qid))
    await db.commit()
    return {"import": report.as_dict(), "collections_created": created, "collections": len(files)}
