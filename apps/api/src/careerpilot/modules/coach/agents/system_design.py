from careerpilot.modules.coach.agents.base import Agent, Criterion

AGENT = Agent(
    slug="system-design",
    name="System Design Agent",
    description="Architecture problems: scalability, availability, security and cost decisions.",
    categories=("system-design", "cloud-architecture", "databases", "apis", "backend"),
    persona=(
        "You are a principal engineer running a system design interview. You give an open problem, expect the "
        "candidate to clarify requirements, estimate scale, propose components and justify trade-offs."
    ),
    extra_criteria=(
        Criterion(
            "scalability", "Scalability", "Handles growth: partitioning, caching, async processing, limits."
        ),
        Criterion("availability", "Availability", "Redundancy, failure modes, degradation, RPO/RTO."),
        Criterion("security", "Security", "Authentication, authorisation, data protection, abuse."),
        Criterion("cost", "Cost", "Sensible resource choices and what would dominate the bill."),
    ),
    open_problem_brief=(
        "a system design problem with explicit scale and constraints (e.g. URL shortener at 10k req/s, job alert "
        "service, multi-tenant RAG platform). Ask for requirements, high-level design and trade-offs"
    ),
    prefers_open=True,
    evaluation_focus="Judge the design decisions and the trade-offs explained, not one 'right' architecture.",
)
