"""Deterministic stand-ins for the local model and the embedder, driven by the requested JSON schema."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from careerpilot.core.llm import LLMUnavailableError, Message


class FakeCoachLLM:
    name, model = "fake", "fake-coach"

    def __init__(
        self,
        *,
        score: int = 4,
        follow_ups: int = 1,
        contradict_key: bool = False,
        leak_hint: bool = False,
        unavailable: bool = False,
    ) -> None:
        self.score, self.follow_ups_left = score, follow_ups
        self.contradict_key, self.leak_hint, self.unavailable = contradict_key, leak_hint, unavailable
        self.calls: list[str] = []
        self.counter = 0

    async def health(self) -> bool:
        return not self.unavailable

    async def structured(
        self, messages: list[Message], schema: dict[str, Any], *, temperature: float = 0.4
    ) -> dict[str, Any]:
        if self.unavailable:
            raise LLMUnavailableError("Ollama is not reachable")
        props = schema.get("properties", {})
        prompt = messages[-1].content
        self.counter += 1
        if "correct_option_ids" in props:
            self.calls.append("enrich")
            key = re.search(r"The correct option\(s\) are: ([A-Z, ]+)\.", prompt)
            ids = [k.strip() for k in (key.group(1) if key else "A").split(",")]
            if self.contradict_key:
                ids = ["Z"]
            return {
                "correct_option_ids": ids,
                "reasoning_steps": ["Read the question.", "Apply the concept [1]."],
                "why_wrong": [{"option_id": "B", "why": "B confuses two concepts."}],
                "concepts": ["probes", "rollout"],
                "real_world_example": "On call, this happened at 3 a.m. [1]",
                "common_mistakes": ["Answering from memory without reading the options"],
                "citations": [1, 42],
            }
        if "scores" in props:
            self.calls.append("evaluate")
            keys = props["scores"]["required"]
            out: dict[str, Any] = {
                "scores": dict.fromkeys(keys, self.score),
                "feedback": "Good structure [1]; mention rollback [7].",
                "strengths": ["Clear steps"],
                "improvements": ["Add monitoring"],
                "model_answer": "A strong answer covers…",
                "concepts": ["SLO"],
                "real_world_example": "In production…",
                "common_mistakes": ["No rollback plan"],
                "citations": [1, 99],
            }
            if "complexity" in props:
                out |= {
                    "complexity": {"time": "O(n)", "space": "O(1)"},
                    "optimized_solution": "def f(xs): ...",
                    "traced_examples": "f([1,2]) -> 3",
                    "issues": [],
                }
            if "needs_follow_up" in props:
                follow = self.follow_ups_left > 0
                self.follow_ups_left -= int(follow)
                out |= {
                    "needs_follow_up": follow,
                    "follow_up_question": "Can you go deeper on rollback?" if follow else "",
                }
            return out
        if "reference_answer" in props:
            self.calls.append("open_problem")
            domain = re.search(r"set the scenario in ([^.]+)\.", prompt)
            return {
                "question": f"Design problem #{self.counter}: build a {domain.group(1) if domain else 'job'} service.",
                "context": "10k users",
                "skill": "system design",
                "recommended_minutes": 12,
                "reference_answer": "SECRET-REFERENCE: queues, idempotent consumers, rate limits",
                "starter_code": "def solve(xs):\n    pass",
            }
        if "hint" in props:
            self.calls.append("hint")
            return {"hint": "Option A is correct." if self.leak_hint else "Think about what removes traffic."}
        if "competency" in props:
            self.calls.append("interview_question")
            return {
                "question": f"Interview question #{self.counter}: how do you roll out safely?",
                "competency": "delivery",
            }
        if "summary" in props:
            self.calls.append("report")
            return {
                "summary": "Solid candidate.",
                "strengths": ["Structure"],
                "improvements": ["Depth"],
                "next_steps": ["Practise canary analysis"],
            }
        if "answer" in props:
            self.calls.append("chat")
            return {
                "answer": "Readiness removes the pod from endpoints [1]. See also [5].",
                "citations": [1, 5],
            }
        if "questions" in props:
            self.calls.append("generate")
            return {
                "questions": [
                    {
                        "stem": f"Generated similar question {self.counter} about probes?",
                        "options": ["Readiness", "Liveness", "Startup", "None"],
                        "correct_indexes": [0],
                        "explanation": "Because.",
                    }
                ]
            }
        if "correct_indexes" in props:
            return {"correct_indexes": [0]}
        raise AssertionError(f"unexpected schema: {list(props)}")


class FakeEmbedder:
    """Bag-of-words hashed into 768 dimensions: similar texts get similar vectors."""

    name, model, dim = "fake", "fake-embed", 768

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            v = [0.0] * self.dim
            for w in re.findall(r"[a-z]{3,}", t.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1.0  # noqa: S324 - not security
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out
