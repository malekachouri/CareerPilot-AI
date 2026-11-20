"""Personalisation: Elo-style rating per topic and adaptive question selection (docs/06 §4.6).

Questions have a nominal rating from their difficulty (beginner 1000 … expert 1600). After each graded answer,
the user's rating in each of the question's topics moves towards the outcome. The next question targets the
difficulty the user is expected to answer correctly ~60-70% of the time, in their weakest topics first.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.db import utcnow
from careerpilot.modules.assessments.models import Attempt, AttemptAnswer
from careerpilot.modules.coach.models import CoachMessage, CoachSession, LearnerProfile, SkillRating
from careerpilot.modules.content.models import Question, QuestionVersion, question_categories
from careerpilot.modules.taxonomy.models import Category

START = 1000.0


def question_rating(difficulty: int) -> float:
    return 800.0 + 200.0 * max(1, min(4, difficulty))


def expected(user: float, question: float) -> float:
    return 1.0 / (1.0 + 10 ** ((question - user) / 400.0))


def k_factor(answered: int, weight: float) -> float:
    return max(12.0, 40.0 / (1.0 + answered / 20.0)) * weight


def target_difficulty(rating: float, shift: int = 0) -> int:
    """Difficulty whose expected success is ~65%: rating - 110 ≈ question rating."""
    return max(1, min(4, round((rating - 110.0 - 800.0) / 200.0) + shift))


async def update_ratings(
    db: AsyncSession,
    user_id: uuid.UUID,
    question_id: uuid.UUID,
    difficulty: int,
    outcome: float,
    *,
    weight: float = 1.0,
) -> None:
    """`outcome` is 1/0 for keyed answers, a 0..1 score for open answers (with a lower weight)."""
    cat_ids = list(
        await db.scalars(
            select(question_categories.c.category_id).where(question_categories.c.question_id == question_id)
        )
    )
    for cat_id in cat_ids:
        current = await db.get(SkillRating, (user_id, cat_id))
        if current is None:
            await db.execute(
                pg_insert(SkillRating)
                .values(user_id=user_id, category_id=cat_id, rating=START, answered=0, correct=0.0)
                .on_conflict_do_nothing()
            )
            current = await db.get(SkillRating, (user_id, cat_id))
            assert current is not None
        e = expected(current.rating, question_rating(difficulty))
        current.rating += k_factor(current.answered, weight) * (outcome - e)
        current.answered += 1
        current.correct += outcome
        current.last_at = utcnow()
    await db.flush()


@dataclass(frozen=True)
class TopicSkill:
    slug: str
    name: str
    rating: float
    answered: int
    accuracy: float | None


async def user_skills(db: AsyncSession, user_id: uuid.UUID) -> list[TopicSkill]:
    rows = await db.execute(
        select(SkillRating, Category)
        .join(Category, Category.id == SkillRating.category_id)
        .where(SkillRating.user_id == user_id)
    )
    out = [
        TopicSkill(
            c.slug,
            c.name,
            round(r.rating, 1),
            r.answered,
            round(r.correct / r.answered, 3) if r.answered else None,
        )
        for r, c in rows.all()
    ]
    return sorted(out, key=lambda s: s.rating)


async def get_profile(db: AsyncSession, user_id: uuid.UUID) -> LearnerProfile:
    profile = await db.get(LearnerProfile, user_id)
    if profile is None:
        profile = LearnerProfile(user_id=user_id, focus_categories=[])
        db.add(profile)
        await db.flush()
    return profile


async def recently_seen(db: AsyncSession, user_id: uuid.UUID, limit: int = 300) -> set[uuid.UUID]:
    from_tests = (
        select(AttemptAnswer.question_id)
        .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
        .where(Attempt.user_id == user_id)
        .order_by(AttemptAnswer.answered_at.desc().nulls_last())
        .limit(limit)
    )
    seen = set(await db.scalars(from_tests))
    coach = await db.scalars(
        select(CoachMessage.data["question_id"].astext)
        .join(CoachSession, CoachSession.id == CoachMessage.session_id)
        .where(
            CoachSession.user_id == user_id,
            CoachMessage.kind == "question",
            CoachMessage.data["question_id"].astext.is_not(None),
        )
        .order_by(CoachMessage.created_at.desc(), CoachMessage.id.desc())
        .limit(limit)
    )
    seen |= {uuid.UUID(q) for q in coach if q}
    return seen


async def pick_question(
    db: AsyncSession,
    user_id: uuid.UUID,
    categories: tuple[str, ...] | list[str],
    *,
    shift: int = 0,
    open_only: bool = False,
    rng: random.Random | None = None,
) -> tuple[Question, QuestionVersion, dict[str, Any]] | None:
    """Adaptive pick inside the agent's topics. Returns the question and why it was chosen."""
    rng = rng or random.Random()  # noqa: S311 - not security sensitive
    skills = {s.slug: s for s in await user_skills(db, user_id)}
    profile = await get_profile(db, user_id)
    topics = list(categories)
    # Weakest first (unknown topics count as the starting rating), profile focus breaks ties.
    topics.sort(
        key=lambda t: (skills[t].rating if t in skills else START, t not in (profile.focus_categories or []))
    )
    seen = await recently_seen(db, user_id)
    for topic in topics[:6]:
        rating = skills[topic].rating if topic in skills else START
        target = target_difficulty(rating, shift)
        stmt = (
            select(Question, QuestionVersion)
            .join(QuestionVersion, QuestionVersion.id == Question.current_version_id)
            .join(question_categories, question_categories.c.question_id == Question.id)
            .join(Category, Category.id == question_categories.c.category_id)
            .where(
                Category.slug == topic,
                Question.status == "published",
                or_(Question.visibility == "public", Question.owner_id == user_id),
                Question.id.not_in(seen) if seen else and_(True),
                QuestionVersion.type != "survey" if topic != "personality" else and_(True),
                func.abs(QuestionVersion.difficulty - target) <= 1,
            )
        )
        if open_only:
            stmt = stmt.where(QuestionVersion.type.in_(["open_ended", "coding", "debugging"]))
        else:
            # Keyed questions, or open ones (evaluated by the model).
            stmt = stmt.where(
                or_(
                    QuestionVersion.answer_key.is_not(None),
                    QuestionVersion.type.in_(["open_ended", "coding", "debugging", "survey"]),
                )
            )
        candidates = list((await db.execute(stmt.limit(200))).all())
        if not candidates:
            continue
        exact = [c for c in candidates if c[1].difficulty == target]
        q, v = rng.choice(exact or candidates)
        return (
            q,
            v,
            {
                "topic": topic,
                "rating": round(rating),
                "target_difficulty": target,
                "reason": "weakest topic" if topic in skills else "new topic",
            },
        )
    return None
