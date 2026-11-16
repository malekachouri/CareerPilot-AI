# 08 — Development Roadmap

Phases are ordered by value for the first user (a DevOps/Cloud/AI engineer preparing interviews and job hunting)
and by technical dependency. Each phase ends with a demo-able increment, green CI and updated docs.

| Phase | Scope | Exit criteria |
|-------|-------|---------------|
| **0 — Foundations** | Monorepo skeleton, Docker Compose (Postgres+pgvector, Valkey, API, worker, web), FastAPI core (config, DB, errors, logging, OTel), Alembic, Next.js shell with auth pages, built-in auth + RBAC, CI (lint, type-check, unit tests, Trivy, gitleaks, licence check), `.env.example`, `FREE_AND_OPEN_SOURCE_STACK.md` kept current | `make dev` brings everything up on a 16 GB laptop; register/login works; CI green |
| **1 — Tests Hub MVP** | Taxonomy for first track, content schema + provenance/licence model, YAML/JSON/CSV importer with validation & review queue, seed content (licensed banks + own questions), test catalogue, player (timed/untimed, autosave, resume), practice & exam modes, results with per-skill breakdown, custom test builder, company prep pages (official links + community topics) | 300+ reviewed questions across domains; full test flow E2E-tested |
| **2 — AI Coach v1** | `core/llm` abstraction + Ollama provider, model profiles, prompt registry, explain/hint/reveal/why-wrong flows (SSE), RAG over curated KB (pgvector hybrid search), similar-question generator + validator, eval harness | Runs offline on CPU; key-consistency eval ≥ 98% on eval set |
| **3 — Job Radar v1** | Source registry + legal review fields, connectors: Greenhouse, Lever, Ashby, SmartRecruiters, Personio, France Travail, BA Jobsuche, Arbeitnow, Remotive/RemoteOK, HN; normalisation, geo, categories, dedup, search UI with filters, saved searches, in-app + Web Push alerts, watchlist, application tracker, link-outs | ≥ 5 connectors live with fixtures; alerts delivered < 10 min after ingestion |
| **4 — Challenges & sandbox** | Sandbox service (gVisor runner; Piston for local dev), Monaco editor, Python/JS/SQL/Bash challenges, debug challenges, validator image (Dockerfile, K8s manifests, IaC, GitHub Actions), simulated K8s troubleshooting scenarios, logic games, XP/badges/leaderboards | Sandbox escape test suite passes; 50+ challenges |
| **5 — Analytics & adaptivity** | Elo skill ratings, adaptive mode, FSRS review, dashboard, weaknesses, readiness score, rules+LLM roadmap, job-match score & missing skills | Readiness score explained in UI; adaptive mode converges in simulations |
| **6 — English Academy** | Sections & CEFR placement, reading/listening content pipeline (public-domain/CC sources + TTS), writing tutor (LanguageTool + LLM), speaking (faster-whisper, fluency & pronunciation), vocab SRS (NGSL + technical glossary), interview English persona, voice mock interview | All 9 sections usable; STT works offline |
| **7 — Production hardening** | Helm chart + kind CI test, OpenTofu + Ansible single-server deployment, Caddy TLS, backups (pg_dump + restic), Prometheus/Grafana/Loki dashboards & alerts, load tests (Locust), ZAP baseline DAST, SonarQube Community scan, security review, GDPR export/delete, docs & runbooks | One-command deploy to a VPS; restore tested; no high/critical findings open |
| **8+ — Extensions** | Additional career tracks, contributor community features, mobile PWA polish, optional OIDC/Keycloak, optional GPU serving with vLLM, extract Job Radar into its own service if needed | — |

Indicative effort for one developer working with Claude Code: Phase 0 ≈ 1 week, Phases 1–3 ≈ 2–3 weeks each, Phases 4–7 ≈ 2–4 weeks each.

## Open decisions (need your approval)

| # | Question | Recommendation |
|---|----------|----------------|
| D1 | Project licence | **AGPL-3.0** if you want improvements by hosted forks shared back; **MIT/Apache-2.0** for maximum reuse. Note: some imported content may be CC BY-SA (share-alike applies to that content only). |
| D2 | Terraform vs OpenTofu | **OpenTofu** (MPL-2.0); code stays Terraform-compatible so both work |
| D3 | Redis vs Valkey | **Valkey** (BSD-3) |
| D4 | UI languages at launch | EN + FR |
| D5 | Default local models | Qwen3 4B/8B (Apache-2.0) as default; Mistral (Apache-2.0) alternative; Llama only if you accept its community licence |
| D6 | Deployment target | Local laptop first; then one low-cost VPS (≈ €5–15/month) or Oracle Cloud Always Free (not guaranteed capacity) |
| D7 | Sandbox engine | Own runner on gVisor (no privileged container) for any exposed deployment; Piston (MIT, needs `--privileged`) acceptable for local-only dev |
| D8 | Multi-user scope | Personal/small-group first (invite-only registration), public sign-up later |
| D9 | Phase order | Jobs (3) before Challenges (4) — swap if interview prep is more urgent than job search |
