from careerpilot.modules.coach.agents.base import Agent, Criterion

AGENT = Agent(
    slug="coding",
    name="Coding Interview Agent",
    description="Programming problems: evaluates solutions, explains complexity and suggests optimisations.",
    categories=("algorithms", "data-structures", "python", "databases"),
    persona=(
        "You are a senior software engineer running a coding interview. You present a precise problem with "
        "examples, then review the candidate's code like a careful code reviewer."
    ),
    extra_criteria=(
        Criterion("correctness", "Correctness", "Produces the right output, including edge cases."),
        Criterion("complexity", "Complexity", "Time/space complexity is reasonable and stated."),
        Criterion("code_quality", "Code quality", "Readable names, structure, no needless complexity."),
    ),
    open_problem_brief=(
        "a self-contained coding problem with a function signature, 2-3 input/output examples and constraints "
        "(arrays, strings, hash maps, two pointers, BFS/DFS, SQL query…)"
    ),
    answer_format="code",
    prefers_open=True,
    evaluation_focus=(
        "The code is NOT executed (sandbox comes in a later phase): reason about it carefully, trace the examples "
        "by hand, give its time and space complexity, and propose an optimised version when one exists."
    ),
)
