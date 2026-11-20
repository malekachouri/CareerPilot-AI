"""Coach workflow (Prompt 3 §1 and §3). Deterministic state machine; the model is only called for content.

Practice session:  present question → (hint / learning-mode reveal / ask the tutor) → answer → evaluation
                   (+ AI insight) → recommendation → next adaptive question or similar exercise.
Interview session: question → answer → hidden evaluation → follow-up or next question → … → report.

Every model call runs in a background job attached to a `pending` coach message (local models on a CPU can
take a minute); the UI polls the session. Without a model, keyed questions still work end to end.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.db import utcnow
from careerpilot.core.errors import ProblemError
from careerpilot.core.jobs import enqueue
from careerpilot.core.llm import LLMProvider, LLMTimeoutError, LLMUnavailableError, get_llm
from careerpilot.modules.coach import evaluation as ev
from careerpilot.modules.coach.agents import AGENTS, PERSONAS, Agent
from careerpilot.modules.coach.models import CoachExplanation, CoachMessage, CoachSession, SkillRating
from careerpilot.modules.coach.ratings import (
    get_profile,
    pick_question,
    target_difficulty,
    update_ratings,
    user_skills,
)
from careerpilot.modules.content.api import PROVENANCE_LABELS, question_details
from careerpilot.modules.content.models import (
    AUTO_GRADED_TYPES,
    Question,
    QuestionType,
    QuestionVersion,
    Source,
)
from careerpilot.modules.kb import service as kb
from careerpilot.modules.taxonomy.models import Category

OPEN_TYPES = {"open_ended", "coding", "debugging", "simulation"}
DEFAULT_SECONDS = {1: 60, 2: 90, 3: 120, 4: 150}
LEVELS = {1: "Beginner", 2: "Intermediate", 3: "Advanced", 4: "Expert"}


def not_found(what: str) -> ProblemError:
    return ProblemError(404, f"{what} not found", code="https://careerpilot.dev/problems/not-found")


def agent_of(session: CoachSession) -> Agent:
    return AGENTS[session.agent]


async def add_message(
    db: AsyncSession,
    session: CoachSession,
    *,
    role: str,
    kind: str,
    content: str = "",
    data: dict[str, Any] | None = None,
    job: dict[str, Any] | None = None,
) -> CoachMessage:
    # Application clock (µs): messages written in one transaction would otherwise share Postgres now().
    msg = CoachMessage(
        session_id=session.id,
        role=role,
        kind=kind,
        content=content,
        data=data or {},
        status="pending" if job else "done",
        created_at=utcnow(),
    )
    if job:
        msg.data = {**msg.data, "job": job}
    db.add(msg)
    session.updated_at = utcnow()
    await db.flush()
    return msg


def _queue(db: AsyncSession, msg: CoachMessage) -> None:
    """Jobs are sent only after the transaction commits, so the worker always finds the message."""
    db.info.setdefault("coach_jobs", []).append(str(msg.id))


async def commit(db: AsyncSession) -> None:
    await db.commit()
    jobs, db.info["coach_jobs"] = db.info.get("coach_jobs", []), []
    for message_id in jobs:
        await enqueue("coach.process", message_id=message_id)


def _busy(session: CoachSession) -> bool:
    return bool(session.state.get("pending"))


# --- sessions --------------------------------------------------------------------------------------------


async def start_practice(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    agent_slug: str,
    learning_mode: bool,
    question_id: uuid.UUID | None = None,
    topic: str | None = None,
) -> CoachSession:
    agent = AGENTS.get(agent_slug)
    if agent is None:
        raise ProblemError(422, "Unknown agent", f"Available: {', '.join(AGENTS)}")
    session = CoachSession(
        user_id=user_id,
        kind="practice",
        agent=agent.slug,
        title=agent.name,
        learning_mode=learning_mode,
        state={"asked": [], "topic": topic},
    )
    db.add(session)
    await db.flush()
    await add_message(
        db,
        session,
        role="coach",
        kind="notice",
        content=f"{agent.name}: {agent.description}"
        + (f"\n\n{agent.disclaimer}" if agent.disclaimer else ""),
    )
    if question_id:
        q = await db.scalar(
            select(Question).where(Question.id == question_id, Question.status == "published")
        )
        if q is None or not (q.visibility == "public" or q.owner_id == user_id):
            raise not_found("Question")
        v = await db.get(QuestionVersion, q.current_version_id)
        assert v is not None
        await present_bank_question(db, session, q, v, {"reason": "chosen by you"})
    else:
        await next_question(db, session)
    await commit(db)
    return session


async def start_interview(
    db: AsyncSession, user_id: uuid.UUID, *, persona_slug: str, duration_minutes: int | None
) -> CoachSession:
    persona = PERSONAS.get(persona_slug)
    if persona is None:
        raise ProblemError(422, "Unknown interview type", f"Available: {', '.join(PERSONAS)}")
    profile = await get_profile(db, user_id)
    minutes = duration_minutes or profile.interview_minutes
    total = max(3, min(10, minutes // 6))
    session = CoachSession(
        user_id=user_id,
        kind="interview",
        agent=persona.agent,
        persona=persona.slug,
        title=persona.name,
        state={
            "interview": {"total": total, "main_asked": 0, "follow_ups": 0, "turns": []},
            "asked": [],
            "minutes": minutes,
        },
    )
    db.add(session)
    await db.flush()
    await add_message(
        db,
        session,
        role="coach",
        kind="notice",
        content=f"{persona.name} · about {minutes} minutes, {total} main questions. {persona.description} "
        "Answer as you would in the real interview. The detailed report comes at the end.",
    )
    msg = await add_message(db, session, role="coach", kind="question", job={"type": "interview_question"})
    session.state = {**session.state, "pending": str(msg.id)}
    _queue(db, msg)
    await commit(db)
    return session


async def get_session(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID) -> CoachSession:
    s = await db.scalar(
        select(CoachSession).where(CoachSession.id == session_id, CoachSession.user_id == user_id)
    )
    if s is None:
        raise not_found("Session")
    return s


# --- STEP 1: present a question --------------------------------------------------------------------------


async def present_bank_question(
    db: AsyncSession, session: CoachSession, q: Question, v: QuestionVersion, selection: dict[str, Any]
) -> CoachMessage:
    details = (await question_details(db, [q.id]))[q.id]
    source = await db.get(Source, q.source_id) if q.source_id else None
    seconds = v.time_limit_s or (600 if v.type in OPEN_TYPES else DEFAULT_SECONDS.get(v.difficulty, 90))
    current = {
        "source": "bank",
        "question_id": str(q.id),
        "version_id": str(v.id),
        "type": v.type,
        "topic": selection.get("topic")
        or (details["categories"][0]["slug"] if details["categories"] else None),
        "difficulty": v.difficulty,
        "hints": 0,
        "revealed": False,
        "categories": [c["slug"] for c in details["categories"]],
    }
    data = {
        "question_id": str(q.id),
        "question": {"stem": v.stem, "context": v.context, "options": v.options, "type": v.type},
        "skills": details["categories"],
        "difficulty": v.difficulty,
        "difficulty_label": LEVELS[v.difficulty],
        "recommended_time_s": seconds,
        "provenance": q.provenance,
        "provenance_label": PROVENANCE_LABELS.get(q.provenance, q.provenance),
        "label": q.label,
        "source": {"name": source.name, "url": source.url, "license": source.license_spdx}
        if source and source.kind != "upload"
        else None,
        "answer_format": "code" if v.type in ("coding", "debugging") else "choice" if v.options else "text",
        "selection": selection,
        "auto_graded": QuestionType(v.type) in AUTO_GRADED_TYPES and bool(v.answer_key),
    }
    msg = await add_message(db, session, role="coach", kind="question", content=v.stem, data=data)
    session.state = {
        **session.state,
        "current": {**current, "message_id": str(msg.id)},
        "step": "awaiting_answer",
        "asked": [*session.state.get("asked", []), v.stem][-30:],
    }
    return msg


async def next_question(db: AsyncSession, session: CoachSession) -> CoachMessage:
    """Adaptive next question: from the bank (weakest topic, target difficulty), else generated."""
    if _busy(session):
        raise ProblemError(409, "The coach is still working on the previous step")
    agent = agent_of(session)
    topics = tuple([session.state["topic"]]) if session.state.get("topic") else agent.categories
    picked = None
    if not agent.prefers_open or len(session.state.get("asked", [])) % 3 == 2:
        picked = await pick_question(db, session.user_id, topics)
    if picked:
        q, v, why = picked
        return await present_bank_question(db, session, q, v, why)
    # Nothing suitable in the bank (or an open-problem agent): ask the model for an open problem.
    skills = {s.slug: s for s in await user_skills(db, session.user_id)}
    topic = sorted(topics, key=lambda t: skills[t].rating if t in skills else 1000.0)[0]
    difficulty = target_difficulty(skills[topic].rating if topic in skills else 1000.0)
    msg = await add_message(
        db,
        session,
        role="coach",
        kind="question",
        job={"type": "generate_question", "topic": topic, "difficulty": difficulty},
    )
    session.state = {**session.state, "pending": str(msg.id), "step": "waiting"}
    await db.flush()
    _queue(db, msg)
    return msg


# --- STEP 3/4: answer and evaluate -----------------------------------------------------------------------


async def submit_answer(
    db: AsyncSession,
    session: CoachSession,
    *,
    selected: list[str] | None,
    text: str | None,
    language: str | None,
) -> list[CoachMessage]:
    if session.status != "active":
        raise ProblemError(409, "This session has ended")
    if _busy(session):
        raise ProblemError(409, "The coach is still working on the previous step")
    if session.kind == "interview":
        return [await _interview_answer(db, session, text or "")]
    cur = session.state.get("current")
    if not cur or session.state.get("step") != "awaiting_answer":
        raise ProblemError(409, "There is no question waiting for an answer", "Ask for the next question.")
    answer_msg = await add_message(
        db,
        session,
        role="user",
        kind="answer",
        content=text or ", ".join(selected or []),
        data={
            "selected": selected,
            "text": text,
            "language": language,
            "question_id": cur.get("question_id"),
        },
    )
    out = [answer_msg]
    if cur["source"] == "bank" and cur["type"] not in OPEN_TYPES and cur["type"] != "survey":
        out += await _evaluate_closed(db, session, cur, selected or [], revealed=False)
    elif cur["type"] == "survey":
        out.append(
            await add_message(
                db,
                session,
                role="coach",
                kind="evaluation",
                data={"reflection": True, "disclaimer": AGENTS["psychometric"].disclaimer},
                content="Thanks. There is no right or wrong answer here. Ask yourself: what does "
                "this preference say about the teams and roles where you do your best work?",
            )
        )
        session.state = {**session.state, "step": "evaluated"}
    else:
        if not (text or "").strip():
            raise ProblemError(422, "Write an answer first")
        msg = await add_message(db, session, role="coach", kind="evaluation", job={"type": "evaluate_open"})
        session.state = {**session.state, "pending": str(msg.id), "step": "waiting"}
        out.append(msg)
        await db.flush()
        _queue(db, msg)
    await commit(db)
    return out


async def reveal(db: AsyncSession, session: CoachSession) -> list[CoachMessage]:
    """Learning mode: show the answer and explanation before answering (not counted in the ratings)."""
    if not session.learning_mode:
        raise ProblemError(
            403,
            "Learning mode is off for this session",
            "Start a session in learning mode to see answers before submitting.",
        )
    cur = session.state.get("current")
    if not cur or session.state.get("step") != "awaiting_answer":
        raise ProblemError(409, "There is no question waiting for an answer")
    if cur["source"] != "bank" or cur["type"] in OPEN_TYPES or cur["type"] == "survey":
        msg = await add_message(
            db,
            session,
            role="coach",
            kind="evaluation",
            data={"revealed": True},
            content="Model answer:\n" + (cur.get("reference_answer") or "No reference answer stored."),
        )
        session.state = {**session.state, "step": "evaluated"}
        await commit(db)
        return [msg]
    out = await _evaluate_closed(db, session, cur, [], revealed=True)
    await commit(db)
    return out


async def _evaluate_closed(
    db: AsyncSession, session: CoachSession, cur: dict[str, Any], selected: list[str], *, revealed: bool
) -> list[CoachMessage]:
    v = await db.get(QuestionVersion, uuid.UUID(cur["version_id"]))
    assert v is not None
    result = ev.grade_choice(v, selected)
    texts = {o["id"]: o["text"] for o in v.options}
    data = {
        **result,
        "revealed": revealed,
        "selected": selected,
        "correct_options": [{"id": i, "text": texts.get(i, i)} for i in result["correct_options"]],
        "explanation": v.explanation,
        "why_wrong": v.distractor_explanations or {},
        "hints_used": cur.get("hints", 0),
    }
    if result["is_correct"] is None:
        content = "There is no answer key for this question yet. Compare with your notes or the explanation."
    elif revealed:
        content = "Learning mode: here is the answer."
    else:
        content = "Correct!" if result["is_correct"] else "Not quite."
    msgs = [await add_message(db, session, role="coach", kind="evaluation", content=content, data=data)]
    if result["is_correct"] is not None and not revealed:
        # Hints make a correct answer worth less in the rating.
        weight = 1.0 if cur.get("hints", 0) == 0 else 0.5
        await update_ratings(
            db,
            session.user_id,
            uuid.UUID(cur["question_id"]),
            v.difficulty,
            1.0 if result["is_correct"] else 0.0,
            weight=weight,
        )
    if v.answer_key:
        cached = await db.get(CoachExplanation, v.id)
        # A short (compact-mode) explanation is not reused once the full mode is back on.
        if cached and (cached.prompt_version == ev.prompt_version() or ev.is_compact()):
            msgs.append(await add_message(db, session, role="coach", kind="insight", data=cached.data))
        else:
            insight = await add_message(
                db, session, role="coach", kind="insight", job={"type": "enrich", "version_id": str(v.id)}
            )
            msgs.append(insight)
            await db.flush()
            _queue(db, insight)
    msgs.append(await recommendation(db, session, cur, result.get("is_correct")))
    session.state = {**session.state, "step": "evaluated"}
    return msgs


# --- STEP 5: learning recommendation ---------------------------------------------------------------------


async def recommendation(
    db: AsyncSession, session: CoachSession, cur: dict[str, Any], correct: bool | None
) -> CoachMessage:
    skills = await user_skills(db, session.user_id)
    agent = agent_of(session)
    in_scope = [s for s in skills if s.slug in agent.categories and s.answered > 0]
    # Only topics that are actually weak: below the starting rating or under 80 % accuracy.
    weak = [
        {"slug": s.slug, "name": s.name, "rating": round(s.rating), "accuracy": s.accuracy}
        for s in in_scope
        if s.rating < 1000 or (s.accuracy is not None and s.accuracy < 0.8)
    ][:3]
    topic: str | None = cur.get("topic") or (str(weak[0]["slug"]) if weak else None)
    lesson = None
    if topic:
        name = await db.scalar(select(Category.name).where(Category.slug == topic)) or topic
        stem = cur.get("stem") or ""
        if not stem and cur.get("version_id"):
            v = await db.get(QuestionVersion, uuid.UUID(cur["version_id"]))
            stem = v.stem if v else ""
        passages = await kb.search(db, f"{name} {stem}", user_id=session.user_id, k=6, categories=[topic])
        # A lesson is study material (notes, documentation, your uploads), never the question itself.
        notes = [p for p in passages if p.kind in ("note", "doc", "upload")]
        if notes:
            lesson = notes[0].reference()
    rating = next((s.rating for s in skills if s.slug == topic), 1000.0)
    data = {
        "weak_topics": weak,
        "lesson": lesson,
        "topic": topic,
        "next_difficulty": target_difficulty(rating),
        "next_difficulty_label": LEVELS[target_difficulty(rating)],
    }
    if correct is False:
        text = "Review the explanation, then try a similar exercise to lock it in."
    elif correct:
        text = "Well done. The next question adapts to your level."
    else:
        text = "Next: a similar exercise or the next adaptive question."
    return await add_message(db, session, role="coach", kind="recommendation", content=text, data=data)


# --- helpers: hint, tutor chat, similar, end -------------------------------------------------------------


async def request_hint(db: AsyncSession, session: CoachSession) -> CoachMessage:
    cur = session.state.get("current")
    if (
        session.kind != "practice"
        or not cur
        or session.state.get("step") != "awaiting_answer"
        or _busy(session)
    ):
        raise ProblemError(409, "Hints are available while a question is waiting for your answer")
    level = min(3, int(cur.get("hints", 0)) + 1)
    session.state = {**session.state, "current": {**cur, "hints": level}}
    msg = await add_message(db, session, role="coach", kind="hint", job={"type": "hint", "level": level})
    _queue(db, msg)
    await commit(db)
    return msg


async def ask_tutor(db: AsyncSession, session: CoachSession, message: str) -> list[CoachMessage]:
    if _busy(session):
        raise ProblemError(409, "The coach is still working on the previous step")
    user = await add_message(db, session, role="user", kind="chat", content=message[:4000])
    reply = await add_message(
        db, session, role="coach", kind="chat", job={"type": "chat", "message": message[:4000]}
    )
    _queue(db, reply)
    await commit(db)
    return [user, reply]


async def similar_exercise(db: AsyncSession, session: CoachSession) -> CoachMessage:
    cur = session.state.get("current")
    if session.kind != "practice" or not cur or _busy(session):
        raise ProblemError(409, "No question to build a similar exercise from")
    msg = await add_message(db, session, role="coach", kind="question", job={"type": "similar"})
    session.state = {**session.state, "pending": str(msg.id), "step": "waiting"}
    _queue(db, msg)
    await commit(db)
    return msg


async def end_session(db: AsyncSession, session: CoachSession) -> CoachSession:
    if session.status == "ended":
        return session
    turns = session.state.get("interview", {}).get("turns", [])
    if session.kind == "interview" and turns and not _busy(session):
        msg = await add_message(db, session, role="coach", kind="report", job={"type": "report"})
        session.state = {**session.state, "pending": str(msg.id)}
        _queue(db, msg)
        await commit(db)
        return session
    session.status, session.ended_at = "ended", utcnow()
    await commit(db)
    return session


# --- interviews ------------------------------------------------------------------------------------------


async def _interview_answer(db: AsyncSession, session: CoachSession, text: str) -> CoachMessage:
    if not text.strip():
        raise ProblemError(422, "Write an answer first")
    if not session.state.get("interview", {}).get("current_question"):
        raise ProblemError(409, "Wait for the interviewer's question")
    await add_message(
        db, session, role="user", kind="answer", content=text[:12000], data={"text": text[:12000]}
    )
    msg = await add_message(
        db, session, role="coach", kind="question", job={"type": "interview_turn", "answer": text[:12000]}
    )
    session.state = {**session.state, "pending": str(msg.id)}
    _queue(db, msg)
    await commit(db)
    return msg


def criterion_averages(turns: list[dict[str, Any]]) -> dict[str, float]:
    sums: dict[str, list[int]] = {}
    for t in turns:
        for c in t.get("criteria", []):
            sums.setdefault(c["label"], []).append(int(c["score"]))
    return {k: round(sum(v) / len(v), 1) for k, v in sums.items()}


# --- background job runner -------------------------------------------------------------------------------


async def run_job(db: AsyncSession, message_id: uuid.UUID, llm: LLMProvider | None = None) -> None:
    msg = await db.get(CoachMessage, message_id)
    if msg is None or msg.status != "pending":
        return
    session = await db.get(CoachSession, msg.session_id)
    assert session is not None
    llm = llm or get_llm()
    job = dict(msg.data.get("job") or {})
    try:
        await _JOBS[job["type"]](db, session, msg, job, llm)
        msg.status = "done"
    except (LLMUnavailableError, ValueError, KeyError) as exc:
        msg.status = "failed"
        if isinstance(exc, LLMTimeoutError):
            msg.content = (
                f"The local model took too long ({exc}). This almost always means there is not enough "
                "free memory and the model is swapping to disk. Close other applications, give Docker/WSL "
                "more RAM, or use a smaller model (LLM_MODEL=qwen3:1.7b in .env), then retry."
            )
        elif isinstance(exc, LLMUnavailableError):
            msg.content = (
                "The local AI model is not available. Start the `ai` profile and pull the model, then retry."
            )
        else:
            msg.content = f"The coach could not complete this step: {exc}"
        msg.data = {**msg.data, "error": str(exc)[:500]}
        if session.state.get("step") == "waiting":
            session.state = {
                **session.state,
                "step": "awaiting_answer" if session.state.get("current") else "idle",
            }
    if session.state.get("pending") == str(msg.id):
        session.state = {k: v for k, v in session.state.items() if k != "pending"}
    session.updated_at = utcnow()
    await commit(db)


async def retry(db: AsyncSession, session: CoachSession, message_id: uuid.UUID) -> CoachMessage:
    msg = await db.get(CoachMessage, message_id)
    if msg is None or msg.session_id != session.id or msg.status != "failed" or not msg.data.get("job"):
        raise not_found("Failed step")
    msg.status, msg.content = "pending", ""
    msg.data = {k: v for k, v in msg.data.items() if k != "error"}
    if msg.data["job"]["type"] in (
        "generate_question",
        "similar",
        "interview_question",
        "interview_turn",
        "report",
        "evaluate_open",
    ):
        session.state = {**session.state, "pending": str(msg.id)}
    _queue(db, msg)
    await commit(db)
    return msg


def _current_question_text(session: CoachSession, v: QuestionVersion | None) -> str:
    cur = session.state.get("current") or {}
    if v is not None:
        return ev.question_text(v)
    ctx = f"Context:\n{cur['context']}\n\n" if cur.get("context") else ""
    return f"{ctx}Question: {cur.get('stem', '')}"


async def _current_version(db: AsyncSession, session: CoachSession) -> QuestionVersion | None:
    cur = session.state.get("current") or {}
    return await db.get(QuestionVersion, uuid.UUID(cur["version_id"])) if cur.get("version_id") else None


async def _job_enrich(
    db: AsyncSession, session: CoachSession, msg: CoachMessage, job: dict[str, Any], llm: LLMProvider
) -> None:
    v = await db.get(QuestionVersion, uuid.UUID(job["version_id"]))
    assert v is not None
    # Never cite the question's own explanation as evidence for itself.
    passages = await kb.search(db, v.stem, user_id=session.user_id, k=4, exclude_question_id=v.question_id)
    data = await ev.enrich_closed(llm, agent_of(session), v, passages)
    if data is None:
        msg.content = (
            "The AI explanation disagreed with the answer key and was discarded. "
            "The stored explanation applies."
        )
        msg.data = {"discarded": True}
        return
    # merge: replaces a short compact-mode explanation when the full mode regenerates it.
    await db.merge(
        CoachExplanation(
            question_version_id=v.id,
            data=data,
            model=f"{llm.name}:{llm.model}",
            prompt_version=ev.prompt_version(),
        )
    )
    msg.data = data


async def _job_evaluate_open(
    db: AsyncSession, session: CoachSession, msg: CoachMessage, job: dict[str, Any], llm: LLMProvider
) -> None:
    cur = session.state.get("current") or {}
    v = await _current_version(db, session)
    answer = await db.scalar(
        select(CoachMessage)
        .where(CoachMessage.session_id == session.id, CoachMessage.kind == "answer")
        .order_by(CoachMessage.created_at.desc(), CoachMessage.id.desc())
    )
    assert answer is not None
    text = answer.data.get("text") or answer.content
    question = _current_question_text(session, v)
    passages = await kb.search(db, f"{cur.get('stem', '')} {text[:400]}", user_id=session.user_id, k=4)
    agent = agent_of(session)
    result = await ev.evaluate_open(
        llm,
        agent,
        question=question,
        answer=text,
        reference=(v.explanation if v else cur.get("reference_answer")),
        passages=passages,
        code=cur.get("type") in ("coding", "debugging") or agent.answer_format == "code",
        language=answer.data.get("language"),
    )
    msg.content = result["feedback"]
    msg.data = result
    outcome = result["score"] / 100
    if cur.get("question_id") and v is not None:
        await update_ratings(
            db, session.user_id, uuid.UUID(cur["question_id"]), v.difficulty, outcome, weight=0.5
        )
    elif cur.get("topic"):
        cat = await db.scalar(select(Category).where(Category.slug == cur["topic"]))
        if cat:
            await _update_topic(db, session.user_id, cat.id, int(cur.get("difficulty", 2)), outcome)
    correct = True if result["score"] >= 75 else False if result["score"] < 45 else None
    await recommendation(db, session, cur, correct)
    session.state = {**session.state, "step": "evaluated"}


async def _update_topic(
    db: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID, difficulty: int, outcome: float
) -> None:
    from careerpilot.modules.coach.ratings import START, expected, k_factor, question_rating

    r = await db.get(SkillRating, (user_id, category_id))
    if r is None:
        r = SkillRating(user_id=user_id, category_id=category_id, rating=START, answered=0, correct=0.0)
        db.add(r)
    r.rating += k_factor(r.answered, 0.5) * (outcome - expected(r.rating, question_rating(difficulty)))
    r.answered += 1
    r.correct += outcome
    r.last_at = utcnow()


async def _present_generated(
    db: AsyncSession,
    session: CoachSession,
    msg: CoachMessage,
    problem: dict[str, Any],
    topic: str,
    difficulty: int,
) -> None:
    agent = agent_of(session)
    cat = await db.scalar(select(Category).where(Category.slug == topic))
    qtype = "coding" if agent.answer_format == "code" else "open_ended"
    msg.content = problem["question"]
    msg.data = {
        "question": {
            "stem": problem["question"],
            "context": problem.get("context"),
            "options": [],
            "type": qtype,
        },
        "skills": [{"slug": topic, "name": cat.name if cat else topic}],
        "difficulty": difficulty,
        "difficulty_label": LEVELS[difficulty],
        "recommended_time_s": problem["recommended_minutes"] * 60,
        "provenance": "ai_generated",
        "provenance_label": PROVENANCE_LABELS["ai_generated"],
        "label": "AI-generated practice question. Unverified: it may contain errors.",
        "answer_format": "code" if qtype == "coding" else "text",
        "starter_code": problem.get("starter_code"),
        "selection": {
            "topic": topic,
            "target_difficulty": difficulty,
            "reason": "generated for your weakest topic",
        },
        "auto_graded": False,
    }
    session.state = {
        **session.state,
        "step": "awaiting_answer",
        "asked": [*session.state.get("asked", []), problem["question"]][-30:],
        "current": {
            "source": "generated",
            "type": qtype,
            "topic": topic,
            "difficulty": difficulty,
            "hints": 0,
            "stem": problem["question"],
            "context": problem.get("context"),
            "reference_answer": problem.get("reference_answer"),
            "message_id": str(msg.id),
        },
    }


async def _job_generate_question(
    db: AsyncSession, session: CoachSession, msg: CoachMessage, job: dict[str, Any], llm: LLMProvider
) -> None:
    profile = await get_profile(db, session.user_id)
    name = await db.scalar(select(Category.name).where(Category.slug == job["topic"])) or job["topic"]
    problem = await ev.generate_open_problem(
        llm,
        agent_of(session),
        topic=name,
        difficulty=int(job["difficulty"]),
        role=profile.target_role,
        avoid=session.state.get("asked", []),
    )
    await _present_generated(db, session, msg, problem, job["topic"], int(job["difficulty"]))


async def _job_similar(
    db: AsyncSession, session: CoachSession, msg: CoachMessage, job: dict[str, Any], llm: LLMProvider
) -> None:
    cur = session.state.get("current") or {}
    topic = cur.get("topic") or agent_of(session).categories[0]
    difficulty = int(cur.get("difficulty", 2))
    if cur.get("source") == "bank" and cur.get("type") not in OPEN_TYPES:
        from careerpilot.modules.generator.service import GenerateRequest, generate

        req = GenerateRequest(
            position=(await get_profile(db, session.user_id)).target_role,
            category=topic,
            difficulty=difficulty,
            count=1,
            question_type=QuestionType(cur["type"])
            if cur["type"] in ("mcq_single", "mcq_multi", "true_false", "scenario")
            else QuestionType.MCQ_SINGLE,
        )
        stats = await generate(db, req, owner_id=session.user_id, llm=llm)
        if not stats.get("created"):
            raise ValueError("no valid similar question passed the checks; try again")
        q = await db.scalar(
            select(Question)
            .where(Question.owner_id == session.user_id, Question.provenance == "ai_generated")
            .order_by(Question.created_at.desc())
        )
        assert q is not None
        v = await db.get(QuestionVersion, q.current_version_id)
        assert v is not None
        session.state = {k: val for k, val in session.state.items() if k != "pending"}
        new = await present_bank_question(
            db, session, q, v, {"topic": topic, "reason": "similar exercise", "target_difficulty": difficulty}
        )
        msg.content, msg.data = new.content, new.data
        await db.delete(new)
        session.state["current"]["message_id"] = str(msg.id)
        return
    name = await db.scalar(select(Category.name).where(Category.slug == topic)) or topic
    problem = await ev.generate_open_problem(
        llm,
        agent_of(session),
        topic=name,
        difficulty=difficulty,
        role=(await get_profile(db, session.user_id)).target_role,
        avoid=session.state.get("asked", []),
    )
    await _present_generated(db, session, msg, problem, topic, difficulty)


async def _job_hint(
    db: AsyncSession, session: CoachSession, msg: CoachMessage, job: dict[str, Any], llm: LLMProvider
) -> None:
    v = await _current_version(db, session)
    forbidden = list(v.answer_key or []) if v else []
    text = await ev.hint(
        llm,
        agent_of(session),
        question=_current_question_text(session, v),
        level=int(job["level"]),
        forbidden=forbidden,
    )
    msg.content, msg.data = text, {"level": job["level"]}


async def _job_chat(
    db: AsyncSession, session: CoachSession, msg: CoachMessage, job: dict[str, Any], llm: LLMProvider
) -> None:
    v = await _current_version(db, session)
    cur = session.state.get("current") or {}
    answered = session.state.get("step") == "evaluated" or session.learning_mode
    history = [
        f"{m.role}: {m.content[:300]}"
        for m in await db.scalars(
            select(CoachMessage)
            .where(
                CoachMessage.session_id == session.id,
                CoachMessage.kind == "chat",
                CoachMessage.status == "done",
            )
            .order_by(CoachMessage.created_at, CoachMessage.id)
        )
    ]
    passages = await kb.search(
        db,
        job["message"] + " " + str(cur.get("stem", "")),
        user_id=session.user_id,
        k=4,
        exclude_question_id=None
        if answered
        else uuid.UUID(cur["question_id"])
        if cur.get("question_id")
        else None,
    )
    out = await ev.tutor_chat(
        llm,
        agent_of(session),
        question=_current_question_text(session, v) if cur else None,
        message=job["message"],
        history=history,
        passages=passages,
        may_reveal=answered,
    )
    msg.content, msg.data = out["answer"], {"references": out["references"]}


async def _job_interview_question(
    db: AsyncSession, session: CoachSession, msg: CoachMessage, job: dict[str, Any], llm: LLMProvider
) -> None:
    persona = PERSONAS[session.persona or "technical"]
    agent = agent_of(session)
    profile = await get_profile(db, session.user_id)
    skills = {s.slug: s.rating for s in await user_skills(db, session.user_id)}
    topics = sorted(agent.categories, key=lambda t: skills.get(t, 1000.0))
    names = dict(
        (await db.execute(select(Category.slug, Category.name).where(Category.slug.in_(topics)))).all()
    )
    iv = dict(session.state["interview"])
    seniority = {"junior": "junior", "mid": "mid-level", "senior": "senior"}.get(
        profile.seniority, "mid-level"
    )
    if persona.seniority_shift:
        seniority = "senior"
    q = await ev.interview_question(
        llm,
        agent,
        persona_style=persona.style,
        persona_name=persona.name,
        role=profile.target_role,
        seniority=seniority,
        topics=[names.get(t, t) for t in topics],
        asked=session.state.get("asked", []),
        number=iv["main_asked"] + 1,
        total=iv["total"],
    )
    iv |= {
        "main_asked": iv["main_asked"] + 1,
        "follow_ups": 0,
        "current_question": q["question"],
        "competency": q["competency"],
    }
    msg.content = q["question"]
    msg.data = {
        "interview": True,
        "number": iv["main_asked"],
        "total": iv["total"],
        "competency": q["competency"],
        "context": q["context"],
        "follow_up": False,
    }
    session.state = {
        **session.state,
        "interview": iv,
        "asked": [*session.state.get("asked", []), q["question"]],
    }


async def _job_interview_turn(
    db: AsyncSession, session: CoachSession, msg: CoachMessage, job: dict[str, Any], llm: LLMProvider
) -> None:
    persona = PERSONAS[session.persona or "technical"]
    agent = agent_of(session)
    iv = dict(session.state["interview"])
    passages = await kb.search(
        db, f"{iv['current_question']} {job['answer'][:300]}", user_id=session.user_id, k=3
    )
    result = await ev.evaluate_open(
        llm,
        agent,
        question=f"Interview question: {iv['current_question']}",
        answer=job["answer"],
        reference=None,
        passages=passages,
        interview=True,
    )
    turn = {
        "question": iv["current_question"],
        "competency": iv.get("competency"),
        "answer": job["answer"],
        "follow_up": iv["follow_ups"] > 0,
        **{
            k: result[k]
            for k in (
                "score",
                "criteria",
                "feedback",
                "strengths",
                "improvements",
                "model_answer",
                "references",
            )
        },
    }
    iv["turns"] = [*iv["turns"], turn]
    if (
        result.get("needs_follow_up")
        and result.get("follow_up_question")
        and iv["follow_ups"] < persona.max_follow_ups
    ):
        iv |= {"follow_ups": iv["follow_ups"] + 1, "current_question": result["follow_up_question"]}
        msg.content = result["follow_up_question"]
        msg.data = {
            "interview": True,
            "number": iv["main_asked"],
            "total": iv["total"],
            "follow_up": True,
            "competency": iv.get("competency"),
        }
        session.state = {**session.state, "interview": iv}
        return
    session.state = {**session.state, "interview": iv}
    if iv["main_asked"] < iv["total"]:
        await _job_interview_question(db, session, msg, job, llm)
        return
    msg.kind = "report"
    await _job_report(db, session, msg, job, llm)


async def _job_report(
    db: AsyncSession, session: CoachSession, msg: CoachMessage, job: dict[str, Any], llm: LLMProvider
) -> None:
    persona = PERSONAS[session.persona or "technical"]
    turns = session.state.get("interview", {}).get("turns", [])
    averages = criterion_averages(turns)
    overall = round(sum(t["score"] for t in turns) / len(turns)) if turns else 0
    summary = await ev.interview_report(
        llm, agent_of(session), persona_name=persona.name, turns=turns, averages=averages
    )
    report = {
        "persona": persona.name,
        "overall_score": overall,
        "verdict": ev.verdict(overall),
        "criteria_averages": averages,
        "questions": turns,
        **summary,
    }
    msg.kind, msg.content, msg.data = "report", str(summary.get("summary") or ""), report
    session.report, session.status, session.ended_at = report, "ended", utcnow()


_JOBS = {
    "enrich": _job_enrich,
    "evaluate_open": _job_evaluate_open,
    "generate_question": _job_generate_question,
    "similar": _job_similar,
    "hint": _job_hint,
    "chat": _job_chat,
    "interview_question": _job_interview_question,
    "interview_turn": _job_interview_turn,
    "report": _job_report,
}
