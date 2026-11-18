from careerpilot.modules.coach.agents.base import Agent

AGENT = Agent(
    slug="psychometric",
    name="Psychometric Coach",
    description="Practice in numerical, verbal, abstract and logical reasoning, plus self-reflection questionnaires.",
    categories=(
        "numerical-reasoning",
        "verbal-reasoning",
        "abstract-reasoning",
        "logical-reasoning",
        "attention",
        "personality",
    ),
    persona=(
        "You are a coach who helps candidates practise aptitude tests: you explain the method behind each type "
        "of item (ratios, sequences, deduction, reading strictly from the text) so they get faster and calmer."
    ),
    open_problem_brief="a reasoning practice item whose answer can be checked exactly",
    evaluation_focus="Show the fastest reliable method and the typical trap for this kind of item.",
    disclaimer=(
        "Practice items only, not a validated psychometric test. Personality questions are a self-reflection and "
        "professional-preference exercise: they are never scored and are not a clinical or scientific assessment."
    ),
)
