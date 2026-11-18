"""Agent definition. An agent is data plus prompts: adding or changing one never touches the workflow."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Criterion:
    key: str
    label: str
    description: str


# Prompt 3 §4: every open answer is evaluated on these six dimensions.
CORE_CRITERIA: tuple[Criterion, ...] = (
    Criterion("technical_accuracy", "Technical accuracy", "Facts, commands and concepts are correct."),
    Criterion("clarity", "Clarity", "Easy to follow, well structured, precise vocabulary."),
    Criterion("completeness", "Completeness", "Covers the important aspects the question asks for."),
    Criterion(
        "problem_solving", "Problem-solving", "Sound reasoning, trade-offs, steps in a sensible order."
    ),
    Criterion(
        "communication",
        "Communication",
        "Would convince an interviewer: concise, confident, honest about limits.",
    ),
    Criterion(
        "practical_understanding", "Practical understanding", "Shows real-world experience, not only theory."
    ),
)


@dataclass(frozen=True)
class Agent:
    slug: str
    name: str
    description: str
    categories: tuple[str, ...]  # taxonomy slugs this agent draws questions from
    persona: str  # who the agent is (system prompt core)
    extra_criteria: tuple[Criterion, ...] = ()
    # Open problems the agent poses when the bank has nothing suitable (coding, design, behavioural…).
    open_problem_brief: str = "a practical open interview question"
    answer_format: str = "text"  # text | code
    evaluation_focus: str = ""  # agent-specific instructions for the evaluator
    prefers_open: bool = False  # start with open problems instead of bank MCQs
    disclaimer: str | None = None  # shown in the UI (e.g. psychometric / personality)
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def criteria(self) -> tuple[Criterion, ...]:
        return CORE_CRITERIA + self.extra_criteria

    def system_prompt(self) -> str:
        return (
            f"{self.persona}\n"
            "Rules: be accurate and say when you are unsure. Never invent sources: cite only the numbered "
            "passages you are given, as [1], [2]. Never claim a question comes from a real company's test. "
            "Be encouraging and specific; give constructive feedback, not only a verdict. Output JSON only."
        )


@dataclass(frozen=True)
class Persona:
    """An interview simulation: who interviews, on what, and how deep."""

    slug: str
    name: str
    description: str
    agent: str  # agent slug used for questions and evaluation
    style: str  # how the interviewer behaves
    seniority_shift: int = 0  # +1 for senior interviews (harder follow-ups)
    max_follow_ups: int = 1
