from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from careerpilot.core.errors import ProblemError
from careerpilot.modules.assessments.models import Test
from careerpilot.modules.auth.deps import CurrentUser, DbSession
from careerpilot.modules.content.models import Question, question_companies
from careerpilot.modules.taxonomy.models import Category, Company, Track, track_categories

router = APIRouter(tags=["taxonomy"])

COMPANY_DISCLAIMER = (
    "CareerPilot does not have access to any company's real recruitment tests. Questions here are your own "
    "private notes or practice questions inspired by publicly documented recruitment topics. They are never "
    "presented as official company questions unless the company itself published them."
)


class CategoryOut(BaseModel):
    slug: str
    name: str
    children: list[CategoryOut] = []


class TrackOut(BaseModel):
    slug: str
    name: str
    description: str
    groups: list[str]


class CompanyOut(BaseModel):
    slug: str
    name: str
    website: str | None
    official_prep_links: list[str]
    description: str
    public_questions: int
    my_private_questions: int
    tests: int


class CompanyDetail(CompanyOut):
    disclaimer: str


@router.get("/categories", response_model=list[CategoryOut])
async def categories(db: DbSession, _: CurrentUser) -> list[CategoryOut]:
    rows = list(await db.scalars(select(Category).order_by(Category.sort_order, Category.name)))
    groups = [c for c in rows if c.parent_id is None]
    return [
        CategoryOut(
            slug=g.slug,
            name=g.name,
            children=[CategoryOut(slug=c.slug, name=c.name) for c in rows if c.parent_id == g.id],
        )
        for g in groups
    ]


@router.get("/tracks", response_model=list[TrackOut])
async def tracks(db: DbSession, _: CurrentUser) -> list[TrackOut]:
    out = []
    for t in await db.scalars(select(Track).order_by(Track.name)):
        slugs = await db.scalars(
            select(Category.slug)
            .join(track_categories, track_categories.c.category_id == Category.id)
            .where(track_categories.c.track_id == t.id)
            .order_by(Category.sort_order)
        )
        out.append(TrackOut(slug=t.slug, name=t.name, description=t.description, groups=list(slugs)))
    return out


async def _company_counts(db: DbSession, user_id: uuid.UUID, company_ids: list[uuid.UUID]) -> dict[str, Any]:
    q = (
        select(
            question_companies.c.company_id,
            func.count().filter(Question.visibility == "public"),
            func.count().filter(Question.owner_id == user_id),
        )
        .join(Question, Question.id == question_companies.c.question_id)
        .where(question_companies.c.company_id.in_(company_ids), Question.status == "published")
        .group_by(question_companies.c.company_id)
    )
    counts = {cid: (int(p), int(m)) for cid, p, m in (await db.execute(q)).all()}
    tests = dict(
        (
            await db.execute(
                select(Test.company_id, func.count())
                .where(
                    Test.company_id.in_(company_ids),
                    Test.status == "published",
                    or_(Test.visibility == "public", Test.owner_id == user_id),
                )
                .group_by(Test.company_id)
            )
        ).all()
    )
    return {"questions": counts, "tests": tests}


def _company_out(c: Company, counts: dict[str, Any]) -> dict[str, Any]:
    public, mine = counts["questions"].get(c.id, (0, 0))
    return {
        "slug": c.slug,
        "name": c.name,
        "website": c.website,
        "official_prep_links": c.official_prep_links or [],
        "description": c.description,
        "public_questions": public,
        "my_private_questions": mine,
        "tests": int(counts["tests"].get(c.id, 0)),
    }


@router.get("/companies", response_model=list[CompanyOut])
async def companies(db: DbSession, user: CurrentUser) -> list[dict[str, Any]]:
    rows = list(await db.scalars(select(Company).order_by(Company.name)))
    counts = await _company_counts(db, user.id, [c.id for c in rows])
    return [_company_out(c, counts) for c in rows]


@router.get("/companies/{slug}", response_model=CompanyDetail)
async def company(slug: str, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    c = await db.scalar(select(Company).where(Company.slug == slug))
    if c is None:
        raise ProblemError(404, "Company not found")
    counts = await _company_counts(db, user.id, [c.id])
    return {**_company_out(c, counts), "disclaimer": COMPANY_DISCLAIMER}
