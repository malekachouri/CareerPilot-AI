# Adding or changing a coach agent

Agents are data plus prompts: the workflow, evaluation engine, API and UI pick a new agent up automatically.

## 1. Create the module

`apps/api/src/careerpilot/modules/coach/agents/data_engineering.py`:

```python
from careerpilot.modules.coach.agents.base import Agent, Criterion

AGENT = Agent(
    slug="data-engineering",
    name="Data Engineering Interview Agent",
    description="SQL, pipelines, batch/stream processing and data modelling.",
    categories=("databases", "python"),          # taxonomy slugs: bank questions come from these topics
    persona="You are a senior data engineer interviewing a candidate…",
    extra_criteria=(                              # added to the 6 core criteria for open answers
        Criterion("data_quality", "Data quality", "Validation, idempotent loads, late data."),
    ),
    open_problem_brief="a data pipeline design or SQL modelling problem with volumes and SLAs",
    answer_format="text",                         # or "code" for the code editor
    prefers_open=False,                           # True: start with open problems instead of bank MCQs
    evaluation_focus="Reward idempotency, backfills and cost awareness.",
    disclaimer=None,                              # shown in the UI when set
)
```

## 2. Register it

Add `"data_engineering"` to `_MODULES` in `coach/agents/__init__.py`. To add an interview simulation, add a
`Persona(...)` to `PERSONAS` there: slug, name, description, the agent it uses, the interviewer style,
`seniority_shift` and `max_follow_ups`.

## 3. Give it content

- Questions: tag bank questions with the agent's categories (see `adding-a-test-source.md`). Without suitable
  questions, the agent generates open problems with the local model.
- Lessons: add Markdown notes to `content/kb/` (front matter: `title`, `categories`, `license`,
  `attribution`), then run `careerpilot seed` or `POST /api/v1/admin/kb/reindex`.

## 4. Test it

`tests/test_coach.py::test_every_bank_agent_starts_with_a_question_from_its_topics` is parametrised by agent:
add the slug. `tests/fakes.py::FakeCoachLLM` answers any schema the engine requests, so no model is needed.

## Rules every agent inherits (`Agent.system_prompt`)

Accurate and honest about uncertainty; cites only the numbered passages it was given; never claims a question
comes from a real company's test; constructive feedback. The engine enforces the critical ones in code:
keys grade closed questions, scores come from the criteria, and invalid citations are removed.
