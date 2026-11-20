"""Evaluation engine (Prompt 3 §1 step 4, §4).

- Closed questions are graded by the stored answer key, never by the model.
- The model only *explains*. Its output must name the same correct options as the key or it is discarded.
- Open, coding, design and behavioural answers are scored per criterion (0-5) with constructive feedback; the
  overall score is computed from the criteria, not taken from the model.
- Citations are indexes into the passages actually retrieved; anything else is dropped (no invented sources).
"""

from __future__ import annotations

import re
from typing import Any

from careerpilot.core.config import get_settings
from careerpilot.core.llm import LLMProvider, Message
from careerpilot.modules.coach.agents import Agent
from careerpilot.modules.coach.agents.base import CORE_CRITERIA, Criterion
from careerpilot.modules.content.models import QuestionVersion
from careerpilot.modules.kb.service import Passage

PROMPT_VERSION = "coach-v1"
COMPACT_PROMPT_VERSION = "coach-v1-compact"
# Compact mode: fewer, shorter reference passages (the prompt is read faster) and shorter outputs.
COMPACT_PASSAGES, COMPACT_PASSAGE_CHARS = 2, 600
COMPACT_STYLE = (
    "Be brief: at most 3 short sentences of feedback, at most 3 strengths and 3 improvements, "
    "and a model answer of at most 120 words."
)

STR_LIST: dict[str, Any] = {"type": "array", "items": {"type": "string"}}
INT_LIST: dict[str, Any] = {"type": "array", "items": {"type": "integer"}}


def is_compact(compact: bool | None = None) -> bool:
    """Explicit value (tests) or the COACH_COMPACT setting."""
    return get_settings().coach_compact if compact is None else compact


def prompt_version(compact: bool | None = None) -> str:
    return COMPACT_PROMPT_VERSION if is_compact(compact) else PROMPT_VERSION


def criteria_for(agent: Agent, compact: bool) -> tuple[Criterion, ...]:
    """Compact mode scores only the six core criteria (Prompt 3 §4); full mode adds the agent's own."""
    return CORE_CRITERIA if compact else agent.criteria


def _trim(passages: list[Passage], compact: bool) -> list[Passage]:
    return passages[:COMPACT_PASSAGES] if compact else passages


def passages_block(passages: list[Passage], *, max_chars: int = 1500) -> str:
    if not passages:
        return "No reference passages were retrieved: answer from general knowledge and cite nothing."
    lines = ["Reference passages (cite as [n] only when you use them):"]
    for i, p in enumerate(passages, start=1):
        lines.append(f"[{i}] {p.title}{' — ' + p.heading if p.heading else ''}\n{p.text[:max_chars]}")
    return "\n\n".join(lines)


def _block(passages: list[Passage], compact: bool) -> str:
    return passages_block(passages, max_chars=COMPACT_PASSAGE_CHARS if compact else 1500)


def resolve_citations(raw: Any, passages: list[Passage], *texts: str) -> list[dict[str, Any]]:
    """Keep only citations that point to a retrieved passage, from the explicit list and from [n] markers."""
    indexes: set[int] = set()
    for v in raw or []:
        try:
            indexes.add(int(v))
        except (TypeError, ValueError):
            continue
    for t in texts:
        indexes |= {int(m) for m in re.findall(r"\[(\d{1,2})\]", t or "")}
    refs = []
    for i in sorted(indexes):
        if 1 <= i <= len(passages):
            refs.append({"n": i, **passages[i - 1].reference()})
    return refs


def strip_bad_markers(text: str, passages: list[Passage]) -> str:
    return re.sub(
        r"\[(\d{1,2})\]", lambda m: m.group(0) if 1 <= int(m.group(1)) <= len(passages) else "", text or ""
    )


def question_text(v: QuestionVersion) -> str:
    opts = "\n".join(f"{o['id']}. {o['text']}" for o in v.options)
    ctx = f"Context:\n{v.context}\n\n" if v.context else ""
    return f"{ctx}Question: {v.stem}" + (f"\nOptions:\n{opts}" if opts else "")


# --- closed questions --------------------------------------------------------------------------------------


def grade_choice(v: QuestionVersion, selected: list[str]) -> dict[str, Any]:
    key = list(v.answer_key or [])
    if not key:
        return {"is_correct": None, "score": None, "correct_options": [], "graded_by": "none"}
    ok = set(selected) == set(key)
    return {"is_correct": ok, "score": 100 if ok else 0, "correct_options": key, "graded_by": "key"}


ENRICH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "correct_option_ids": STR_LIST,
        "reasoning_steps": STR_LIST,
        "why_wrong": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"option_id": {"type": "string"}, "why": {"type": "string"}},
                "required": ["option_id", "why"],
            },
        },
        "concepts": STR_LIST,
        "real_world_example": {"type": "string"},
        "common_mistakes": STR_LIST,
        "citations": INT_LIST,
    },
    "required": [
        "correct_option_ids",
        "reasoning_steps",
        "why_wrong",
        "concepts",
        "real_world_example",
        "common_mistakes",
    ],
}


COMPACT_ENRICH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        k: ENRICH_SCHEMA["properties"][k]
        for k in ("correct_option_ids", "reasoning_steps", "why_wrong", "citations")
    },
    "required": ["correct_option_ids", "reasoning_steps", "why_wrong"],
}


async def enrich_closed(
    llm: LLMProvider,
    agent: Agent,
    v: QuestionVersion,
    passages: list[Passage],
    *,
    compact: bool | None = None,
) -> dict[str, Any] | None:
    """Teaching material for a keyed question. Returns None when the model contradicts the key."""
    compact = is_compact(compact)
    passages = _trim(passages, compact)
    key = ", ".join(v.answer_key or [])
    task = (
        "Teach it briefly: correct_option_ids (repeat the correct ids), reasoning_steps (2-3 short steps) "
        "and one short sentence in why_wrong for every other option."
        if compact
        else "Teach it: correct_option_ids (repeat the correct ids), reasoning_steps (3-5 short steps), "
        "why_wrong for every other option, key concepts, one real-world example from production "
        "work, and the common mistakes candidates make in interviews."
    )
    out = await llm.structured(
        [
            Message("system", agent.system_prompt()),
            Message(
                "user",
                f"{question_text(v)}\n\nThe correct option(s) are: {key}. This is fixed: do not dispute it.\n"
                f"Stored explanation: {v.explanation or '(none)'}\n\n{_block(passages, compact)}\n\n{task}",
            ),
        ],
        COMPACT_ENRICH_SCHEMA if compact else ENRICH_SCHEMA,
        temperature=0.2,
    )
    if set(map(str, out.get("correct_option_ids", []))) != set(v.answer_key or []):
        return None  # contradicts the key: never shown
    valid_ids = {o["id"] for o in v.options} - set(v.answer_key or [])
    why_wrong = {
        str(w.get("option_id")): strip_bad_markers(str(w.get("why", "")), passages)
        for w in out.get("why_wrong", [])
        if str(w.get("option_id")) in valid_ids
    }
    steps = [strip_bad_markers(str(s), passages) for s in out.get("reasoning_steps", [])][:6]
    return {
        "reasoning_steps": steps,
        "why_wrong": why_wrong,
        "concepts": [str(c) for c in out.get("concepts", [])][:8],
        "real_world_example": strip_bad_markers(str(out.get("real_world_example", "")), passages),
        "common_mistakes": [str(m) for m in out.get("common_mistakes", [])][:5],
        "references": resolve_citations(
            out.get("citations"), passages, *steps, str(out.get("real_world_example", ""))
        ),
    }


# --- open answers ----------------------------------------------------------------------------------------


def open_schema(agent: Agent, *, code: bool, interview: bool, compact: bool = False) -> dict[str, Any]:
    scores = {c.key: {"type": "integer", "minimum": 0, "maximum": 5} for c in criteria_for(agent, compact)}
    props: dict[str, Any] = {
        "scores": {"type": "object", "properties": scores, "required": list(scores)},
        "feedback": {"type": "string"},
        "strengths": STR_LIST,
        "improvements": STR_LIST,
        "model_answer": {"type": "string"},
        "citations": INT_LIST,
    }
    if not compact:
        props |= {"concepts": STR_LIST, "real_world_example": {"type": "string"}, "common_mistakes": STR_LIST}
    required = ["scores", "feedback", "strengths", "improvements", "model_answer"]
    if code:
        props |= {
            "complexity": {
                "type": "object",
                "properties": {"time": {"type": "string"}, "space": {"type": "string"}},
            },
            "issues": STR_LIST,
            "optimized_solution": {"type": "string"},
        }
        if not compact:
            props["traced_examples"] = {"type": "string"}
        required += ["complexity", "optimized_solution"]
    if interview:
        props |= {"follow_up_question": {"type": "string"}, "needs_follow_up": {"type": "boolean"}}
        required += ["needs_follow_up"]
    return {"type": "object", "properties": props, "required": required}


def overall_score(scores: dict[str, Any], criteria: tuple[Criterion, ...]) -> int:
    values = [max(0, min(5, int(scores.get(c.key, 0)))) for c in criteria]
    return round(100 * sum(values) / (5 * len(values))) if values else 0


def verdict(score: int) -> str:
    return "strong" if score >= 75 else "partial" if score >= 45 else "needs work"


async def evaluate_open(
    llm: LLMProvider,
    agent: Agent,
    *,
    question: str,
    answer: str,
    reference: str | None,
    passages: list[Passage],
    code: bool = False,
    interview: bool = False,
    language: str | None = None,
    compact: bool | None = None,
) -> dict[str, Any]:
    compact = is_compact(compact)
    passages = _trim(passages, compact)
    crits = criteria_for(agent, compact)
    criteria = "\n".join(f"- {c.key}: {c.label}. {c.description}" for c in crits)
    extras = (
        COMPACT_STYLE
        if compact
        else "Give a model answer, key concepts, a real-world example and common interview mistakes."
    )
    ref = f"Reference points (guidance, not the only valid wording): {reference}\n" if reference else ""
    code_part = f"The answer is {language or 'code'}.\n" if code else ""
    out = await llm.structured(
        [
            Message("system", agent.system_prompt()),
            Message(
                "user",
                f"{question}\n\n{ref}{code_part}Candidate answer:\n<<<\n{answer[:12000]}\n>>>\n\n"
                f"{_block(passages, compact)}\n\nScore each criterion from 0 to 5:\n{criteria}\n"
                f"{agent.evaluation_focus}\nDifferent wording or a different valid approach must not lose "
                "points. Feedback must be constructive: what was good, what is missing, how to improve. "
                f"{extras}"
                + (
                    " Decide needs_follow_up (true when a key point is missing or unclear) and write one "
                    "short follow_up_question that probes it."
                    if interview
                    else ""
                ),
            ),
        ],
        open_schema(agent, code=code, interview=interview, compact=compact),
        temperature=0.2,
    )
    scores = {c.key: max(0, min(5, int((out.get("scores") or {}).get(c.key, 0)))) for c in crits}
    score = overall_score(scores, crits)
    texts = [
        str(out.get("feedback", "")),
        str(out.get("model_answer", "")),
        str(out.get("real_world_example", "")),
    ]
    result: dict[str, Any] = {
        "score": score,
        "verdict": verdict(score),
        "criteria": [{"key": c.key, "label": c.label, "score": scores[c.key]} for c in crits],
        "feedback": strip_bad_markers(texts[0], passages),
        "strengths": [str(s) for s in out.get("strengths", [])][:6],
        "improvements": [str(s) for s in out.get("improvements", [])][:6],
        "model_answer": strip_bad_markers(texts[1], passages),
        "concepts": [str(c) for c in out.get("concepts", [])][:8],
        "real_world_example": strip_bad_markers(texts[2], passages),
        "common_mistakes": [str(m) for m in out.get("common_mistakes", [])][:5],
        "references": resolve_citations(out.get("citations"), passages, *texts),
    }
    if code:
        cx = out.get("complexity") or {}
        result |= {
            "executed": False,
            "traced_examples": str(out.get("traced_examples", "")),
            "complexity": {"time": str(cx.get("time", "?")), "space": str(cx.get("space", "?"))},
            "issues": [str(i) for i in out.get("issues", [])][:8],
            "optimized_solution": str(out.get("optimized_solution", "")),
        }
    if interview:
        result |= {
            "needs_follow_up": bool(out.get("needs_follow_up")),
            "follow_up_question": str(out.get("follow_up_question", "")).strip(),
        }
    return result


# --- generated open problems, hints, chat, reports ---------------------------------------------------------

OPEN_QUESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "context": {"type": "string"},
        "skill": {"type": "string"},
        "recommended_minutes": {"type": "integer"},
        "reference_answer": {"type": "string"},
        "starter_code": {"type": "string"},
    },
    "required": ["question", "skill", "recommended_minutes", "reference_answer"],
}


async def generate_open_problem(
    llm: LLMProvider, agent: Agent, *, topic: str, difficulty: int, role: str, avoid: list[str]
) -> dict[str, Any]:
    levels = {1: "beginner", 2: "intermediate", 3: "advanced", 4: "expert"}
    out = await llm.structured(
        [
            Message("system", agent.system_prompt()),
            Message(
                "user",
                f"Write {agent.open_problem_brief}. Topic: {topic}. Level: {levels.get(difficulty, 'intermediate')}. "
                f"Candidate's target role: {role}. Put scenario details in `context`. `reference_answer` "
                "lists the key points of a strong answer (it is hidden from the candidate). "
                + (
                    "Give `starter_code` with the function signature. "
                    if agent.answer_format == "code"
                    else ""
                )
                + (f"Do not repeat these questions: {'; '.join(avoid[-5:])}" if avoid else ""),
            ),
        ],
        OPEN_QUESTION_SCHEMA,
        temperature=0.7,
    )
    if not str(out.get("question", "")).strip():
        raise ValueError("the model returned an empty question")
    return {
        "question": str(out["question"]).strip(),
        "context": str(out.get("context") or "").strip() or None,
        "skill": str(out.get("skill") or topic),
        "recommended_minutes": max(1, min(60, int(out.get("recommended_minutes") or 8))),
        "reference_answer": str(out.get("reference_answer", "")),
        "starter_code": str(out.get("starter_code") or "") or None,
    }


HINT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"hint": {"type": "string"}},
    "required": ["hint"],
}


async def hint(llm: LLMProvider, agent: Agent, *, question: str, level: int, forbidden: list[str]) -> str:
    out = await llm.structured(
        [
            Message("system", agent.system_prompt()),
            Message(
                "user",
                f"{question}\n\nGive hint number {level} of 3 (1 = gentle nudge, 3 = strong hint). Never state "
                f"the answer{' or name these options as correct: ' + ', '.join(forbidden) if forbidden else ''}.",
            ),
        ],
        HINT_SCHEMA,
        temperature=0.3,
    )
    text = str(out.get("hint", "")).strip()
    for f in forbidden:  # last guard against leaking the key
        text = re.sub(
            rf"\b(option\s+)?{re.escape(f)}\b(?=\s*(is|est)\s+(correct|right|juste))",
            "an option",
            text,
            flags=re.I,
        )
    return text


CHAT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"answer": {"type": "string"}, "citations": INT_LIST},
    "required": ["answer"],
}


async def tutor_chat(
    llm: LLMProvider,
    agent: Agent,
    *,
    question: str | None,
    message: str,
    history: list[str],
    passages: list[Passage],
    may_reveal: bool,
    compact: bool | None = None,
) -> dict[str, Any]:
    compact = is_compact(compact)
    passages = _trim(passages, compact)
    rule = (
        "You may discuss the answer."
        if may_reveal
        else "The learner has NOT answered yet: explain concepts and help them think, but do not give the answer."
    )
    out = await llm.structured(
        [
            Message("system", agent.system_prompt()),
            Message(
                "user",
                (f"Current question:\n{question}\n\n" if question else "")
                + f"{rule}\n"
                + ("Recent conversation:\n" + "\n".join(history[-6:]) + "\n\n" if history else "")
                + f"{_block(passages, compact)}\n\n"
                + ("Answer in at most 5 sentences.\n" if compact else "")
                + f"Learner: {message[:4000]}",
            ),
        ],
        CHAT_SCHEMA,
        temperature=0.3,
    )
    answer = strip_bad_markers(str(out.get("answer", "")), passages)
    return {"answer": answer, "references": resolve_citations(out.get("citations"), passages, answer)}


INTERVIEW_Q_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "competency": {"type": "string"},
        "context": {"type": "string"},
    },
    "required": ["question", "competency"],
}


async def interview_question(
    llm: LLMProvider,
    agent: Agent,
    *,
    persona_style: str,
    persona_name: str,
    role: str,
    seniority: str,
    topics: list[str],
    asked: list[str],
    number: int,
    total: int,
) -> dict[str, Any]:
    out = await llm.structured(
        [
            Message(
                "system", agent.system_prompt() + f" You are running a '{persona_name}': {persona_style}."
            ),
            Message(
                "user",
                f"Interview for a {seniority} {role}. This is main question {number} of {total}. "
                f"Prefer these topics (weakest first): {', '.join(topics[:6])}. Ask ONE question only, as you "
                "would say it in a real interview. "
                + (
                    f"Already asked (do not repeat): {'; '.join(a[:120] for a in asked[-8:])}"
                    if asked
                    else ""
                ),
            ),
        ],
        INTERVIEW_Q_SCHEMA,
        temperature=0.7,
    )
    q = str(out.get("question", "")).strip()
    if not q:
        raise ValueError("the model returned an empty question")
    return {
        "question": q,
        "competency": str(out.get("competency") or ""),
        "context": str(out.get("context") or "") or None,
    }


REPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "strengths": STR_LIST,
        "improvements": STR_LIST,
        "next_steps": STR_LIST,
    },
    "required": ["summary", "strengths", "improvements", "next_steps"],
}


async def interview_report(
    llm: LLMProvider,
    agent: Agent,
    *,
    persona_name: str,
    turns: list[dict[str, Any]],
    averages: dict[str, float],
) -> dict[str, Any]:
    lines = [f"Q: {t['question']}\nA: {t['answer'][:800]}\nScore: {t['score']}/100" for t in turns]
    out = await llm.structured(
        [
            Message("system", agent.system_prompt()),
            Message(
                "user",
                f"Write the debrief of this '{persona_name}'. Criterion averages (0-5): {averages}.\n\n"
                + "\n\n".join(lines)
                + "\n\nGive an honest summary, concrete strengths, improvements and "
                "3-5 next steps to practise. Be constructive.",
            ),
        ],
        REPORT_SCHEMA,
        temperature=0.3,
    )
    return {k: out.get(k) for k in ("summary", "strengths", "improvements", "next_steps")}
