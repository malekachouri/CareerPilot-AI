"""Test library, custom tests, attempts (server-side timing), grading, results and analytics."""

from __future__ import annotations

import random
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.db import utcnow
from careerpilot.core.errors import ProblemError
from careerpilot.modules.assessments.models import Attempt, AttemptAnswer, Test, TestItem
from careerpilot.modules.content.models import (
    AUTO_GRADED_TYPES,
    Question,
    QuestionType,
    QuestionVersion,
    question_categories,
    question_companies,
)
from careerpilot.modules.taxonomy.models import Category, Company

GRACE_SECONDS = 5  # network latency allowance after the deadline
CORRECT_AS_INT = case((AttemptAnswer.is_correct.is_(True), 1), else_=0)
SINGLE_CHOICE = {
    QuestionType.MCQ_SINGLE,
    QuestionType.TRUE_FALSE,
    QuestionType.TRUE_FALSE_UNDETERMINED,
    QuestionType.SCENARIO,
    QuestionType.SITUATIONAL,
    QuestionType.SURVEY,
}


def not_found(what: str) -> ProblemError:
    return ProblemError(404, f"{what} not found", code="https://careerpilot.dev/problems/not-found")


# --- visibility -----------------------------------------------------------------------------------------


def visible_questions(user_id: uuid.UUID) -> Any:
    return and_(
        Question.status == "published", or_(Question.visibility == "public", Question.owner_id == user_id)
    )


def visible_tests(user_id: uuid.UUID) -> Any:
    return and_(Test.status == "published", or_(Test.visibility == "public", Test.owner_id == user_id))


async def expand_categories(db: AsyncSession, slugs: list[str]) -> list[uuid.UUID]:
    """A group slug (e.g. `devops`) means all of its categories."""
    if not slugs:
        return []
    cats = list(await db.scalars(select(Category).where(Category.slug.in_(slugs))))
    ids = [c.id for c in cats]
    group_ids = [c.id for c in cats if c.parent_id is None]
    if group_ids:
        ids += list(await db.scalars(select(Category.id).where(Category.parent_id.in_(group_ids))))
    return ids


# --- library ---------------------------------------------------------------------------------------------


async def test_summaries(db: AsyncSession, tests: list[Test]) -> dict[uuid.UUID, dict[str, Any]]:
    """Question count, categories, average difficulty, types and provenance for each test (two queries)."""
    if not tests:
        return {}
    ids = [t.id for t in tests]
    per_question = await db.execute(
        select(TestItem.test_id, QuestionVersion.difficulty, QuestionVersion.type, Question.provenance)
        .join(Question, Question.id == TestItem.question_id)
        .join(QuestionVersion, QuestionVersion.id == Question.current_version_id)
        .where(TestItem.test_id.in_(ids))
    )
    acc: dict[uuid.UUID, dict[str, Any]] = {
        i: {"d": [], "types": set(), "prov": set(), "cats": {}} for i in ids
    }
    for test_id, difficulty, qtype, provenance in per_question.all():
        acc[test_id]["d"].append(difficulty)
        acc[test_id]["types"].add(qtype)
        acc[test_id]["prov"].add(provenance)
    cats = await db.execute(
        select(TestItem.test_id, Category.slug, Category.name)
        .join(question_categories, question_categories.c.question_id == TestItem.question_id)
        .join(Category, Category.id == question_categories.c.category_id)
        .where(TestItem.test_id.in_(ids))
        .distinct()
    )
    for test_id, slug, name in cats.all():
        acc[test_id]["cats"][slug] = name
    out = {}
    for t in tests:
        a = acc[t.id]
        out[t.id] = {
            "question_count": len(a["d"]),
            "categories": [{"slug": s, "name": n} for s, n in sorted(a["cats"].items())],
            "average_difficulty": round(sum(a["d"]) / len(a["d"]), 1) if a["d"] else None,
            "provenance": sorted(a["prov"]),
            "types": sorted(a["types"]),
        }
    return out


async def list_tests(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    q: str | None,
    category: str | None,
    difficulty: int | None,
    kind: str | None,
    company: str | None,
    mine: bool,
    limit: int,
    offset: int,
) -> list[Test]:
    stmt: Select[Any] = select(Test).where(visible_tests(user_id))
    if mine:
        stmt = stmt.where(Test.owner_id == user_id)
    if kind:
        stmt = stmt.where(Test.kind == kind)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Test.title.ilike(like), Test.description.ilike(like)))
    if company:
        stmt = stmt.join(Company, Company.id == Test.company_id).where(Company.slug == company)
    if category or difficulty:
        sub = (
            select(TestItem.test_id)
            .join(Question, Question.id == TestItem.question_id)
            .join(QuestionVersion, QuestionVersion.id == Question.current_version_id)
        )
        if category:
            cat_ids = await expand_categories(db, [category])
            sub = sub.join(question_categories, question_categories.c.question_id == Question.id).where(
                question_categories.c.category_id.in_(cat_ids)
            )
        if difficulty:
            sub = sub.where(QuestionVersion.difficulty == difficulty)
        stmt = stmt.where(Test.id.in_(sub))
    stmt = stmt.order_by(Test.kind != "curated", Test.title).limit(limit).offset(offset)
    return list(await db.scalars(stmt))


async def get_test(db: AsyncSession, user_id: uuid.UUID, test_id: uuid.UUID) -> Test:
    test = await db.scalar(select(Test).where(Test.id == test_id, visible_tests(user_id)))
    if test is None:
        raise not_found("Test")
    return test


async def search_questions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    q: str | None,
    categories: list[str],
    difficulties: list[int],
    types: list[str],
    provenance: list[str],
    company: str | None,
    require_key: bool,
) -> Select[Any]:
    stmt = (
        select(Question.id)
        .join(QuestionVersion, QuestionVersion.id == Question.current_version_id)
        .where(visible_questions(user_id))
    )
    if categories:
        cat_ids = await expand_categories(db, categories)
        stmt = stmt.where(
            Question.id.in_(
                select(question_categories.c.question_id).where(
                    question_categories.c.category_id.in_(cat_ids)
                )
            )
        )
    if difficulties:
        stmt = stmt.where(QuestionVersion.difficulty.in_(difficulties))
    if types:
        stmt = stmt.where(QuestionVersion.type.in_(types))
    if provenance:
        stmt = stmt.where(Question.provenance.in_(provenance))
    if company:
        stmt = stmt.where(
            Question.id.in_(
                select(question_companies.c.question_id)
                .join(Company, Company.id == question_companies.c.company_id)
                .where(Company.slug == company)
            )
        )
    if require_key:
        stmt = stmt.where(
            QuestionVersion.answer_key.is_not(None), QuestionVersion.type.in_(list(AUTO_GRADED_TYPES))
        )
    if q:
        stmt = stmt.where(QuestionVersion.stem.ilike(f"%{q.strip()}%"))
    return stmt


async def build_custom_test(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    title: str,
    categories: list[str],
    difficulties: list[int],
    types: list[str],
    provenance: list[str],
    company: str | None,
    count: int,
    time_limit_minutes: int | None,
    mode: str,
    require_key: bool,
) -> Test:
    stmt = await search_questions(
        db,
        user_id,
        q=None,
        categories=categories,
        difficulties=difficulties,
        types=types,
        provenance=provenance,
        company=company,
        require_key=require_key,
    )
    ids = list(await db.scalars(stmt.order_by(func.random()).limit(count)))
    if not ids:
        raise ProblemError(
            422,
            "No questions match these filters",
            "Widen the filters (more categories or difficulty levels).",
            code="https://careerpilot.dev/problems/no-questions",
        )
    test = Test(
        title=title,
        owner_id=user_id,
        visibility="private",
        mode=mode,
        kind="custom",
        time_limit_s=time_limit_minutes * 60 if time_limit_minutes else None,
        generator_spec={
            "categories": categories,
            "difficulties": difficulties,
            "types": types,
            "provenance": provenance,
            "company": company,
            "count": count,
        },
        description=f"Custom test: {len(ids)} questions.",
    )
    db.add(test)
    await db.flush()
    for pos, qid in enumerate(ids):
        db.add(TestItem(test_id=test.id, position=pos, question_id=qid))
    await db.commit()
    return test


# --- attempts --------------------------------------------------------------------------------------------


async def start_attempt(db: AsyncSession, user_id: uuid.UUID, test_id: uuid.UUID) -> Attempt:
    test = await get_test(db, user_id, test_id)
    items = list(
        await db.execute(
            select(TestItem, Question.current_version_id)
            .join(Question, Question.id == TestItem.question_id)
            .where(TestItem.test_id == test.id, visible_questions(user_id))
            .order_by(TestItem.position)
        )
    )
    if not items:
        raise ProblemError(422, "This test has no questions available to you")
    order = list(range(len(items)))
    if test.shuffle:
        random.shuffle(order)
    now = utcnow()
    attempt = Attempt(
        user_id=user_id,
        test_id=test.id,
        mode=test.mode,
        started_at=now,
        deadline_at=now + timedelta(seconds=test.time_limit_s) if test.time_limit_s else None,
    )
    db.add(attempt)
    await db.flush()
    for pos, idx in enumerate(order):
        item, version_id = items[idx]
        db.add(
            AttemptAnswer(
                attempt_id=attempt.id,
                position=pos,
                question_id=item.question_id,
                question_version_id=version_id,
                points=item.points,
            )
        )
    await db.commit()
    return attempt


async def get_attempt(db: AsyncSession, user_id: uuid.UUID, attempt_id: uuid.UUID) -> Attempt:
    attempt = await db.scalar(select(Attempt).where(Attempt.id == attempt_id, Attempt.user_id == user_id))
    if attempt is None:
        raise not_found("Attempt")
    if (
        attempt.status == "in_progress"
        and attempt.deadline_at
        and utcnow() > attempt.deadline_at + timedelta(seconds=GRACE_SECONDS)
    ):
        await submit_attempt(db, attempt, auto=True)
    return attempt


async def attempt_rows(
    db: AsyncSession, attempt: Attempt
) -> list[tuple[AttemptAnswer, QuestionVersion, Question]]:
    rows = await db.execute(
        select(AttemptAnswer, QuestionVersion, Question)
        .join(QuestionVersion, QuestionVersion.id == AttemptAnswer.question_version_id)
        .join(Question, Question.id == AttemptAnswer.question_id)
        .where(AttemptAnswer.attempt_id == attempt.id)
        .order_by(AttemptAnswer.position)
    )
    return [(a, v, q) for a, v, q in rows.all()]


async def save_answer(
    db: AsyncSession,
    user_id: uuid.UUID,
    attempt_id: uuid.UUID,
    position: int,
    *,
    selected: list[str] | None,
    text_answer: str | None,
    flagged: bool | None,
    time_spent_ms: int,
) -> AttemptAnswer:
    attempt = await get_attempt(db, user_id, attempt_id)
    if attempt.status != "in_progress":
        raise ProblemError(
            409, "This attempt is already submitted", code="https://careerpilot.dev/problems/attempt-closed"
        )
    row = await db.execute(
        select(AttemptAnswer, QuestionVersion)
        .join(QuestionVersion, QuestionVersion.id == AttemptAnswer.question_version_id)
        .where(AttemptAnswer.attempt_id == attempt.id, AttemptAnswer.position == position)
    )
    found = row.first()
    if found is None:
        raise not_found("Question position")
    answer, version = found
    if selected is not None:
        valid = {o["id"] for o in version.options}
        unknown = [s for s in selected if s not in valid]
        if unknown:
            raise ProblemError(422, "Unknown option", f"Options {unknown} do not exist for this question")
        if QuestionType(version.type) in SINGLE_CHOICE and len(selected) > 1:
            raise ProblemError(422, "Only one option can be selected for this question")
        answer.selected = list(dict.fromkeys(selected))
    if text_answer is not None:
        answer.text_answer = text_answer[:20000]
    if flagged is not None:
        answer.flagged = flagged
    answer.time_spent_ms = min(answer.time_spent_ms + max(time_spent_ms, 0), 24 * 3600 * 1000)
    answer.answered_at = utcnow()
    await db.commit()
    return answer


def grade(answer: AttemptAnswer, version: QuestionVersion) -> None:
    qtype = QuestionType(version.type)
    if qtype in AUTO_GRADED_TYPES and version.answer_key:
        answer.is_correct = set(answer.selected or []) == set(version.answer_key)
        answer.score = answer.points if answer.is_correct else 0.0
        answer.graded_by = "key"
    else:
        answer.is_correct, answer.score, answer.graded_by = None, None, "none"


async def submit_attempt(db: AsyncSession, attempt: Attempt, *, auto: bool = False) -> Attempt:
    if attempt.status != "in_progress":
        return attempt
    score = max_score = 0.0
    for answer, version, _ in await attempt_rows(db, attempt):
        grade(answer, version)
        if answer.is_correct is not None:
            max_score += answer.points
            score += answer.score or 0.0
    attempt.status, attempt.submitted_at, attempt.auto_submitted = "submitted", utcnow(), auto
    attempt.score, attempt.max_score = score, max_score
    await db.commit()
    return attempt


async def self_grade(
    db: AsyncSession, user_id: uuid.UUID, attempt_id: uuid.UUID, position: int, correct: bool
) -> None:
    """Open-ended, coding and key-less items: the user marks their own answer after seeing the explanation."""
    attempt = await get_attempt(db, user_id, attempt_id)
    if attempt.status != "submitted":
        raise ProblemError(409, "Submit the attempt before grading your own answers")
    answer = await db.scalar(
        select(AttemptAnswer).where(
            AttemptAnswer.attempt_id == attempt.id, AttemptAnswer.position == position
        )
    )
    if answer is None:
        raise not_found("Question position")
    if answer.graded_by == "key":
        raise ProblemError(409, "This answer was graded automatically")
    previous = answer.score if answer.graded_by == "self" else None
    answer.is_correct, answer.score, answer.graded_by = correct, answer.points if correct else 0.0, "self"
    if previous is None:
        attempt.max_score = (attempt.max_score or 0.0) + answer.points
    attempt.score = (attempt.score or 0.0) - (previous or 0.0) + (answer.score or 0.0)
    await db.commit()


# --- analytics -------------------------------------------------------------------------------------------


async def user_analytics(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    graded = (
        select(AttemptAnswer.id)
        .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
        .where(
            Attempt.user_id == user_id, Attempt.status == "submitted", AttemptAnswer.is_correct.is_not(None)
        )
    )
    base = select(AttemptAnswer).where(AttemptAnswer.id.in_(graded))
    answers = list(await db.scalars(base))
    correct = sum(1 for a in answers if a.is_correct)
    timed = [a.time_spent_ms for a in answers if a.time_spent_ms > 0]

    by_cat_rows = await db.execute(
        select(
            Category.slug,
            Category.name,
            func.count(),
            func.sum(CORRECT_AS_INT),
            func.avg(AttemptAnswer.time_spent_ms),
        )
        .join(question_categories, question_categories.c.category_id == Category.id)
        .join(AttemptAnswer, AttemptAnswer.question_id == question_categories.c.question_id)
        .where(AttemptAnswer.id.in_(graded))
        .group_by(Category.slug, Category.name)
    )
    by_category: list[dict[str, Any]] = [
        {
            "slug": s,
            "name": n,
            "answered": int(t),
            "correct": int(c or 0),
            "accuracy": round(int(c or 0) / int(t), 3),
            "average_time_ms": int(avg or 0),
        }
        for s, n, t, c, avg in by_cat_rows.all()
    ]
    by_category.sort(key=lambda x: (x["accuracy"], -x["answered"]))

    by_diff_rows = await db.execute(
        select(QuestionVersion.difficulty, func.count(), func.sum(CORRECT_AS_INT))
        .join(AttemptAnswer, AttemptAnswer.question_version_id == QuestionVersion.id)
        .where(AttemptAnswer.id.in_(graded))
        .group_by(QuestionVersion.difficulty)
        .order_by(QuestionVersion.difficulty)
    )
    by_difficulty = [
        {"difficulty": d, "answered": int(t), "accuracy": round(int(c or 0) / int(t), 3)}
        for d, t, c in by_diff_rows.all()
    ]

    timeline_rows = await db.execute(
        select(
            Attempt.id,
            Attempt.submitted_at,
            Attempt.score,
            Attempt.max_score,
            Test.title,
            func.avg(QuestionVersion.difficulty),
        )
        .join(Test, Test.id == Attempt.test_id)
        .join(AttemptAnswer, AttemptAnswer.attempt_id == Attempt.id)
        .join(QuestionVersion, QuestionVersion.id == AttemptAnswer.question_version_id)
        .where(Attempt.user_id == user_id, Attempt.status == "submitted")
        .group_by(Attempt.id, Test.title)
        .order_by(Attempt.submitted_at.desc())
        .limit(30)
    )
    timeline = [
        {
            "attempt_id": str(i),
            "submitted_at": at.isoformat() if at else None,
            "title": title,
            "score_percent": round(100 * s / m, 1) if m else None,
            "average_difficulty": round(float(d or 0), 2),
        }
        for i, at, s, m, title, d in timeline_rows.all()
    ][::-1]

    mistakes_rows = await db.execute(
        select(AttemptAnswer.question_id, func.count(), func.max(QuestionVersion.stem))
        .join(QuestionVersion, QuestionVersion.id == AttemptAnswer.question_version_id)
        .where(AttemptAnswer.id.in_(graded), AttemptAnswer.is_correct.is_(False))
        .group_by(AttemptAnswer.question_id)
        .having(func.count() >= 2)
        .order_by(func.count().desc())
        .limit(20)
    )
    repeated = [
        {"question_id": str(q), "times_wrong": int(n), "stem": (stem or "")[:200]}
        for q, n, stem in mistakes_rows.all()
    ]

    gaps = [c for c in by_category if c["answered"] >= 5 and c["accuracy"] < 0.6]
    return {
        "answered": len(answers),
        "correct": correct,
        "incorrect": len(answers) - correct,
        "accuracy": round(correct / len(answers), 3) if answers else None,
        "average_response_time_ms": int(sum(timed) / len(timed)) if timed else None,
        "attempts": len(timeline),
        "by_category": by_category,
        "by_difficulty": by_difficulty,
        "timeline": timeline,
        "repeated_mistakes": repeated,
        "knowledge_gaps": gaps,
    }
