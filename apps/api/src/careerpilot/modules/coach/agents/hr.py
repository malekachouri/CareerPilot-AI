from careerpilot.modules.coach.agents.base import Agent, Criterion

AGENT = Agent(
    slug="hr",
    name="HR Interview Agent",
    description="Behavioural questions answered with the STAR method (Situation, Task, Action, Result).",
    categories=("situational-judgment",),
    persona=(
        "You are an experienced technical recruiter running a behavioural interview. You help the candidate "
        "tell concrete stories with the STAR method and sound authentic, not rehearsed."
    ),
    extra_criteria=(
        Criterion("star_situation", "STAR · Situation", "Sets the context briefly and concretely."),
        Criterion("star_task", "STAR · Task", "States their own responsibility or goal."),
        Criterion("star_action", "STAR · Action", 'Describes what THEY did ("I", not only "we").'),
        Criterion(
            "star_result", "STAR · Result", "Gives the outcome, ideally measurable, and what they learned."
        ),
    ),
    open_problem_brief=(
        "a behavioural interview question (conflict, failure, leadership, prioritisation, learning something fast, "
        "disagreeing with a decision) to be answered with the STAR method"
    ),
    prefers_open=True,
    evaluation_focus="There is no single right story: coach the structure, specificity and the candidate's own role.",
)
