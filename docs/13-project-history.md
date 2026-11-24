# 13 — Project history and traceability

A step-by-step record of what was built, why, and which concepts were applied, with links to the evidence
(pull requests, commits, files). Read it top to bottom to follow the project, or use the
[concept index](#concept-index) to find where a given idea is implemented.

Repository: `malekachouri/CareerPilot-AI` (public, MIT). Private content: `malekachouri/careerpilot-private-content`.
Pull requests (PRs) are listed by number; commits by their short hash on `main`.

## Summary timeline

| # | Date | Step | Evidence | Result |
|---|------|------|----------|--------|
| 1 | 16 Nov | Vision and constraints | Owner's prompts | 6 modules; free and open-source only |
| 2 | 16 Nov | Design documents (Prompt 1) | `d40f175`, `docs/01`–`11` | Architecture approved |
| 3 | 16 Nov | Review of the owner's tests and links | `9479bfb`, `docs/12-source-review.md` | Legal status of each source |
| 4 | 16 Nov | Private content repository | `ecffe98`, private repo | Captures kept out of the public repo |
| 5 | 16 Nov | Phase 0 — foundations | `820dd26` | Monorepo, auth, Docker Compose, CI |
| 6 | 16 Nov | Dependency maintenance | PRs #1–#4, `98a5faf`, `c05e2ff` | Valkey 9; Dependabot policy |
| 7 | 16–18 Nov | Phase 1 — Interview Tests Hub (Prompt 2) | PR #5 (`b75c6d7`, `a4d7362`) | Import engine, question bank, tests, analytics |
| 8 | 18 Nov | Phase 2 — AI Interview Coach (Prompt 3) | PR #6 (`f1917f5`, `f8abd19`, `912651c`) | 7 agents, evaluation engine, RAG, interviews |
| 9 | 18–20 Nov | Local installation by the owner | `1141a5d`, French guide | Runs on Windows + WSL, 16 GB RAM |
| 10 | 20 Nov | Tuning for a CPU-only laptop | PRs #7, #8 | One AI job at a time, token cap, call logs |
| 11 | 20 Nov | Lightweight coach mode | PR #9 | `COACH_COMPACT`, about half the output |
| 12 | 20 Nov | Fixes from real use | PRs #10, #11, #12, #13 | No praise for gibberish, varied problems, SQL lesson, timing logs |

---

## Step 1 — Vision and global constraints

**Goal.** A career platform for a DevOps / Cloud / AI engineer with six modules: Interview Tests Hub, Coding
Challenges, AI Interview Coach, English Academy, Global Job Radar, Career Analytics.

**Constraints set by the owner** (they apply to every later step):
- Free and open-source technology only: no paid API, subscription or paid AI provider; no trial account as
  permanent infrastructure; free hosting is not assumed to be unlimited; no exposed API keys.
- Before adding a dependency, check its licence, maintenance and cost, and record it in
  [`FREE_AND_OPEN_SOURCE_STACK.md`](FREE_AND_OPEN_SOURCE_STACK.md).
- Never invent real company recruitment tests. Always distinguish official, publicly available and
  AI-generated questions.
- Respect licences and terms of service; no scraping against them (e.g. LinkedIn). When content cannot be
  imported legally, store a reference and a link instead.
- Personality questionnaires are self-reflection tools, never clinical diagnoses.
- Do not fabricate references; protect user data.

**Concepts applied.** Requirements as explicit, testable constraints; *local-first* AI; legal compliance by
design.

## Step 2 — Design documents (Prompt 1)

**What was done.** Eleven design documents were written before any code and approved by the owner:

| Document | Content |
|----------|---------|
| [01 Functional specification](01-functional-specification.md) | Users, modules, features, acceptance criteria |
| [02 System architecture](02-system-architecture.md) | Frontend, backend, workers, auth, deployment |
| [03 Database design](03-database-design.md) | PostgreSQL schema with pgvector |
| [04 Project structure](04-project-structure.md) | Monorepo layout |
| [05 API design](05-api-design.md) | REST conventions and endpoints |
| [06 AI agents](06-ai-agents.md) | LLM abstraction, RAG, agents, guardrails |
| [07 Job aggregation](07-job-aggregation.md) | Legal job sources per country, ingestion, dedup, alerts |
| [08 Roadmap](08-roadmap.md) | Phases 0–8, exit criteria, decisions |
| [09 Security](09-security.md) | Threat model, controls, GDPR |
| [10 Testing strategy](10-testing-strategy.md) | Test pyramid, AI evaluation, CI gates |
| [11 Content and licensing policy](11-content-licensing-policy.md) | Provenance labels, licence rules, takedown |

**Decisions recorded** ([roadmap](08-roadmap.md#decisions-taken-nov-2026)): MIT licence, OpenTofu rather than
Terraform, Valkey rather than Redis, EN + FR interface, Qwen3 as default local model, local laptop first then
a low-cost VPS, own gVisor sandbox runner, invite-only first, Job Radar before Coding Challenges.

**Concepts applied.** Design before code; architecture decision records; modular monolith (one API with
clear modules, extractable later); open-source licence compatibility (permissive vs copyleft).

## Step 3 — Review of the owner's tests and suggested links

**What was done.** The four PDFs the owner supplied (captured recruitment tests and QCM) and the suggested
websites and GitHub repositories were analysed for content, legal status and reuse conditions. The result is
in [`12-source-review.md`](12-source-review.md).

**Concepts applied.** Source licensing (a public repository is not automatically reusable); the distinction
between *copying content* and *linking to it*; provenance as a first-class attribute of every question.

## Step 4 — Private content repository

**Decision.** The owner's captured tests stay in the separate private repository
`careerpilot-private-content` and never enter the public repository.

**What was done.**
- `tools/parse_capture.py` turns the captures into importable YAML: 216 questions in `captures/*.yaml`.
- `tools/check_public_similarity.py` checks that no public question reuses a captured one.
- In the application, provenance `personal_capture` is forced to private by a database check constraint.

**Concepts applied.** Separation of public and private data; defence in depth (convention, tooling and a
database constraint); similarity checks to prevent leaks.

## Step 5 — Phase 0: foundations (`820dd26`)

**What was built.**
- **Monorepo.** `apps/api` (Python, FastAPI) and `apps/web` (Next.js), with shared docs and content.
- **API core.** Settings from environment variables (pydantic-settings), async SQLAlchemy 2 with asyncpg,
  Alembic migrations, RFC 9457 problem responses, structured JSON logs (structlog), Prometheus metrics.
- **Authentication.** Argon2 password hashes; server-side sessions in Valkey keyed by HMAC; `httpOnly`
  cookie; CSRF double-submit token; login rate limiting; audit log; roles learner < contributor < reviewer <
  admin. Production refuses to start with insecure defaults.
- **Background jobs.** Celery with Valkey as the broker.
- **Docker Compose stack.** PostgreSQL 16 + pgvector, Valkey, migrations, API, worker, beat scheduler, web.
  Services are bound to `127.0.0.1`, with health checks.
- **CI (GitHub Actions).** Lint, type-check and tests for the API and the web app; an OpenAPI contract check;
  Trivy image scan and gitleaks secret scan; licence gates; a Compose end-to-end smoke test. Actions are
  pinned to commit SHAs.

**Concepts applied.** Twelve-factor configuration; secure session management (OWASP); CSRF protection;
RBAC; least privilege; supply-chain security (pinned actions, image scanning, secret scanning); time-ordered
UUIDv7 primary keys; infrastructure as code with Compose.

## Step 6 — Dependency maintenance (PRs #1–#4)

**What was done.** Dependabot proposed four upgrades:
- Valkey 8 → 9 (PR #3) and the `uv-build` range (PR #4) were merged.
- Python 3.15 (PR #1) and Node 26 (PR #2) were closed, because runtime major versions need a deliberate
  migration.

The Dependabot configuration now leaves runtime line upgrades to deliberate PRs (`98a5faf`), and the CI and
docs were aligned on Valkey 9 (`c05e2ff`).

**Concepts applied.** Automated dependency updates with a human policy; separating routine patches from
runtime migrations.

## Step 7 — Phase 1: Interview Tests Hub (Prompt 2, PR #5)

**What was built** (details in the [roadmap](08-roadmap.md#phase-1--delivered-tests-hub-prompt-2)):
- **Source integration engine.**
  - Adapters for GitHub repositories (licence detection, commit pinning), HTTPS files, local folders and
    link-only websites.
  - Parsers for JSON, YAML, CSV, Markdown, text and PDF.
  - Guide: [adding a test source](guides/adding-a-test-source.md).
- **Licence policy** (`content/licensing.py`, `decide()`). Each source is copied, link-only or sent to human
  review. A missing licence or a "no derivatives" licence means link-only.
- **Content model.**
  - Six provenance values: `official_public`, `community_licensed`, `original`, `ai_generated`,
    `user_created`, `personal_capture`.
  - Versioned questions, with attribution down to the file and line.
- **Deduplication.** A content hash plus trigram similarity (pg_trgm) on the stem and its context.
- **Taxonomy.** DevOps, Cloud, AI, Software Engineering and Recruitment Assessments, with aliases; 13
  company preparation pages.
- **Assessments.**
  - The deadline is enforced by the server, with auto-submit.
  - Options are shuffled per attempt with a stable seed.
  - Grading uses only the answer key; questionnaires are never scored.
- **Analytics.** Accuracy by topic and level, response time, repeated mistakes, knowledge gaps.
- **AI question generator.** A local model with schema validation and a blind self-check. Output is stored
  private and labelled unverified.
- **Content.** 55 original questions (CC BY 4.0) in 9 curated tests. The 216 private captures are imported
  into private collections.

**Problems found and fixed during the phase.**
- The first original questions reused scenarios from the private captures. They were rewritten, and the
  similarity checker was added.
- Every seed answer was "A", so always choosing the first option scored 57 %. This led to per-attempt
  option shuffling.
- Questions sharing a generic stem ("Which action should you take?") were flagged as duplicates. Dedup now
  uses stem + context.
- Options differing only by punctuation were judged identical. Option keys now keep symbols and case.

**Concepts applied.**
- Adapter and parser patterns.
- Licence compliance automation.
- Content provenance and versioning.
- Idempotent imports.
- Fuzzy matching with trigrams.
- Server-authoritative timing (the client is never trusted).
- Test-validity safeguards (answer position bias).

## Step 8 — Phase 2: AI Interview Coach and specialised agents (Prompt 3, PR #6)

**What was built** (as-built table in [06 AI agents](06-ai-agents.md)):
- **Seven agents**, each defined as data in `coach/agents/`: DevOps, Cloud, AI Engineering, System Design,
  Coding, HR, Psychometric. An agent has a persona, topics, extra rubric criteria and an evaluation focus.
  There are also six interview personas. Guide: [adding a coach agent](guides/adding-a-coach-agent.md).
- **Workflow.** A deterministic state machine (`coach/workflow.py`) with these steps:
  1. question;
  2. answer;
  3. evaluation;
  4. explanation;
  5. recommendation.

  Every model call is a Celery job on the `llm` queue, queued only **after the database commit**; the UI
  polls for the result. LangGraph was not used: the flows are short and linear, and explicit code is easier
  to test.
- **Evaluation engine** (`coach/evaluation.py`).
  - The model never overrides an answer key: an explanation that contradicts the key is discarded.
  - Open answers are scored 0–5 per criterion, and the overall score is computed in code, not taken from
    the model.
  - Citations must point to a retrieved passage, and a question never cites itself.
- **RAG.** Knowledge-base documents and chunks are searched with PostgreSQL full-text search and pgvector
  (HNSW) vectors, fused by reciprocal rank fusion. The sources are:
  - curated notes in `content/kb/`;
  - published explanations;
  - private user uploads.

  Embeddings come from `nomic-embed-text` (768 dimensions) via Ollama.
- **Personalisation.** Elo ratings per topic, fed by tests and coach answers. The coach targets the weakest
  topic first, at a difficulty of about 65 % expected success.
- **Interviews.** One question at a time, follow-up questions, and a final report.
- **Web UI.** Coach home and chat, a code editor (CodeMirror 6), and provenance labels on every AI-generated
  question.
- **Tooling.**
  - The `kb-reindex` CLI command.
  - A French step-by-step local guide ([installation-locale-fr.md](guides/installation-locale-fr.md)).
  - A coach check in the end-to-end smoke test.

**Problems found and fixed.**
- Jobs were queued before the transaction committed (race condition): they are now dispatched after commit.
- API responses served stale "pending" rows: the session is refreshed.
- AI explanations cited the question's own explanation: it is now excluded.
- The suggested "lesson" was the question itself: lessons now come only from notes, docs and uploads.

**Concepts applied.**
- LLM guardrails ("the key decides, the model explains").
- Structured outputs with a JSON schema.
- Retrieval-augmented generation with hybrid search.
- Grounded citations.
- Transactional outbox-style dispatch (queue after commit).
- Elo rating and adaptive difficulty.
- Agents as configuration.

## Step 9 — Local installation by the owner (18–20 Nov)

**What happened.**
- The owner installed the stack on Windows with WSL (16 GB RAM, 8 logical processors), following the French
  guide.
- `git clone` failed because it was run in `/`: the fix was to run `cd ~` first.
- Compose printed a harmless "pull access denied" for locally built images: `pull_policy` was added
  (`1141a5d`).
- Ollama was started with the `ai` profile; the models `qwen3:4b` and `nomic-embed-text` were pulled; 72
  knowledge-base chunks were embedded.

**Concepts applied.** Reproducible local environments; documentation written for the real user and their
platform.

## Step 10 — Tuning for a CPU-only laptop (PRs #7, #8)

**Observed.** Coach jobs took more than 5 minutes or timed out. Only 2.2 GB of RAM was free, swap was in use,
and two AI jobs ran in parallel.

**What was done.**
- **PR #7.**
  - A dedicated `worker-ai` service with concurrency 1, so model calls run one at a time.
  - A smaller context window (`LLM_NUM_CTX`).
  - The model stays loaded between steps (`keep_alive`), and thinking mode is off (`think: false`).
  - Ollama is limited to one parallel request.
  - A clear timeout message suggests freeing memory or using a smaller model.
  - The French guide gained a RAM / model table.
- **The owner switched to `qwen3:1.7b`.**
- **PR #8.**
  - A cap on generated tokens (`LLM_MAX_TOKENS`, Ollama `num_predict`), so a runaway generation stops.
  - An `llm_call` log line per call: duration, load time, tokens, stop reason.

**Measured.**
- First call: 102 s, of which about 49 s was loading the model.
- Later calls: about 50 s to generate a problem and 74 s to evaluate an open answer, at about 8.5 tokens/s.

**Concepts applied.**
- Capacity planning (RAM per model size).
- Serialising contended resources.
- Bounded work (token caps, timeouts).
- Observability first (measure before optimising).
- An earlier hypothesis of a runaway loop was disproved by the measurements.

## Step 11 — Lightweight coach mode (PR #9)

**Why.** On a CPU, the length of the output dominates the time.

**What was done.** With `COACH_COMPACT=true`:
- only the 6 core criteria are scored;
- feedback is short;
- concepts, the real-world example and common mistakes are dropped;
- 2 reference passages of 600 characters are sent instead of 4 of 1,500.

Compact explanations are cached under prompt version `coach-v1-compact` and regenerated when the full mode is
back on.

**Measured.** On a comparable evaluation, prompt tokens fell from 1,252 to 679 (−46 %) and output tokens from
569 to 252 (−56 %). The wall-clock time of that run was affected by a parallel Docker build; see step 12.

**Concepts applied.** Configurable quality/latency trade-off; cache versioning by prompt version.

## Step 12 — Fixes from real use (PRs #10–#13)

| PR | Observed by the owner | Root cause | Fix |
|----|-----------------------|------------|-----|
| #10 | The strings `vdfwfdvfd` and `edrftghyjuk` scored 100/100 | The small model graded the question, not the answer | A deterministic gate: fewer than 5 readable words, or letter salad, scores 0 without calling the model. Completeness is capped at 2/5 under 30 words. The prompt says to score only the delimited answer. |
| #10 | The same video-platform problem twice, labelled "Beginner" | The small model repeats one scenario | Each problem is set in a random business domain; a repeat is regenerated once |
| #11 | "Weakest topics" listed topics at 100 % | All practised topics were listed | Only topics below rating 1000 or under 80 % accuracy are listed |
| #11 | A SQL question linked to the system design checklist | No SQL note in the knowledge base | New CC BY 4.0 note `content/kb/sql-and-databases.md` |
| #11 | The recommendation appeared above the answer | Not reproduced: the server order was verified correct. It was most likely the previous question's message. | UUIDv7 made monotonic as an extra safeguard; order asserted in tests |
| #12 | A compact evaluation took 87 s instead of about 45 s | Unknown: the log did not separate the phases | `prompt_seconds`, `gen_seconds`, `tokens_per_s` added. They later showed 9.5–11.5 tokens/s, so the slow run was CPU contention. |
| #13 | One problem cost two model calls (30 s + 55 s) | The 80 % repeat threshold matched the small model's fixed sentence template | Threshold raised to 92 %: only near-identical repeats are regenerated |

**Concepts applied.**
- Never trust a small model's self-assessment: use deterministic pre-checks and caps.
- Root-cause analysis from logs.
- Admitting a wrong diagnosis (PR #11) and recording it.
- Regression tests for every fix.
- Tuning heuristics against real model behaviour.

**State at the end of step 12.** 88 automated API tests pass; `ruff` and `mypy` are clean. PR #13 is open.

---

## Concept index

| Concept | Where it is applied |
|---------|---------------------|
| Free and open-source only, with licence checks | [`FREE_AND_OPEN_SOURCE_STACK.md`](FREE_AND_OPEN_SOURCE_STACK.md); CI licence gates |
| Content provenance and licensing | `apps/api/src/careerpilot/modules/content/` (`licensing.py`, `models.py`); [11](11-content-licensing-policy.md) |
| Public / private data separation | Private repo; DB check on `personal_capture`; `check_public_similarity.py` |
| Deduplication (hash + trigram) | `modules/content/service.py`, pg_trgm |
| Server-authoritative timing, option shuffling | `modules/assessments/` |
| Secure sessions, CSRF, RBAC, rate limiting, audit | `modules/auth/`, `core/security.py`; [09](09-security.md) |
| Structured logs and metrics | `core/logging.py`, `core/metrics.py`, `llm_call` log line |
| Background jobs queued after commit | `core/jobs.py`, `coach/workflow.py` (`_queue`, `commit`) |
| LLM provider abstraction (local, no paid API) | `core/llm/__init__.py` (Ollama provider, embedder) |
| Structured outputs (JSON schema) | `coach/evaluation.py` (`*_SCHEMA`) |
| "The key decides, the model explains" | `coach/evaluation.py` (`grade_choice`, `enrich_closed`) |
| Deterministic answer gate and score caps | `coach/evaluation.py` (`answer_problem`, `SHORT_COMPLETENESS_CAP`) |
| Hybrid RAG (full-text + vectors, RRF) and grounded citations | `modules/kb/service.py`; `resolve_citations` |
| Elo ratings and adaptive difficulty | `coach/ratings.py` |
| Agents as data | `coach/agents/` |
| Compact mode and cache versioning | `COACH_COMPACT`; `prompt_version()` |
| Resource limits for CPU inference | `docker-compose.yml` (`worker-ai`, Ollama settings), `LLM_*` settings |
| Supply-chain security | `.github/workflows/ci.yml` (pinned SHAs, Trivy, gitleaks), Dependabot |
| Time-ordered, monotonic IDs | `core/db.py` (`uuid7`) |

## Open items

- Phase 1's exit criterion of 300+ reviewed public questions is not met (55 original questions so far).
- An automated evaluation dataset against a real model (docs/06 §6) is not built yet.
- The small model does not always match the problem's scale to its level; a larger model follows the
  instruction better.
- The French interface translation is pending.
- Next phase: 3, Job Radar ([07](07-job-aggregation.md)).
- Dependabot PRs #14–#16 are waiting for review.

## How to keep this file up to date

After each PR, add a row to the timeline and, if the change is significant, a short section. Each section
answers four questions: what was observed or asked, what was done, which concepts were applied, and where the
evidence is (PR, commit, files).
