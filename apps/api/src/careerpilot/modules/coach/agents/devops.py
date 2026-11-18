from careerpilot.modules.coach.agents.base import Agent, Criterion

AGENT = Agent(
    slug="devops",
    name="DevOps Interview Agent",
    description="Linux, CI/CD, Docker, Kubernetes, Jenkins, Terraform, Ansible and GitOps.",
    categories=(
        "linux",
        "docker",
        "kubernetes",
        "jenkins",
        "github-actions",
        "gitlab-ci",
        "terraform",
        "ansible",
        "gitops",
        "cicd",
        "monitoring",
        "networking",
        "troubleshooting",
        "devsecops",
        "git",
    ),
    persona=(
        "You are a senior DevOps / SRE engineer interviewing a candidate and coaching them. You care about "
        "reliability, automation, security and how things behave in production at 3 a.m."
    ),
    extra_criteria=(
        Criterion(
            "operability", "Operability", "Thinks about monitoring, rollback, failure modes and on-call."
        ),
    ),
    open_problem_brief=(
        "a realistic DevOps troubleshooting or design scenario (e.g. a failing deployment, a slow node, a pipeline "
        "to design) that the candidate answers in a few paragraphs"
    ),
    evaluation_focus="Reward concrete commands, the order of investigation, rollback plans and least privilege.",
)
