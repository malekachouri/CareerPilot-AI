# CareerPilot AI

**AI-powered interview preparation & career intelligence platform — free, open-source and self-hostable.**

> Status: **Design phase (Phase 0).** No application code yet. The documents below are the
> proposed specification and are awaiting approval before implementation starts.

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
| [Free & open-source stack](docs/FREE_AND_OPEN_SOURCE_STACK.md) | Every technology: licence, cost, resources, alternatives |

## Core principles

1. **Free & open source first** — runs fully on a laptop with local models (Ollama). No paid API is required.
2. **Honest content** — every question is labelled `official_public`, `community_licensed`, `ai_generated`
   or `user_created`. We never present invented questions as a real company's recruitment test.
3. **Legal data sourcing** — official APIs, RSS feeds and public ATS endpoints only; licences and ToS recorded per source.
4. **Modular monolith** — one FastAPI backend with strict module boundaries, one worker, one Next.js frontend.
   Easy to run locally, Kubernetes-ready later.
