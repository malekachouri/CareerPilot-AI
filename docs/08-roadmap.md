# 08 — Development Roadmap

Phases are ordered by value for the first user (a DevOps/Cloud/AI engineer preparing interviews and job hunting)
and by technical dependency. Each phase ends with a demo-able increment, green CI and updated docs.

| Phase | Scope | Exit criteria |
|-------|-------|---------------|
| **0 — Foundations** ✅ done | Monorepo skeleton, Docker Compose (Postgres+pgvector, Valkey, API, worker, web), FastAPI core (config, DB, errors, logging, OTel), Alembic, Next.js shell with auth pages, built-in auth + RBAC, CI (lint, type-check, unit tests, Trivy, gitleaks, licence check), `.env.example`, `FREE_AND_OPEN_SOURCE_STACK.md` kept current | `make dev` brings everything up on a 16 GB laptop; register/login works; CI green |
| **1 — Tests Hub MVP** ✅ done | Taxonomy for first track, content schema + provenance/licence model, YAML/JSON/CSV importer with validation & review queue, seed content (licensed banks + own questions), test catalogue, player (timed/untimed, autosave, resume), practice & exam modes, results with per-skill breakdown, custom test builder, company prep pages (official links + community topics) | 300+ reviewed questions across domains; full test flow E2E-tested |
| **2 — AI Coach v1** ✅ done (Prompt 3) | `core/llm` abstraction + Ollama provider, model profiles, prompt registry, explain/hint/reveal/why-wrong flows (SSE), RAG over curated KB (pgvector hybrid search), similar-question generator + validator, eval harness | Runs offline on CPU; key-consistency eval ≥ 98% on eval set |
| **3 — Job Radar v1** | Source registry + legal review fields, connectors: Greenhouse, Lever, Ashby, SmartRecruiters, Personio, France Travail, BA Jobsuche, Arbeitnow, Remotive/RemoteOK, HN; normalisation, geo, categories, dedup, search UI with filters, saved searches, in-app + Web Push alerts, watchlist, application tracker, link-outs | ≥ 5 connectors live with fixtures; alerts delivered < 10 min after ingestion |
| **4 — Challenges & sandbox** | Sandbox service (gVisor runner; Piston for local dev), Monaco editor, Python/JS/SQL/Bash challenges, debug challenges, validator image (Dockerfile, K8s manifests, IaC, GitHub Actions), simulated K8s troubleshooting scenarios, logic games, XP/badges/leaderboards | Sandbox escape test suite passes; 50+ challenges |
| **5 — Analytics & adaptivity** | Elo skill ratings, adaptive mode, FSRS review, dashboard, weaknesses, readiness score, rules+LLM roadmap, job-match score & missing skills | Readiness score explained in UI; adaptive mode converges in simulations |
| **6 — English Academy** | Sections & CEFR placement, reading/listening content pipeline (public-domain/CC sources + TTS), writing tutor (LanguageTool + LLM), speaking (faster-whisper, fluency & pronunciation), vocab SRS (NGSL + technical glossary), interview English persona, voice mock interview | All 9 sections usable; STT works offline |
| **7 — Production hardening** | Helm chart + kind CI test, OpenTofu + Ansible single-server deployment, Caddy TLS, backups (pg_dump + restic), Prometheus/Grafana/Loki dashboards & alerts, load tests (Locust), ZAP baseline DAST, SonarQube Community scan, security review, GDPR export/delete, docs & runbooks | One-command deploy to a VPS; restore tested; no high/critical findings open |
| **8+ — Extensions** | Additional career tracks, contributor community features, mobile PWA polish, optional OIDC/Keycloak, optional GPU serving with vLLM, extract Job Radar into its own service if needed | — |

### Phase 1 — delivered (Tests Hub, Prompt 2)
- **Source integration engine**: adapters for GitHub repositories (metadata, README and question-bank
  detection, licence from GitHub, commit pinning), HTTPS files, local folders and link-only websites. Parsers for
  JSON, YAML, CSV, Markdown task lists, plain text and PDF. Licence gate: copy, link only, or human review.
  Dedup by content hash and trigram similarity, versioned re-imports, attribution to file and line.
  Background jobs with reports. Guide: [adding a test source](guides/adding-a-test-source.md).
- **Categories**: all five groups of Prompt 2 (DevOps, Cloud, AI, Software Engineering, Recruitment
  Assessments), plus QA, Git and web basics found in real tests, with aliases for imported banks.
- **Formats**: multiple choice, multiple select, true/false, true/false/cannot tell, scenario, situational
  judgment, open-ended, coding/debugging (graded by the user until the Phase 4 sandbox), questionnaires (never
  scored). Interactive simulations are modelled; their player comes with Phase 4.
- **Company preparation**: 13 companies; collections are your private captures or practice questions labelled
  *"inspired by publicly documented recruitment topics"*. Official links are added only after review.
- **AI generator**: position, technology, level, count, duration and type. Local model (Ollama), schema
  validation, blind self-check, dedup. Output is stored private and unverified, apart from verified content.
- **UX**: library with search and filters, test details, server-timed countdown with auto-submit, question
  navigation, flags, keyboard, autosave and resume, results with explanations and why-wrong per option,
  self-grading, setting keys on your own captures, file import.
- **Analytics**: correct/incorrect, average response time, accuracy by topic and level, history, repeated
  mistakes, knowledge gaps.
- **Content**: 55 original questions in 9 curated tests (CC BY 4.0), checked against the private captures so
  none reuses their content. Your 216 captured questions are imported privately into 4 collections.
- **Not yet**: the planned exit criterion "300+ reviewed public questions" is not met (55 original). Next: import
  approved open banks and write more. UI translations (FR) moved to Phase 2, together with the coach UI.

### Phase 0 — delivered vs. planned
Delivered: monorepo; Docker Compose (Postgres 16 + pgvector, Valkey 9, one-shot migrations, API, Celery
worker and beat with the five queues, web); FastAPI core (settings with production safety checks, problem+json
errors, structured JSON logs with request ids, Prometheus `/metrics`, `/healthz` and `/readyz`); built-in auth
(Argon2id, server-side Valkey sessions, CSRF, login rate limiting, session rotation and revocation, audit log);
RBAC with four roles; admin CLI; Next.js shell (landing, register, login, dashboard, optimistic route guard,
security headers); typed API client generated from OpenAPI with a CI drift check; CI (ruff, strict mypy, pytest
on real services, vitest, ESLint, tsc, build, licence allow-lists, gitleaks, Trivy fs + image scans, Compose E2E
in a real browser); Dependabot; pre-commit.

Moved to later phases, on purpose:
| Item | Now planned in | Why |
|------|----------------|-----|
| OpenTelemetry tracing | Phase 7 (with Tempo/Grafana) | Metrics and request-id logs cover Phase 0; tracing pays off once there are async flows |
| UI translations EN/FR (next-intl) | Phase 1 | Few strings yet; added with the first real pages |
| TOTP 2FA, personal access tokens, password reset by e-mail | Phase 1 (2FA, tokens) and Phase 7 (e-mail) | Not needed for a single-user instance; e-mail needs SMTP |
| Caddy reverse proxy and TLS | Phase 7 | Local use goes through the Next.js proxy |

Indicative effort for one developer working with Claude Code: Phase 0 ≈ 1 week, Phases 1–3 ≈ 2–3 weeks each, Phases 4–7 ≈ 2–4 weeks each.

## Decisions taken (Nov 2026)
D1 licence **MIT** · D2 **OpenTofu** · D3 **Valkey** · D4 EN + FR UI · D5 Qwen3 4B/8B by default · D6 local first,
then a low-cost VPS · D7 own gVisor runner · D8 personal / invite-only first (`REGISTRATION_OPEN=false`) ·
D9 Jobs (phase 3) before Challenges (phase 4). Any of these can be revisited.

## Decision log (original proposals)

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
