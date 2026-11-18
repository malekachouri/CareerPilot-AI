# CareerPilot AI

**AI-powered interview preparation & career intelligence platform — free, open-source and self-hostable.**

> Status: **Phase 2 (AI Interview Coach) is done**: 7 specialised agents, a 5-step coaching workflow,
> interview simulations with follow-ups and a report, an evaluation engine, RAG with checked citations, and
> per-topic personalisation. Earlier: **Phase 1 (Interview Tests Hub)**, on top of the Phase 0 foundations: source import engine
> with licence checks, question bank, timed tests, results with explanations, analytics, company collections and
> a local-AI question generator. See the [roadmap](docs/08-roadmap.md).

## Quick start

Requirements: Docker Engine with Compose v2 (Docker Desktop is not required: Podman, Colima or Rancher
Desktop work too) and about 3 GB of free RAM.

```bash
git clone https://github.com/malekachouri/CareerPilot-AI.git && cd CareerPilot-AI
cp .env.example .env
docker compose up -d --build --wait
```

Open http://localhost:3000 and create an account. The API docs are at http://localhost:8000/api/v1/docs.
The first start seeds the categories, 55 original questions and 9 curated tests. For the AI question generator,
also run `docker compose --profile ai up -d`, then `docker compose exec ollama ollama pull qwen3:4b` and
`docker compose exec ollama ollama pull nomic-embed-text`. Without a model, multiple-choice coaching still works.
To add test sources, see [docs/guides/adding-a-test-source.md](docs/guides/adding-a-test-source.md).

For a personal, invite-only instance, set `REGISTRATION_OPEN=false` in `.env`, then create your account:

```bash
docker compose run --rm api careerpilot create-admin --email you@example.org
```

## Development

| Task | Command |
|------|---------|
| Start Postgres + Valkey only | `make dev-deps` |
| API with hot reload (port 8000) | `make api` (uses [uv](https://docs.astral.sh/uv/)) |
| Web with hot reload (port 3000) | `make web` (uses pnpm) |
| Tests / lint / types | `make test` · `make lint` · `make typecheck` |
| Regenerate the typed API client after an API change | `make api-client` |
| Browser smoke test against the running stack | `make e2e` |

| Path | What |
|------|------|
| `apps/api` | FastAPI + SQLAlchemy 2 + Alembic + Celery (Python 3.12) |
| `apps/web` | Next.js 16 + TypeScript + Tailwind CSS; `/api/*` is proxied to the API (same-origin cookies) |
| `docs/` | Design documents (below) |
| `.github/workflows/ci.yml` | Lint, strict types, tests on real Postgres/Valkey, licence gate, gitleaks, Trivy, image scan, Compose E2E |

Private study content (captured recruitment tests) lives in a **separate private repository** and is never committed here.

## Modules

| # | Module | Purpose |
|---|--------|---------|
| A | Interview Tests Hub | Licensed, provenance-tracked question banks; timed/untimed tests; custom tests |
| B | Coding & Logic Challenges | Sandboxed code execution, DevOps/K8s/IaC scenarios, logic games, leaderboards |
| C | AI Interview Coach | Local-LLM agent that explains, evaluates, generates similar questions, mock interviews |
| D | English Academy | Speaking, Listening, Reading, Writing, Grammar, Vocabulary, Technical & Interview English |
| E | Global Job Radar | Job aggregation from official APIs, RSS and public ATS endpoints — no scraping in violation of ToS |
| F | Career Analytics | Skill ratings, weaknesses, readiness score, personalised roadmap |

First career track: **DevOps / Cloud / AI Engineer**. The content model supports adding tracks later.

## Design documents

| Doc | Content |
|-----|---------|
| [01 — Functional specification](docs/01-functional-specification.md) | Users, modules, features, acceptance criteria |
| [02 — System architecture](docs/02-system-architecture.md) | System, frontend, backend, background processing, auth, deployment |
| [03 — Database design](docs/03-database-design.md) | PostgreSQL schema (+ pgvector) |
| [04 — Project structure](docs/04-project-structure.md) | Monorepo folder layout |
| [05 — API design](docs/05-api-design.md) | REST endpoints, conventions |
| [06 — AI agents](docs/06-ai-agents.md) | LLM abstraction, RAG, agents, guardrails |
| [07 — Job aggregation](docs/07-job-aggregation.md) | Legal sources per country, ingestion pipeline, dedup, alerts |
| [08 — Roadmap](docs/08-roadmap.md) | Phases, exit criteria, open decisions |
| [09 — Security](docs/09-security.md) | Threat model, controls, data protection (GDPR) |
| [10 — Testing strategy](docs/10-testing-strategy.md) | Test pyramid, AI evaluation, CI gates |
| [11 — Content & licensing policy](docs/11-content-licensing-policy.md) | Provenance labels, licence rules, takedown process |
| [12 — Source review (Nov 2026)](docs/12-source-review.md) | Analysis of the owner's captured tests & suggested resources |
| [Free & open-source stack](docs/FREE_AND_OPEN_SOURCE_STACK.md) | Every technology: licence, cost, resources, alternatives |

Licence: [MIT](LICENSE). Security reports: see [SECURITY.md](SECURITY.md).

## Core principles

1. **Free & open source first** — runs fully on a laptop with local models (Ollama). No paid API is required.
2. **Honest content** — every question is labelled `official_public`, `community_licensed`, `ai_generated`
   `user_created` or `personal_capture` (private). We never present invented questions as a real company's recruitment test.
3. **Legal data sourcing** — official APIs, RSS feeds and public ATS endpoints only; licences and ToS recorded per source.
4. **Modular monolith** — one FastAPI backend with strict module boundaries, one worker, one Next.js frontend.
   Easy to run locally, Kubernetes-ready later.
