"""AI question generator (Prompt 2 §5, docs/06 §4.2).

Generated questions are stored apart from verified content: provenance `ai_generated`, private to the
requester, `unverified`. Each draft is validated (schema, key consistency, duplicates) and, when enabled,
checked by a second blind "solver" pass: if the model cannot reach its own key, the draft is discarded.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.db import utcnow
from careerpilot.core.llm import LLMProvider, LLMUnavailableError, Message, get_llm
from careerpilot.modules.assessments.models import Test, TestItem
from careerpilot.modules.content.canonical import QuestionIn
from careerpilot.modules.content.models import BackgroundJob, Provenance, QuestionType
from careerpilot.modules.content.service import create_question as store_question
from careerpilot.modules.content.service import find_duplicate
from careerpilot.modules.taxonomy.models import Category

LEVELS = {1: "beginner", 2: "intermediate", 3: "advanced", 4: "expert"}
GENERATABLE_TYPES = {
    QuestionType.MCQ_SINGLE,
    QuestionType.MCQ_MULTI,
    QuestionType.TRUE_FALSE,
    QuestionType.SCENARIO,
}


class GenerateRequest(BaseModel):
    position: str = Field(min_length=2, max_length=120, examples=["DevOps Engineer"])
    category: str = Field(min_length=2, max_length=64, description="category slug, e.g. kubernetes")
    difficulty: int = Field(default=2, ge=1, le=4)
    count: int = Field(default=5, ge=1, le=20)
    duration_minutes: int | None = Field(default=None, ge=1, le=240)
    question_type: QuestionType = QuestionType.MCQ_SINGLE
    language: str = Field(default="en", pattern="^(en|fr)$")
    self_check: bool = True


QUESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "stem": {"type": "string"},
                    "context": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 6},
                    "correct_indexes": {"type": "array", "items": {"type": "integer"}, "minItems": 1},
                    "explanation": {"type": "string"},
                    "why_others_are_wrong": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["stem", "options", "correct_indexes", "explanation"],
            },
        }
    },
    "required": ["questions"],
}

SOLVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"correct_indexes": {"type": "array", "items": {"type": "integer"}}},
    "required": ["correct_indexes"],
}

SYSTEM_PROMPT = (
    "You write accurate technical interview practice questions. Every question must have exactly the "
    "number of correct options requested, plausible distractors, and a factual explanation. Never claim a "
    "question comes from a real company's recruitment test. Output JSON only."
)

TYPE_RULES = {
    QuestionType.MCQ_SINGLE: "multiple choice with 4 options and exactly ONE correct option",
    QuestionType.MCQ_MULTI: "multiple select with 4 to 5 options and TWO OR MORE correct options",
    QuestionType.TRUE_FALSE: 'true/false: exactly the two options ["True", "False"] and one correct option',
    QuestionType.SCENARIO: (
        "a short realistic work scenario in `context`, then 4 possible actions with ONE best action"
    ),
}


def build_prompt(req: GenerateRequest, category_name: str, count: int) -> list[Message]:
    lang = "French" if req.language == "fr" else "English"
    return [
        Message("system", SYSTEM_PROMPT),
        Message(
            "user",
            f"Write {count} {LEVELS[req.difficulty]}-level questions for a {req.position} interview "
            f"about {category_name}. Format: {TYPE_RULES[req.question_type]}. "
            f"Indexes in correct_indexes are 0-based positions in options. "
            "For each wrong option, explain in why_others_are_wrong (same order as options, empty string for "
            f"correct ones). Write in {lang}. Cover different sub-topics; no two questions alike.",
        ),
    ]


def draft_to_question(draft: dict[str, Any], req: GenerateRequest, category_slug: str) -> QuestionIn:
    options = [str(o).strip() for o in draft.get("options", [])]
    if req.question_type == QuestionType.TRUE_FALSE:
        options = ["True", "False"] if req.language == "en" else ["Vrai", "Faux"]
    letters = "ABCDEF"
    correct = sorted({int(i) for i in draft.get("correct_indexes", []) if 0 <= int(i) < len(options)})
    why = draft.get("why_others_are_wrong") or []
    return QuestionIn.model_validate(
        {
            "type": req.question_type,
            "stem": str(draft.get("stem", "")).strip(),
            "context": (str(draft.get("context") or "").strip() or None),
            "options": [{"id": letters[i], "text": t} for i, t in enumerate(options)],
            "answer": [letters[i] for i in correct],
            "explanation": str(draft.get("explanation", "")).strip() or None,
            "distractor_explanations": {
                letters[i]: str(w).strip()
                for i, w in enumerate(why[: len(options)])
                if str(w).strip() and i not in correct
            },
            "difficulty": req.difficulty,
            "categories": [category_slug],
            "language": req.language,
        }
    )


async def blind_check(llm: LLMProvider, q: QuestionIn) -> bool:
    """Ask the model to answer without the key. Keep the draft only if it lands on the same key."""
    listing = "\n".join(f"{i}. {o.text}" for i, o in enumerate(q.options))
    context = f"\nContext: {q.context}" if q.context else ""
    try:
        out = await llm.structured(
            [
                Message("system", "Answer the question. Output JSON only."),
                Message(
                    "user",
                    f"Question: {q.stem}{context}\nOptions (0-based):\n{listing}\n"
                    "Return the 0-based indexes of ALL correct options.",
                ),
            ],
            SOLVE_SCHEMA,
            temperature=0.0,
        )
    except ValueError:
        return False
    ids = {q.options[int(i)].id for i in out.get("correct_indexes", []) if 0 <= int(i) < len(q.options)}
    return ids == set(q.answer or [])


async def generate(
    db: AsyncSession,
    req: GenerateRequest,
    *,
    owner_id: uuid.UUID,
    job_id: uuid.UUID | None = None,
    llm: LLMProvider | None = None,
) -> dict[str, Any]:
    llm = llm or get_llm()
    job = await db.get(BackgroundJob, job_id) if job_id else None
    if job:
        job.status, job.started_at = "running", utcnow()
        await db.commit()
    stats: dict[str, Any] = {
        "requested": req.count,
        "created": 0,
        "invalid": 0,
        "failed_self_check": 0,
        "duplicates": 0,
        "model": f"{llm.name}:{llm.model}",
    }
    try:
        category = await db.scalar(select(Category).where(Category.slug == req.category))
        if category is None or category.parent_id is None:
            raise ValueError(f"unknown category: {req.category}")
        if req.question_type not in GENERATABLE_TYPES:
            raise ValueError(f"the generator cannot produce {req.question_type.value} questions yet")
        created_ids: list[uuid.UUID] = []
        for _round in range(2):  # one retry round to replace rejected drafts
            missing = req.count - len(created_ids)
            if missing <= 0:
                break
            data = await llm.structured(build_prompt(req, category.name, missing + 1), QUESTION_SCHEMA)
            for draft in data.get("questions", [])[: missing + 1]:
                if len(created_ids) >= req.count:
                    break
                try:
                    q = draft_to_question(draft, req, category.slug)
                except (ValidationError, ValueError, TypeError):
                    stats["invalid"] += 1
                    continue
                if not q.answer:
                    stats["invalid"] += 1
                    continue
                if await find_duplicate(db, q, owner_id):
                    stats["duplicates"] += 1
                    continue
                if req.self_check and not await blind_check(llm, q):
                    stats["failed_self_check"] += 1
                    continue
                question = await store_question(
                    db,
                    q,
                    provenance=Provenance.AI_GENERATED,
                    category_ids=[category.id],
                    owner_id=owner_id,
                    visibility="private",
                    status="published",
                    label="AI-generated practice question. Unverified: it may contain errors.",
                )
                created_ids.append(question.id)
        stats["created"] = len(created_ids)
        test_id = None
        if created_ids:
            test = Test(
                title=f"{category.name} · {LEVELS[req.difficulty]} · AI practice",
                description=f"Generated for a {req.position} profile. AI-generated and unverified.",
                owner_id=owner_id,
                visibility="private",
                mode="practice",
                kind="generated",
                time_limit_s=req.duration_minutes * 60 if req.duration_minutes else None,
                generator_spec=req.model_dump(mode="json"),
                label="AI-generated practice test",
            )
            db.add(test)
            await db.flush()
            for pos, qid in enumerate(created_ids):
                db.add(TestItem(test_id=test.id, position=pos, question_id=qid))
            test_id = test.id
        stats["test_id"] = str(test_id) if test_id else None
        if job:
            job.status, job.result, job.finished_at = "succeeded", stats, utcnow()
        await db.commit()
        return stats
    except (LLMUnavailableError, ValueError) as exc:
        await db.rollback()
        if job:
            job = await db.get(BackgroundJob, job_id)
            assert job is not None
            job.status, job.error, job.result, job.finished_at = "failed", str(exc), stats, utcnow()
            await db.commit()
            return stats
        raise
