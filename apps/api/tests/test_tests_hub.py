"""Integration tests: library, attempts with server-side timing, grading, results, analytics, companies."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import update

from careerpilot.core.db import SessionFactory, utcnow
from careerpilot.modules.assessments.models import Attempt
from tests.conftest import csrf, login_as


async def _test_by_slug(client: httpx.AsyncClient, slug: str) -> dict[str, Any]:
    tests = (await client.get("/api/v1/tests")).json()
    return next(t for t in tests if t["slug"] == slug)


async def _answer_key(attempt_id: str, position: int) -> list[str]:
    """Test helper: read the key directly from the database (the API never exposes it before submission)."""
    from sqlalchemy import select

    from careerpilot.modules.assessments.models import AttemptAnswer
    from careerpilot.modules.content.models import QuestionVersion

    async with SessionFactory() as db:
        key = await db.scalar(
            select(QuestionVersion.answer_key)
            .join(AttemptAnswer, AttemptAnswer.question_version_id == QuestionVersion.id)
            .where(AttemptAnswer.attempt_id == attempt_id, AttemptAnswer.position == position)
        )
    return list(key or [])


async def test_library_lists_curated_tests_with_summary_and_filters(
    client: httpx.AsyncClient, content: None
) -> None:
    await login_as(client, "ada@example.org")
    tests = (await client.get("/api/v1/tests")).json()
    assert len(tests) == 9
    k8s = await _test_by_slug(client, "containers-kubernetes")
    assert k8s["question_count"] == 7 and k8s["time_limit_s"] == 600
    assert {"docker", "kubernetes"} <= {c["slug"] for c in k8s["categories"]}
    assert k8s["provenance"] == ["original"]

    by_group = (await client.get("/api/v1/tests?category=cloud")).json()  # group slug expands to children
    assert "cloud-essentials" in {t["slug"] for t in by_group}
    search = (await client.get("/api/v1/tests?q=aptitude")).json()
    assert [t["slug"] for t in search] == ["aptitude-practice"]


async def test_full_attempt_flow_grading_and_results(client: httpx.AsyncClient, content: None) -> None:
    await login_as(client, "ada@example.org")
    test = await _test_by_slug(client, "linux-networking-fundamentals")
    r = await client.post(f"/api/v1/tests/{test['id']}/attempts", headers=csrf(client))
    assert r.status_code == 201
    attempt = r.json()
    assert attempt["remaining_seconds"] > 400
    q0 = attempt["questions"][0]["question"]
    assert "answer_key" not in q0 and "explanation" not in q0  # nothing leaks before submission

    # Results are refused while the attempt is open.
    assert (await client.get(f"/api/v1/attempts/{attempt['id']}/results")).status_code == 409

    key0 = await _answer_key(attempt["id"], 0)
    key1 = await _answer_key(attempt["id"], 1)
    wrong1 = next(o["id"] for o in attempt["questions"][1]["question"]["options"] if o["id"] not in key1)
    url = f"/api/v1/attempts/{attempt['id']}/answers"
    assert (
        await client.put(f"{url}/0", json={"selected": key0, "time_spent_ms": 4000}, headers=csrf(client))
    ).status_code == 200
    assert (
        await client.put(f"{url}/1", json={"selected": [wrong1], "time_spent_ms": 6000}, headers=csrf(client))
    ).status_code == 200
    # Validation: unknown option, two options on a single-choice question.
    assert (await client.put(f"{url}/2", json={"selected": ["Z"]}, headers=csrf(client))).status_code == 422
    assert (
        await client.put(f"{url}/2", json={"selected": ["A", "B"]}, headers=csrf(client))
    ).status_code == 422
    # Resume: the saved answers come back.
    state = (await client.get(f"/api/v1/attempts/{attempt['id']}")).json()
    assert state["questions"][0]["selected"] == key0 and state["questions"][0]["answered"]

    res = (await client.post(f"/api/v1/attempts/{attempt['id']}/submit", headers=csrf(client))).json()
    assert res["score"] == 1.0 and res["max_score"] == 6.0
    assert (res["correct"], res["incorrect"], res["unanswered"]) == (1, 5, 4)
    assert res["average_time_ms"] == 5000
    item = res["items"][1]
    assert item["is_correct"] is False and item["question"]["answer_key"] and item["question"]["explanation"]
    assert res["by_category"] and res["by_difficulty"]
    # Closed: answers can no longer change.
    assert (await client.put(f"{url}/2", json={"selected": ["A"]}, headers=csrf(client))).status_code == 409


async def test_deadline_auto_submits(client: httpx.AsyncClient, content: None) -> None:
    await login_as(client, "ada@example.org")
    test = await _test_by_slug(client, "cloud-essentials")
    attempt = (await client.post(f"/api/v1/tests/{test['id']}/attempts", headers=csrf(client))).json()
    async with SessionFactory() as db:
        await db.execute(
            update(Attempt)
            .where(Attempt.id == attempt["id"])
            .values(deadline_at=utcnow() - timedelta(minutes=1))
        )
        await db.commit()
    r = await client.put(
        f"/api/v1/attempts/{attempt['id']}/answers/0", json={"selected": ["A"]}, headers=csrf(client)
    )
    assert r.status_code == 409
    res = (await client.get(f"/api/v1/attempts/{attempt['id']}/results")).json()
    assert res["auto_submitted"] is True and res["score"] == 0.0


async def test_attempts_are_private(client: httpx.AsyncClient, content: None) -> None:
    await login_as(client, "ada@example.org")
    test = await _test_by_slug(client, "cloud-essentials")
    attempt = (await client.post(f"/api/v1/tests/{test['id']}/attempts", headers=csrf(client))).json()
    await login_as(client, "eve@example.org")
    assert (await client.get(f"/api/v1/attempts/{attempt['id']}")).status_code == 404
    assert (
        await client.post(f"/api/v1/attempts/{attempt['id']}/submit", headers=csrf(client))
    ).status_code == 404


async def test_custom_test_builder(client: httpx.AsyncClient, content: None) -> None:
    await login_as(client, "ada@example.org")
    body = {
        "title": "Docker drill",
        "categories": ["docker", "kubernetes"],
        "difficulties": [1, 2],
        "count": 4,
        "time_limit_minutes": 5,
    }
    r = await client.post("/api/v1/tests/custom", json=body, headers=csrf(client))
    assert r.status_code == 201, r.text
    t = r.json()
    assert (
        t["is_mine"]
        and t["visibility"] == "private"
        and t["question_count"] == 4
        and t["time_limit_s"] == 300
    )
    assert all(
        c["slug"] in {"docker", "kubernetes", "devsecops", "troubleshooting", "cloud-security"}
        for c in t["categories"]
    )
    none = await client.post("/api/v1/tests/custom", json={"categories": ["openstack"]}, headers=csrf(client))
    assert none.status_code == 422
    await login_as(client, "eve@example.org")
    assert (await client.get(f"/api/v1/tests/{t['id']}")).status_code == 404


async def test_analytics_accuracy_gaps_and_repeated_mistakes(
    client: httpx.AsyncClient, content: None
) -> None:
    await login_as(client, "ada@example.org")
    test = await _test_by_slug(client, "aptitude-practice")  # 12 questions
    for _ in range(2):
        attempt = (await client.post(f"/api/v1/tests/{test['id']}/attempts", headers=csrf(client))).json()
        for pos, q in enumerate(attempt["questions"]):
            key = await _answer_key(attempt["id"], pos)
            wrong = next(o["id"] for o in q["question"]["options"] if o["id"] not in key)
            choice = key if pos == 0 else [wrong]  # only the first one right
            await client.put(
                f"/api/v1/attempts/{attempt['id']}/answers/{pos}",
                json={"selected": choice, "time_spent_ms": 1000},
                headers=csrf(client),
            )
        await client.post(f"/api/v1/attempts/{attempt['id']}/submit", headers=csrf(client))
    a = (await client.get("/api/v1/me/analytics")).json()
    assert a["answered"] == 24 and a["correct"] == 2 and a["average_response_time_ms"] == 1000
    assert len(a["timeline"]) == 2 and len(a["repeated_mistakes"]) == 11
    assert {g["slug"] for g in a["knowledge_gaps"]} >= {"numerical-reasoning", "logical-reasoning"}
    assert [d["difficulty"] for d in a["by_difficulty"]] == sorted(
        d["difficulty"] for d in a["by_difficulty"]
    )
    history = (await client.get("/api/v1/me/attempts")).json()
    assert len(history) == 2 and history[0]["percent"] is not None


async def test_private_capture_without_key_then_owner_sets_key(
    client: httpx.AsyncClient, taxonomy: None
) -> None:
    await login_as(client, "owner@example.org")
    yaml_text = b"""company: Neoshore
questions:
  - {id: c1, domain: docker, type: mcq_single, stem: "Which flag removes a container when it exits?",
     options: [{id: A, text: "--rm"}, {id: B, text: "--restart"}], answer_key: null}
  - {id: c2, domain: linux, type: open_ended, stem: "Explain how you would debug a slow Linux server."}
"""
    await client.post(
        "/api/v1/me/imports/upload",
        files={"file": ("cap.yaml", yaml_text)},
        data={"kind": "personal_capture"},
        headers=csrf(client),
    )
    body = {
        "title": "Neoshore notes",
        "provenance": ["personal_capture"],
        "count": 10,
        "require_key": False,
        "mode": "practice",
    }
    t = (await client.post("/api/v1/tests/custom", json=body, headers=csrf(client))).json()
    attempt = (await client.post(f"/api/v1/tests/{t['id']}/attempts", headers=csrf(client))).json()
    res = (await client.post(f"/api/v1/attempts/{attempt['id']}/submit", headers=csrf(client))).json()
    assert res["ungraded"] == 2 and res["max_score"] == 0  # no key, open answer: not auto-graded

    open_pos = next(i["position"] for i in res["items"] if i["question"]["type"] == "open_ended")
    r = await client.post(
        f"/api/v1/attempts/{attempt['id']}/answers/{open_pos}/self-grade",
        json={"correct": True},
        headers=csrf(client),
    )
    assert r.status_code == 204
    res2 = (await client.get(f"/api/v1/attempts/{attempt['id']}/results")).json()
    assert (res2["score"], res2["max_score"], res2["ungraded"]) == (1.0, 1.0, 1)

    mcq = next(i["question"] for i in res["items"] if i["question"]["type"] == "mcq_single")
    r = await client.put(
        f"/api/v1/questions/{mcq['id']}/answer-key",
        json={"answer": ["A"], "explanation": "--rm"},
        headers=csrf(client),
    )
    assert r.status_code == 200 and r.json()["answer_key"] == ["A"] and r.json()["version"] == 2

    companies = (await client.get("/api/v1/companies")).json()
    neoshore = next(c for c in companies if c["slug"] == "neoshore")
    assert neoshore["my_private_questions"] == 2 and neoshore["public_questions"] == 0
    await login_as(client, "eve@example.org")
    assert (
        await client.put(
            f"/api/v1/questions/{mcq['id']}/answer-key", json={"answer": ["B"]}, headers=csrf(client)
        )
    ).status_code == 404
    detail = (await client.get("/api/v1/companies/neoshore")).json()
    assert detail["my_private_questions"] == 0 and "does not have access" in detail["disclaimer"]


async def test_categories_tree_and_tracks(client: httpx.AsyncClient, taxonomy: None) -> None:
    await login_as(client, "ada@example.org")
    tree = (await client.get("/api/v1/categories")).json()
    groups = {g["slug"]: [c["slug"] for c in g["children"]] for g in tree}
    assert set(groups) == {"devops", "cloud", "ai", "software-engineering", "recruitment"}
    assert {"gitlab-ci", "gitops", "troubleshooting"} <= set(groups["devops"])
    assert {"situational-judgment", "personality", "attention"} <= set(groups["recruitment"])
    tracks = (await client.get("/api/v1/tracks")).json()
    assert tracks[0]["slug"] == "devops-cloud-ai" and len(tracks[0]["groups"]) == 5


async def test_review_queue_publish(client: httpx.AsyncClient, taxonomy: None) -> None:
    await login_as(client, "contrib@example.org", role="contributor")
    body = {
        "stem": "Which file defines a Compose application?",
        "categories": ["docker"],
        "visibility": "public",
        "options": [{"id": "A", "text": "compose.yaml"}, {"id": "B", "text": "Makefile"}],
        "answer": ["A"],
    }
    r = await client.post("/api/v1/questions", json=body, headers=csrf(client))
    assert r.status_code == 201 and r.json()["status"] == "in_review"
    qid = r.json()["id"]
    await login_as(client, "reader@example.org")
    assert (await client.get(f"/api/v1/questions/{qid}")).status_code == 404  # not published yet
    await login_as(client, "rev@example.org", role="reviewer")
    queue = (await client.get("/api/v1/admin/review")).json()
    assert queue["total"] == 1 and queue["items"][0]["answer_key"] == ["A"]
    r = await client.post(
        "/api/v1/admin/review/decision",
        json={"question_ids": [qid], "action": "publish"},
        headers=csrf(client),
    )
    assert r.json() == {"updated": 1}
    await login_as(client, "reader@example.org")
    q = (await client.get(f"/api/v1/questions/{qid}")).json()
    assert q["status"] == "published" and q["verification"] == "reviewed"


async def test_options_are_shuffled_per_attempt_but_stable(client: httpx.AsyncClient, content: None) -> None:
    await login_as(client, "ada@example.org")
    test = await _test_by_slug(client, "devops-cloud-mock-exam")  # 15 questions, all 4-option
    attempt = (await client.post(f"/api/v1/tests/{test['id']}/attempts", headers=csrf(client))).json()
    orders = [[o["id"] for o in q["question"]["options"]] for q in attempt["questions"]]
    assert any(order != sorted(order) for order in orders)  # not the stored A, B, C, D order
    again = (await client.get(f"/api/v1/attempts/{attempt['id']}")).json()
    assert [[o["id"] for o in q["question"]["options"]] for q in again["questions"]] == orders
    results = (await client.post(f"/api/v1/attempts/{attempt['id']}/submit", headers=csrf(client))).json()
    assert [[o["id"] for o in i["question"]["options"]] for i in results["items"]] == orders

    verbal = await _test_by_slug(client, "aptitude-practice")
    a2 = (await client.post(f"/api/v1/tests/{verbal['id']}/attempts", headers=csrf(client))).json()
    tfu = [q for q in a2["questions"] if q["question"]["type"] == "true_false_undetermined"]
    assert tfu and all([o["id"] for o in q["question"]["options"]] == ["A", "B", "C"] for q in tfu)
