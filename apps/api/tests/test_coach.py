"""AI Interview Coach: workflow, evaluation engine, agents, interviews, RAG citations and personalisation."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import select

from careerpilot.core.db import SessionFactory
from careerpilot.core.llm import set_embedder_override, set_llm_override
from careerpilot.modules.coach.models import CoachExplanation
from tests.conftest import csrf, login_as
from tests.fakes import FakeCoachLLM, FakeEmbedder

C = "/api/v1/coach"
# A realistic open answer: long enough not to be gated or capped by the evaluation engine.
DESIGN_ANSWER = (
    "I would put the API behind a load balancer and run several stateless instances. Writes go to a "
    "queue consumed by idempotent workers, so retries are safe. PostgreSQL stores the data with a read "
    "replica, a cache absorbs frequent reads, and Prometheus alerts on latency and error rate. The main "
    "trade-off is cost against availability."
)


def last(session: dict[str, Any], kind: str) -> dict[str, Any]:
    return next(m for m in reversed(session["messages"]) if m["kind"] == kind)


async def post(client: httpx.AsyncClient, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    r = await client.post(path, json=body or {}, headers=csrf(client))
    assert r.status_code in (200, 201), r.text
    return r.json()


async def key_of(question_id: str) -> list[str]:
    from careerpilot.modules.content.models import Question, QuestionVersion

    async with SessionFactory() as db:
        q = await db.get(Question, question_id)
        assert q is not None
        v = await db.get(QuestionVersion, q.current_version_id)
        assert v is not None
        return list(v.answer_key or [])


async def test_agents_and_interviews_catalogue(client: httpx.AsyncClient) -> None:
    await login_as(client, "ada@example.org")
    data = (await client.get(f"{C}/agents")).json()
    slugs = {a["slug"] for a in data["agents"]}
    assert slugs == {"devops", "cloud", "ai-engineering", "system-design", "coding", "hr", "psychometric"}
    design = next(a for a in data["agents"] if a["slug"] == "system-design")
    assert {
        "Technical accuracy",
        "Clarity",
        "Completeness",
        "Problem-solving",
        "Communication",
        "Practical understanding",
        "Scalability",
        "Availability",
        "Security",
        "Cost",
    } == set(design["criteria"])
    hr = next(a for a in data["agents"] if a["slug"] == "hr")
    assert any("STAR" in c for c in hr["criteria"])
    psy = next(a for a in data["agents"] if a["slug"] == "psychometric")
    assert "not a clinical" in psy["disclaimer"]
    assert {i["slug"] for i in data["interviews"]} == {
        "hr-screening",
        "technical",
        "senior-engineer",
        "devops-scenario",
        "cloud-architecture",
        "ai-engineer",
    }


async def test_practice_flow_closed_question(client: httpx.AsyncClient, content: None) -> None:
    llm = FakeCoachLLM()
    set_llm_override(llm)
    await login_as(client, "ada@example.org")
    s = await post(client, f"{C}/sessions", {"agent": "devops"})
    q = last(s, "question")
    # STEP 1: question, context, skill, difficulty, recommended time; no key anywhere.
    assert q["data"]["skills"] and q["data"]["difficulty_label"] and q["data"]["recommended_time_s"] >= 60
    assert {sk["slug"] for sk in q["data"]["skills"]} & {
        "linux",
        "docker",
        "kubernetes",
        "networking",
        "cicd",
        "terraform",
        "ansible",
        "monitoring",
        "devsecops",
        "github-actions",
        "gitops",
        "troubleshooting",
        "git",
    }
    assert "answer_key" not in json.dumps(s) and "explanation" not in json.dumps(q)
    assert s["state"]["step"] == "awaiting_answer"

    key = await key_of(q["data"]["question_id"])
    wrong = next(o["id"] for o in q["data"]["question"]["options"] if o["id"] not in key)
    s = await post(client, f"{C}/sessions/{s['id']}/answer", {"selected": [wrong]})
    # STEP 4: verdict, score, correct answer, explanation, why others are wrong.
    e = last(s, "evaluation")
    assert e["data"]["is_correct"] is False and e["data"]["score"] == 0
    assert [o["id"] for o in e["data"]["correct_options"]] == key and e["data"]["explanation"]
    # AI insight (concepts, real-world example, common mistakes) with only valid citations.
    insight = last(s, "insight")
    assert insight["status"] == "done", insight
    assert (
        insight["data"]["concepts"]
        and insight["data"]["real_world_example"]
        and insight["data"]["common_mistakes"]
    )
    assert all(r["n"] == 1 for r in insight["data"]["references"])  # [42] did not exist and was dropped
    stem = q["data"]["question"]["stem"]
    assert all(stem[:60] not in r["title"] for r in insight["data"]["references"])  # never cites itself
    # Messages written in one transaction keep their order: answer, evaluation, then recommendation.
    kinds = [m["kind"] for m in s["messages"]]
    assert kinds.index("answer") < kinds.index("evaluation") < kinds.index("recommendation")
    # STEP 5: recommendation with a lesson from the knowledge base.
    rec = last(s, "recommendation")
    assert rec["data"]["weak_topics"] and all(  # a wrong answer: the topic is listed as weak
        w["rating"] < 1000 or w["accuracy"] < 0.8 for w in rec["data"]["weak_topics"]
    )
    assert rec["data"]["topic"] and rec["data"]["next_difficulty"] in (1, 2, 3, 4)
    if rec["data"]["lesson"]:  # a lesson is study material, never a question
        assert rec["data"]["lesson"]["kind"] in ("note", "doc", "upload")
    skills = (await client.get("/api/v1/me/skills")).json()
    assert any(sk["answered"] == 1 and sk["rating"] < 1000 for sk in skills)

    # The explanation is cached per question version: a second answer does not call the model again.
    async with SessionFactory() as db:
        assert len(list(await db.scalars(select(CoachExplanation)))) == 1

    s2 = await post(client, f"{C}/sessions/{s['id']}/next")
    assert last(s2, "question")["data"]["question_id"] != q["data"]["question_id"]


async def test_learning_mode_reveal_not_counted(client: httpx.AsyncClient, content: None) -> None:
    set_llm_override(FakeCoachLLM())
    await login_as(client, "ada@example.org")
    normal = await post(client, f"{C}/sessions", {"agent": "cloud"})
    r = await client.post(f"{C}/sessions/{normal['id']}/reveal", headers=csrf(client))
    assert r.status_code == 403
    s = await post(client, f"{C}/sessions", {"agent": "cloud", "learning_mode": True})
    s = await post(client, f"{C}/sessions/{s['id']}/reveal")
    e = last(s, "evaluation")
    assert e["data"]["revealed"] is True and e["data"]["correct_options"]
    assert (await client.get("/api/v1/me/skills")).json() == []  # revealed answers do not change ratings


async def test_hint_never_states_the_key(client: httpx.AsyncClient, content: None) -> None:
    set_llm_override(FakeCoachLLM(leak_hint=True))
    await login_as(client, "ada@example.org")
    s = await post(client, f"{C}/sessions", {"agent": "devops"})
    key = await key_of(last(s, "question")["data"]["question_id"])
    s = await post(client, f"{C}/sessions/{s['id']}/hint")
    h = last(s, "hint")
    assert h["status"] == "done" and h["data"]["level"] == 1
    if key == ["A"]:
        assert "A is correct" not in h["content"]


async def test_explanation_contradicting_the_key_is_discarded(
    client: httpx.AsyncClient, content: None
) -> None:
    set_llm_override(FakeCoachLLM(contradict_key=True))
    await login_as(client, "ada@example.org")
    s = await post(client, f"{C}/sessions", {"agent": "devops"})
    q = last(s, "question")
    s = await post(
        client, f"{C}/sessions/{s['id']}/answer", {"selected": [q["data"]["question"]["options"][0]["id"]]}
    )
    insight = last(s, "insight")
    assert insight["data"].get("discarded") is True and "discarded" in insight["content"]
    async with SessionFactory() as db:
        assert list(await db.scalars(select(CoachExplanation))) == []


async def test_open_problem_generated_scored_by_criteria_and_hidden_reference(
    client: httpx.AsyncClient, taxonomy: None
) -> None:
    set_llm_override(FakeCoachLLM(score=4))
    await login_as(client, "ada@example.org")
    s = await post(client, f"{C}/sessions", {"agent": "system-design"})
    q = last(s, "question")
    assert (
        q["status"] == "done"
        and q["data"]["provenance"] == "ai_generated"
        and q["data"]["recommended_time_s"] == 720
    )
    assert "SECRET-REFERENCE" not in json.dumps(s)  # the reference answer stays server-side
    s = await post(client, f"{C}/sessions/{s['id']}/answer", {"text": DESIGN_ANSWER})
    e = last(s, "evaluation")
    assert e["status"] == "done"
    assert len(e["data"]["criteria"]) == 10 and e["data"]["score"] == 80 and e["data"]["verdict"] == "strong"
    assert [r["n"] for r in e["data"]["references"]] in ([], [1])  # [7] and [99] never point to real passages
    assert "[7]" not in e["data"]["feedback"]
    assert last(s, "recommendation")


async def test_coding_answer_gets_complexity_and_is_marked_not_executed(
    client: httpx.AsyncClient, taxonomy: None
) -> None:
    set_llm_override(FakeCoachLLM())
    await login_as(client, "ada@example.org")
    s = await post(client, f"{C}/sessions", {"agent": "coding"})
    q = last(s, "question")
    assert q["data"]["answer_format"] == "code" and q["data"]["starter_code"]
    s = await post(
        client,
        f"{C}/sessions/{s['id']}/answer",
        {"text": "def solve(xs):\n    return sum(xs)", "language": "python"},
    )
    e = last(s, "evaluation")["data"]
    assert (
        e["executed"] is False
        and e["complexity"] == {"time": "O(n)", "space": "O(1)"}
        and e["optimized_solution"]
    )
    assert any(c["key"] == "complexity" for c in e["criteria"])


async def test_interview_one_question_at_a_time_follow_up_and_report(
    client: httpx.AsyncClient, taxonomy: None
) -> None:
    llm = FakeCoachLLM(score=3, follow_ups=1)
    set_llm_override(llm)
    await login_as(client, "ada@example.org")
    s = await post(client, f"{C}/interviews", {"persona": "technical", "duration_minutes": 18})
    assert s["state"]["interview"]["total"] == 3
    questions = [m for m in s["messages"] if m["kind"] == "question"]
    assert len(questions) == 1 and questions[0]["status"] == "done"
    answers = 0
    while s["status"] == "active":
        s = await post(
            client,
            f"{C}/sessions/{s['id']}/answer",
            {"text": f"My answer {answers}: canary, rollback, SLOs."},
        )
        answers += 1
        if s["status"] == "active":
            assert "score" not in json.dumps([m["data"] for m in s["messages"] if m["kind"] == "question"])
        assert answers < 10
    assert all(m["data"]["text"] for m in s["messages"] if m["kind"] == "answer")
    follow_ups = [m for m in s["messages"] if m["kind"] == "question" and m["data"].get("follow_up")]
    assert len(follow_ups) == 1 and answers == 4  # 3 main questions + 1 adaptive follow-up
    report = s["report"]
    assert report["overall_score"] == 60 and report["verdict"] == "partial"
    assert set(report["criteria_averages"]) >= {"Technical accuracy", "Communication", "Operability"}
    assert len(report["questions"]) == 4 and report["next_steps"]
    assert last(s, "report")["content"] == "Solid candidate."
    listed = (await client.get(f"{C}/sessions")).json()
    assert listed[0]["overall_score"] == 60
    # Conversation history is private.
    await login_as(client, "eve@example.org")
    assert (await client.get(f"{C}/sessions/{s['id']}")).status_code == 404


async def test_unavailable_model_fails_cleanly_then_retry(client: httpx.AsyncClient, taxonomy: None) -> None:
    set_llm_override(FakeCoachLLM(unavailable=True))
    await login_as(client, "ada@example.org")
    s = await post(client, f"{C}/sessions", {"agent": "hr"})
    q = last(s, "question")
    assert q["status"] == "failed" and "not available" in q["content"]
    assert (await client.get(f"{C}/status")).json()["llm"]["available"] is False
    set_llm_override(FakeCoachLLM())
    s = await post(client, f"{C}/sessions/{s['id']}/messages/{q['id']}/retry")
    assert last(s, "question")["status"] == "done" and s["state"]["step"] == "awaiting_answer"


async def test_tutor_chat_cites_only_retrieved_passages(client: httpx.AsyncClient, content: None) -> None:
    set_llm_override(FakeCoachLLM())
    await login_as(client, "ada@example.org")
    s = await post(client, f"{C}/sessions", {"agent": "devops"})
    s = await post(
        client, f"{C}/sessions/{s['id']}/ask", {"message": "What does a readiness probe do in Kubernetes?"}
    )
    reply = last(s, "chat")
    assert reply["role"] == "coach" and reply["status"] == "done"
    refs = reply["data"]["references"]
    assert refs and all(r["title"] for r in refs) and len(refs) <= 2


async def test_hybrid_search_and_private_materials(client: httpx.AsyncClient, content: None) -> None:
    set_embedder_override(FakeEmbedder())
    from careerpilot.modules.kb.service import embed_missing

    async with SessionFactory() as db:
        assert await embed_missing(db, embedder=FakeEmbedder()) > 0
    await login_as(client, "ada@example.org")
    hits = (
        await client.get(
            "/api/v1/kb/search", params={"q": "readiness probe removes pod from service endpoints"}
        )
    ).json()
    assert hits and "probe" in (hits[0]["title"] + hits[0]["text"]).lower()
    assert all(h["license"] in ("CC-BY-4.0", None) for h in hits)

    files = {"file": ("my-notes.md", b"# Blue green\nMy personal note about blue-green switchover drills.")}
    r = await client.post("/api/v1/me/kb/upload", files=files, headers=csrf(client))
    assert r.status_code == 201 and r.json()["chunks"] == 1
    mine = (await client.get("/api/v1/kb/search", params={"q": "switchover drills"})).json()
    assert any(h["title"] == "my-notes.md" for h in mine)
    await login_as(client, "eve@example.org")
    other = (await client.get("/api/v1/kb/search", params={"q": "switchover drills"})).json()
    assert all(h["title"] != "my-notes.md" for h in other)


async def test_personality_items_are_reflection_not_scored(client: httpx.AsyncClient, taxonomy: None) -> None:
    await login_as(client, "ada@example.org")
    yaml_text = (
        b"questions:\n  - {id: p1, domain: personality, type: survey,\n"
        b"     stem: 'I prefer to plan my work in detail.', options: [Agree, Neutral, Disagree]}\n"
    )
    await client.post(
        "/api/v1/me/imports/upload",
        files={"file": ("p.yaml", yaml_text)},
        data={"kind": "user_created"},
        headers=csrf(client),
    )
    s = await post(client, f"{C}/sessions", {"agent": "psychometric", "topic": "personality"})
    q = last(s, "question")
    assert q["data"]["question"]["type"] == "survey"
    s = await post(client, f"{C}/sessions/{s['id']}/answer", {"selected": ["A"]})
    e = last(s, "evaluation")
    assert (
        e["data"]["reflection"] is True and "score" not in e["data"] and "clinical" in e["data"]["disclaimer"]
    )
    assert "not a clinical" in last(s, "notice")["content"]


async def test_personalisation_weak_topic_profile_and_test_ratings(
    client: httpx.AsyncClient, content: None
) -> None:
    await login_as(client, "ada@example.org")
    r = await client.put(
        "/api/v1/me/learning-profile",
        headers=csrf(client),
        json={
            "target_role": "SRE",
            "seniority": "senior",
            "interview_minutes": 45,
            "focus_categories": ["kubernetes"],
            "language": "en",
        },
    )
    assert r.status_code == 200
    assert (await client.get("/api/v1/me/learning-profile")).json()["interview_minutes"] == 45

    # Answering a Tests Hub test wrongly lowers the rating of its topics...
    tests = (await client.get("/api/v1/tests")).json()
    test = next(t for t in tests if t["slug"] == "cloud-essentials")
    a = (await client.post(f"/api/v1/tests/{test['id']}/attempts", headers=csrf(client))).json()
    await client.post(f"/api/v1/attempts/{a['id']}/submit", headers=csrf(client))
    skills = {sk["slug"]: sk for sk in (await client.get("/api/v1/me/skills")).json()}
    assert skills["aws"]["rating"] < 1000 and skills["aws"]["answered"] >= 3

    # ...and the cloud agent then starts with a weak topic (the weakest one that still has unseen questions).
    s = await post(client, f"{C}/sessions", {"agent": "cloud"})
    sel = last(s, "question")["data"]["selection"]
    assert sel["reason"] == "weakest topic" and sel["rating"] < 1000
    assert sel["target_difficulty"] <= 2


@pytest.mark.parametrize("agent", ["devops", "cloud", "ai-engineering", "psychometric"])
async def test_every_bank_agent_starts_with_a_question_from_its_topics(
    client: httpx.AsyncClient, content: None, agent: str
) -> None:
    set_llm_override(FakeCoachLLM())
    await login_as(client, "ada@example.org")
    agents = {a["slug"]: a for a in (await client.get(f"{C}/agents")).json()["agents"]}
    s = await post(client, f"{C}/sessions", {"agent": agent})
    q = last(s, "question")
    assert q["status"] == "done"
    assert {sk["slug"] for sk in q["data"]["skills"]} & set(agents[agent]["categories"])


@respx.mock
async def test_ollama_provider_sends_memory_settings_and_reports_timeouts() -> None:
    from careerpilot.core.llm import LLMTimeoutError, OllamaProvider

    route = respx.post("http://ollama.test/api/chat").respond(json={"message": {"content": '{"ok": true}'}})
    provider = OllamaProvider("http://ollama.test", "qwen3:4b", 5, num_ctx=2048, keep_alive="15m")
    assert await provider.structured([], {"type": "object"}) == {"ok": True}
    sent = json.loads(route.calls[0].request.content)
    assert (
        sent["options"]["num_ctx"] == 2048
        and sent["keep_alive"] == "15m"
        and sent["format"] == {"type": "object"}
    )

    assert sent["options"]["num_predict"] == 1200

    respx.post("http://ollama.test/api/chat").respond(
        json={"message": {"content": '{"a": '}, "done_reason": "length"}
    )
    with pytest.raises(ValueError, match="cut off"):
        await provider.structured([], {"type": "object"})

    respx.post("http://ollama.test/api/chat").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(LLMTimeoutError, match="did not answer within 5s"):
        await provider.structured([], {"type": "object"})


async def test_slow_model_explains_memory_and_smaller_model(
    client: httpx.AsyncClient, taxonomy: None
) -> None:
    from careerpilot.core.llm import LLMTimeoutError

    class SlowLLM(FakeCoachLLM):
        async def structured(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise LLMTimeoutError("The model 'qwen3:4b' did not answer within 300s")

    set_llm_override(SlowLLM())
    await login_as(client, "ada@example.org")
    s = await post(client, f"{C}/sessions", {"agent": "system-design"})
    q = last(s, "question")
    assert q["status"] == "failed"
    assert "not enough free memory" in q["content"] and "qwen3:1.7b" in q["content"]


async def test_compact_mode_scores_core_criteria_with_shorter_outputs(
    client: httpx.AsyncClient, taxonomy: None
) -> None:
    from careerpilot.core.config import get_settings

    class RecordingLLM(FakeCoachLLM):
        def __init__(self) -> None:
            super().__init__(score=4)
            self.seen: list[tuple[str, dict[str, Any]]] = []

        async def structured(self, messages: Any, schema: dict[str, Any], **kw: Any) -> dict[str, Any]:
            self.seen.append((messages[-1].content, schema))
            return await super().structured(messages, schema, **kw)

    llm = RecordingLLM()
    set_llm_override(llm)
    settings = get_settings()
    settings.coach_compact = True
    try:
        await login_as(client, "ada@example.org")
        s = await post(client, f"{C}/sessions", {"agent": "system-design"})
        s = await post(client, f"{C}/sessions/{s['id']}/answer", {"text": DESIGN_ANSWER})
    finally:
        settings.coach_compact = False
    e = last(s, "evaluation")
    assert e["status"] == "done"
    # Only the six core criteria, still scored from the criteria (4/5 everywhere = 80).
    assert len(e["data"]["criteria"]) == 6 and e["data"]["score"] == 80
    prompt, schema = next((p, sc) for p, sc in llm.seen if "scores" in sc["properties"])
    assert len(schema["properties"]["scores"]["required"]) == 6
    assert not {"concepts", "real_world_example", "common_mistakes"} & set(schema["properties"])
    assert "Be brief" in prompt


async def test_compact_explanation_is_short_and_replaced_in_full_mode(
    client: httpx.AsyncClient, content: None
) -> None:
    from careerpilot.core.config import get_settings
    from careerpilot.modules.coach import evaluation as ev

    set_llm_override(FakeCoachLLM())
    settings = get_settings()
    await login_as(client, "ada@example.org")
    settings.coach_compact = True
    try:
        s = await post(client, f"{C}/sessions", {"agent": "devops"})
        q = last(s, "question")
        key = await key_of(q["data"]["question_id"])
        s = await post(client, f"{C}/sessions/{s['id']}/answer", {"selected": key})
    finally:
        settings.coach_compact = False
    assert last(s, "insight")["status"] == "done"
    async with SessionFactory() as db:
        cached = (await db.scalars(select(CoachExplanation))).one()
        assert cached.prompt_version == ev.COMPACT_PROMPT_VERSION
        assert "concepts" not in ev.COMPACT_ENRICH_SCHEMA["properties"]

    # Same question in full mode: the short explanation is regenerated, not reused.
    s2 = await post(client, f"{C}/sessions", {"agent": "devops", "question_id": q["data"]["question_id"]})
    assert last(s2, "question")["data"]["question_id"] == q["data"]["question_id"]
    s2 = await post(client, f"{C}/sessions/{s2['id']}/answer", {"selected": key})
    assert last(s2, "insight")["status"] == "done"
    async with SessionFactory() as db:
        cached = (await db.scalars(select(CoachExplanation))).one()
        assert cached.prompt_version == ev.PROMPT_VERSION


async def test_unreadable_or_short_answers_are_not_praised(client: httpx.AsyncClient, taxonomy: None) -> None:
    from careerpilot.modules.coach import evaluation as ev

    llm = FakeCoachLLM(score=5)
    set_llm_override(llm)
    await login_as(client, "ada@example.org")
    s = await post(client, f"{C}/sessions", {"agent": "system-design"})
    s = await post(client, f"{C}/sessions/{s['id']}/answer", {"text": "vdfwfdvfd edrftghyjuk"})
    e = last(s, "evaluation")
    # Gibberish never reaches the model (which would praise it) and scores 0.
    assert e["status"] == "done" and e["data"]["score"] == 0 and e["data"]["not_evaluated"]
    assert "evaluate" not in llm.calls and "not readable" in e["content"]

    assert ev.answer_problem("Use a CDN.", code=False)  # too short
    assert ev.answer_problem("kubectl get pods", code=True)  # code under 20 characters
    assert ev.answer_problem(DESIGN_ANSWER, code=False) is None
    assert (
        ev.answer_problem("Les données passent par une file, puis des consommateurs idempotents.", code=False)
        is None
    )

    # A short but real answer is evaluated, but cannot be "complete".
    s = await post(client, f"{C}/sessions/{s['id']}/next")
    s = await post(
        client, f"{C}/sessions/{s['id']}/answer", {"text": "A load balancer, several instances and a cache."}
    )
    e = last(s, "evaluation")
    completeness = next(c for c in e["data"]["criteria"] if c["key"] == "completeness")
    assert completeness["score"] == ev.SHORT_COMPLETENESS_CAP and e["data"]["score"] < 100


async def test_generated_problems_vary_their_domain_and_avoid_repeats() -> None:
    import random

    from careerpilot.modules.coach import evaluation as ev
    from careerpilot.modules.coach.agents import AGENTS

    avoid = [f"Design a system for {d}" for d in ev.DOMAINS[:-1]]
    assert ev.pick_domain(avoid, random.Random(1)) == ev.DOMAINS[-1]  # noqa: S311
    assert ev.too_similar("Design a real-time video platform.", ["design a real-time video platform"])
    assert not ev.too_similar("Design a URL shortener.", ["Design a payment ledger for a bank."])
    # Same template, different domain and numbers: not a repeat (seen with qwen3:1.7b).
    assert not ev.too_similar(
        "Design an API system for a logistics and shipping platform that supports 10,000 concurrent users, "
        "with a latency of less than 500ms for API calls, and must handle 1,000 API requests per second.",
        [
            "Design an API system for a social network that supports 100 million concurrent users, with a "
            "latency of less than 100ms for API calls, and must handle 10 million API requests per second."
        ],
    )

    class Repeating(FakeCoachLLM):
        async def structured(self, messages: Any, schema: dict[str, Any], **kw: Any) -> dict[str, Any]:
            out = await super().structured(messages, schema, **kw)
            if self.calls.count("open_problem") == 1:
                out["question"] = "Design a real-time video streaming platform."
            return out

    llm = Repeating()
    out = await ev.generate_open_problem(
        llm, AGENTS["system-design"], topic="system-design", difficulty=1, role="DevOps",
        avoid=["Design a real-time video streaming platform."],
    )  # fmt: skip
    assert llm.calls.count("open_problem") == 2 and "video" not in out["question"]
