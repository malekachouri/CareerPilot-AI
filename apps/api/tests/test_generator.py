"""AI question generator with a scripted fake model (no real LLM in tests)."""

from __future__ import annotations

from typing import Any

import httpx

from careerpilot.core.llm import LLMUnavailableError, Message, set_llm_override
from tests.conftest import csrf, login_as


class FakeLLM:
    name, model = "fake", "fake-1"

    def __init__(
        self, drafts: list[dict[str, Any]], solver: dict[str, list[int]] | None = None, fail: bool = False
    ) -> None:
        self.drafts, self.solver, self.fail, self.calls = drafts, solver or {}, fail, 0

    async def structured(
        self, messages: list[Message], schema: dict[str, Any], *, temperature: float = 0.4
    ) -> dict[str, Any]:
        self.calls += 1
        if self.fail:
            raise LLMUnavailableError("Ollama is not reachable")
        if "questions" in schema["properties"]:
            return {"questions": self.drafts}
        # Blind solver pass: answer by stem (defaults to the generator's own key).
        stem = messages[-1].content.split("\n")[0].removeprefix("Question: ")
        return {"correct_indexes": self.solver.get(stem, [0])}

    async def health(self) -> bool:
        return not self.fail


GOOD = {
    "stem": "Which kubectl command shows recent cluster events sorted by time?",
    "options": [
        "kubectl get events --sort-by=.lastTimestamp",
        "kubectl logs",
        "kubectl top nodes",
        "kubectl cp",
    ],
    "correct_indexes": [0],
    "explanation": "Events explain scheduling and probe failures.",
    "why_others_are_wrong": ["", "container logs", "resource usage", "copies files"],
}
BAD_INDEX = {
    "stem": "Broken draft with an impossible key",
    "options": ["a", "b"],
    "correct_indexes": [7],
    "explanation": "x",
}
SOLVER_DISAGREES = {
    "stem": "Which Kubernetes object stores non-confidential configuration?",
    "options": ["Secret", "ConfigMap", "PersistentVolume", "Ingress"],
    "correct_indexes": [0],
    "explanation": "(wrong key on purpose)",
}


async def test_generation_validates_self_checks_and_stores_separately(
    client: httpx.AsyncClient, taxonomy: None
) -> None:
    llm = FakeLLM([GOOD, BAD_INDEX, SOLVER_DISAGREES], solver={SOLVER_DISAGREES["stem"]: [1]})
    set_llm_override(llm)
    await login_as(client, "ada@example.org")
    status = (await client.get("/api/v1/generator/status")).json()
    assert status == {
        "provider": "fake",
        "model": "fake-1",
        "available": True,
        "types": ["mcq_multi", "mcq_single", "scenario", "true_false"],
    }

    body = {
        "position": "DevOps Engineer",
        "category": "kubernetes",
        "difficulty": 3,
        "count": 2,
        "duration_minutes": 5,
    }
    r = await client.post("/api/v1/generator/questions", json=body, headers=csrf(client))
    assert r.status_code == 202
    job = (await client.get(f"/api/v1/jobs/{r.json()['id']}")).json()
    assert job["status"] == "succeeded"
    res = job["result"]
    assert res["created"] == 1 and res["invalid"] >= 1 and res["failed_self_check"] >= 1

    generated = (await client.get("/api/v1/questions?provenance=ai_generated")).json()
    q = generated["items"][0]
    assert generated["total"] == 1 and q["visibility"] == "private" and q["verification"] == "unverified"
    assert "Unverified" in q["label"] and q["difficulty"] == 3
    test = (await client.get(f"/api/v1/tests/{res['test_id']}")).json()
    assert test["kind"] == "generated" and test["time_limit_s"] == 300 and test["question_count"] == 1

    # Generated questions never appear for other users or in the verified bank.
    await login_as(client, "eve@example.org")
    assert (await client.get("/api/v1/questions?provenance=ai_generated")).json()["total"] == 0
    assert (await client.get(f"/api/v1/jobs/{r.json()['id']}")).status_code == 404


async def test_duplicates_of_existing_questions_are_rejected(
    client: httpx.AsyncClient, taxonomy: None
) -> None:
    set_llm_override(FakeLLM([GOOD]))
    await login_as(client, "ada@example.org")
    body = {"position": "SRE", "category": "kubernetes", "count": 1, "self_check": False}
    first = await client.post("/api/v1/generator/questions", json=body, headers=csrf(client))
    second = await client.post("/api/v1/generator/questions", json=body, headers=csrf(client))
    j1 = (await client.get(f"/api/v1/jobs/{first.json()['id']}")).json()["result"]
    j2 = (await client.get(f"/api/v1/jobs/{second.json()['id']}")).json()["result"]
    assert j1["created"] == 1 and j2["created"] == 0 and j2["duplicates"] >= 1 and j2["test_id"] is None


async def test_llm_unavailable_fails_job_cleanly(client: httpx.AsyncClient, taxonomy: None) -> None:
    set_llm_override(FakeLLM([], fail=True))
    await login_as(client, "ada@example.org")
    assert (await client.get("/api/v1/generator/status")).json()["available"] is False
    r = await client.post(
        "/api/v1/generator/questions",
        json={"position": "SRE", "category": "kubernetes"},
        headers=csrf(client),
    )
    job = (await client.get(f"/api/v1/jobs/{r.json()['id']}")).json()
    assert job["status"] == "failed" and "not reachable" in job["error"]


async def test_unknown_category_and_unsupported_type(client: httpx.AsyncClient, taxonomy: None) -> None:
    set_llm_override(FakeLLM([GOOD]))
    await login_as(client, "ada@example.org")
    for body in (
        {"position": "SRE", "category": "devops"},
        {"position": "SRE", "category": "kubernetes", "question_type": "open_ended"},
    ):
        r = await client.post("/api/v1/generator/questions", json=body, headers=csrf(client))
        job = (await client.get(f"/api/v1/jobs/{r.json()['id']}")).json()
        assert job["status"] == "failed"
