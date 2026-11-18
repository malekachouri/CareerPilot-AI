from careerpilot.modules.coach.agents.base import Agent, Criterion

AGENT = Agent(
    slug="cloud",
    name="Cloud Interview Agent",
    description="AWS, Azure, GCP, OpenStack, networking, IAM and architecture scenarios.",
    categories=("aws", "azure", "gcp", "openstack", "cloud-security", "cloud-architecture", "networking"),
    persona=(
        "You are a principal cloud architect interviewing a candidate. You expect provider-neutral reasoning "
        "first, then precise service knowledge, with attention to identity, networking, resilience and cost."
    ),
    extra_criteria=(
        Criterion(
            "security", "Security & IAM", "Least privilege, network isolation, secrets and encryption."
        ),
        Criterion("cost_awareness", "Cost awareness", "Knows what drives the bill and how to control it."),
    ),
    open_problem_brief=(
        "a cloud architecture or networking scenario (e.g. multi-AZ web app, private subnets, IAM for a CI "
        "pipeline, migrating an on-prem service) with constraints"
    ),
    evaluation_focus="Reward multi-AZ thinking, explicit IAM boundaries, private networking and cost trade-offs.",
)
