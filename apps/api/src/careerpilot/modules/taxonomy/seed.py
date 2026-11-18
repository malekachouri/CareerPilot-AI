"""Seed data for the taxonomy. Idempotent: running it again updates names and adds what is missing."""

from __future__ import annotations

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.taxonomy.models import Category, Company, Track, track_categories

# group slug, group name, [(slug, name, aliases)]
CATEGORY_TREE: list[tuple[str, str, list[tuple[str, str, list[str]]]]] = [
    (
        "devops",
        "DevOps",
        [
            ("linux", "Linux", ["linux-sysadmin", "unix", "bash"]),
            ("docker", "Docker", ["containers", "container"]),
            ("kubernetes", "Kubernetes", ["k8s", "helm"]),
            ("jenkins", "Jenkins", []),
            ("github-actions", "GitHub Actions", ["gha"]),
            ("gitlab-ci", "GitLab CI/CD", ["gitlab"]),
            ("terraform", "Terraform / OpenTofu", ["iac-terraform", "opentofu", "iac"]),
            ("ansible", "Ansible", ["iac-ansible"]),
            ("gitops", "GitOps", ["argocd", "flux"]),
            ("cicd", "CI/CD", ["cicd-gitops", "ci-cd", "devops-general"]),
            ("monitoring", "Monitoring & Observability", ["prometheus", "grafana", "elk", "observability"]),
            ("networking", "Networking", ["network", "dns"]),
            ("troubleshooting", "Troubleshooting", []),
            ("devsecops", "DevSecOps & Security", ["security", "cybersecurity", "owasp"]),
            ("git", "Git", ["version-control"]),
        ],
    ),
    (
        "cloud",
        "Cloud",
        [
            ("aws", "AWS", ["cloud-aws", "amazon-web-services"]),
            ("azure", "Azure", ["cloud-azure"]),
            ("gcp", "GCP", ["cloud-gcp", "google-cloud"]),
            ("openstack", "OpenStack", []),
            ("cloud-security", "Cloud Security", ["iam"]),
            ("cloud-architecture", "Cloud Architecture", []),
        ],
    ),
    (
        "ai",
        "AI",
        [
            ("python", "Python", []),
            ("machine-learning", "Machine Learning", ["ml"]),
            ("deep-learning", "Deep Learning", ["dl"]),
            ("llms", "LLMs", ["llm", "ai-engineering", "fundamentals-of-ai"]),
            ("rag", "RAG", []),
            ("vector-databases", "Vector Databases", ["vector-db", "embeddings"]),
            ("ai-agents", "AI Agents", ["agents"]),
            ("mlops", "MLOps", []),
            ("llmops", "LLMOps", []),
        ],
    ),
    (
        "software-engineering",
        "Software Engineering",
        [
            ("algorithms", "Algorithms", []),
            ("data-structures", "Data Structures", []),
            ("databases", "Databases & SQL", ["sql", "database"]),
            ("apis", "APIs", ["rest", "api"]),
            ("backend", "Backend", ["technical-knowledge"]),
            ("system-design", "System Design", ["architecture"]),
            ("software-testing", "Software Testing & QA", ["software-testing-qa", "qa", "testing"]),
            ("web-frontend", "Web & Frontend", ["git-web", "javascript", "react", "css", "html"]),
        ],
    ),
    (
        "recruitment",
        "Recruitment Assessments",
        [
            ("numerical-reasoning", "Numerical reasoning", ["numerical"]),
            ("verbal-reasoning", "Verbal reasoning", ["verbal-reading", "verbal", "reading-comprehension"]),
            ("abstract-reasoning", "Abstract reasoning", ["abstract"]),
            ("logical-reasoning", "Logical reasoning", ["logic-psychometric", "logic", "logical"]),
            ("situational-judgment", "Situational judgment", ["hr-behavioural", "teamwork", "behavioural"]),
            ("personality", "Personality questionnaires", ["profile-survey", "personality-questionnaire"]),
            ("attention", "Attention and concentration", ["concentration"]),
        ],
    ),
]

TRACKS = [
    (
        "devops-cloud-ai",
        "DevOps / Cloud / AI Engineer",
        "Linux, containers, Kubernetes, CI/CD, IaC, cloud, observability, security and AI engineering.",
        ["devops", "cloud", "ai", "software-engineering", "recruitment"],
    ),
]

# Websites only. Official preparation links are added by a reviewer after checking the company's own pages,
# never guessed.
COMPANIES = [
    ("amazon", "Amazon", "https://www.amazon.jobs"),
    ("google", "Google", "https://www.google.com/about/careers/"),
    ("microsoft", "Microsoft", "https://careers.microsoft.com"),
    ("accenture", "Accenture", "https://www.accenture.com"),
    ("capgemini", "Capgemini", "https://www.capgemini.com"),
    ("deloitte", "Deloitte", "https://www.deloitte.com"),
    ("ibm", "IBM", "https://www.ibm.com/careers"),
    ("sopra-steria", "Sopra Steria", "https://www.soprasteria.com"),
    ("orange", "Orange", "https://www.orange.com"),
    ("ooredoo", "Ooredoo", "https://www.ooredoo.com"),
    ("neoshore", "Neoshore", None),
    ("hydatis", "Hydatis", None),
    ("xtech-technology", "xTECH Technology", None),
]


async def seed_taxonomy(db: AsyncSession) -> dict[str, int]:
    created = {"categories": 0, "tracks": 0, "companies": 0}
    by_slug = {c.slug: c for c in await db.scalars(select(Category))}
    for g_order, (g_slug, g_name, children) in enumerate(CATEGORY_TREE):
        group = by_slug.get(g_slug)
        if group is None:
            group = Category(slug=g_slug, name=g_name, sort_order=g_order, aliases=[])
            db.add(group)
            created["categories"] += 1
            await db.flush()
            by_slug[g_slug] = group
        group.name = g_name
        for order, (slug, name, aliases) in enumerate(children):
            cat = by_slug.get(slug)
            if cat is None:
                cat = Category(slug=slug, name=name, parent_id=group.id, sort_order=order, aliases=aliases)
                db.add(cat)
                created["categories"] += 1
                by_slug[slug] = cat
            cat.name, cat.aliases, cat.parent_id = name, aliases, group.id
    await db.flush()

    tracks = {t.slug: t for t in await db.scalars(select(Track))}
    for slug, name, description, groups in TRACKS:
        track = tracks.get(slug)
        if track is None:
            track = Track(slug=slug, name=name, description=description)
            db.add(track)
            created["tracks"] += 1
            await db.flush()
            existing: set[object] = set()
        else:
            existing = set(
                await db.scalars(
                    select(track_categories.c.category_id).where(track_categories.c.track_id == track.id)
                )
            )
        for g in groups:
            if by_slug[g].id not in existing:
                await db.execute(
                    insert(track_categories).values(track_id=track.id, category_id=by_slug[g].id)
                )

    companies = {c.slug for c in await db.scalars(select(Company))}
    for slug, name, website in COMPANIES:
        if slug not in companies:
            db.add(Company(slug=slug, name=name, website=website, official_prep_links=[]))
            created["companies"] += 1
    await db.commit()
    return created
