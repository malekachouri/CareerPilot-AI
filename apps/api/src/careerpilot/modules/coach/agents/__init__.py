"""Agent registry. To add an agent: create a module exposing `AGENT` and list it in `_MODULES`."""

from __future__ import annotations

from importlib import import_module

from careerpilot.modules.coach.agents.base import Agent, Criterion, Persona

_MODULES = ("devops", "cloud", "ai_engineering", "system_design", "coding", "hr", "psychometric")

AGENTS: dict[str, Agent] = {}
for _name in _MODULES:
    _agent: Agent = import_module(f"{__name__}.{_name}").AGENT
    AGENTS[_agent.slug] = _agent

# Prompt 3 §3 — interview simulations.
PERSONAS: dict[str, Persona] = {
    p.slug: p
    for p in (
        Persona(
            "hr-screening",
            "Initial HR screening",
            "Motivation, background, communication and a couple of behavioural questions.",
            agent="hr",
            style="friendly recruiter, 20-30 minutes, checks motivation and fit",
        ),
        Persona(
            "technical",
            "Technical interview",
            "Core technical questions for your target role, with follow-ups on your answers.",
            agent="devops",
            style="hands-on engineer who digs into the reasons behind answers",
        ),
        Persona(
            "senior-engineer",
            "Senior engineer interview",
            "Depth, trade-offs, ownership and mentoring; harder follow-ups.",
            agent="system-design",
            style="principal engineer probing depth, trade-offs and leadership",
            seniority_shift=1,
            max_follow_ups=2,
        ),
        Persona(
            "devops-scenario",
            "DevOps scenario interview",
            "Production incidents and pipeline scenarios, step by step.",
            agent="devops",
            style="SRE lead walking through incidents and asking 'what next?'",
            max_follow_ups=2,
        ),
        Persona(
            "cloud-architecture",
            "Cloud architecture interview",
            "Design a cloud solution and defend networking, IAM, resilience and cost choices.",
            agent="cloud",
            style="cloud architect reviewing a design with constraints",
        ),
        Persona(
            "ai-engineer",
            "AI Engineer interview",
            "LLMs, RAG, evaluation and production concerns of AI features.",
            agent="ai-engineering",
            style="staff AI engineer focused on evaluation and production",
        ),
    )
}


def get_agent(slug: str) -> Agent | None:
    return AGENTS.get(slug)


__all__ = ["AGENTS", "PERSONAS", "Agent", "Criterion", "Persona", "get_agent"]
