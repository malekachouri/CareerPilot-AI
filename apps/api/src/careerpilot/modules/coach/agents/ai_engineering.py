from careerpilot.modules.coach.agents.base import Agent, Criterion

AGENT = Agent(
    slug="ai-engineering",
    name="AI Engineering Interview Agent",
    description="Python, ML, DL, LLMs, RAG, vector databases, embeddings, agents and inference.",
    categories=(
        "python",
        "machine-learning",
        "deep-learning",
        "llms",
        "rag",
        "vector-databases",
        "ai-agents",
        "mlops",
        "llmops",
    ),
    persona=(
        "You are a staff AI engineer who ships LLM and ML systems to production. You interview candidates on "
        "fundamentals and on the engineering around models: evaluation, retrieval, safety, latency and cost."
    ),
    extra_criteria=(
        Criterion(
            "evaluation_rigour",
            "Evaluation rigour",
            "Measures quality properly: datasets, metrics, baselines.",
        ),
    ),
    open_problem_brief=(
        "an applied AI engineering problem (e.g. design a RAG pipeline for internal docs, evaluate an LLM feature, "
        "reduce inference latency, make an agent's tools safe)"
    ),
    evaluation_focus="Reward evaluation plans, data leakage awareness, grounding/citations and safety of tool use.",
)
