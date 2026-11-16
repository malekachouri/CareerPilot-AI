# 10 — Testing Strategy

## 1. Test pyramid

| Level | Backend | Frontend | Target |
|-------|---------|----------|--------|
| Unit | pytest (services, grading, Elo, FSRS wrappers, normalisers, dedup, parsers) | Vitest + Testing Library (components, hooks) | ≥ 80% line coverage on `services` / domain logic |
| Integration | pytest + **Testcontainers** (real Postgres+pgvector, Valkey); httpx `AsyncClient` against the app | MSW-mocked API | every endpoint: happy path + authz (owner/other user/anon/role) |
| Contract | OpenAPI schema snapshot diff; **Schemathesis** property-based fuzzing of the API | TS client generated in CI must compile | no unreviewed breaking change |
| Connector | Recorded HTTP cassettes (vcrpy / respx) per job source; schema drift alert job runs weekly against live sources (not in PR CI) | — | each connector |
| E2E | — | **Playwright** against `docker compose` stack: register → test → coach (stub LLM) → job search → alert | critical journeys, run on PR (smoke) and nightly (full) |
| Sandbox security | Escape suite: fork bomb, infinite loop, memory bomb, network access, write outside tmp, read env/secrets, large output, privilege escalation attempts | — | 100% contained |
| Performance | **Locust** scenarios (catalogue, test-taking, job search) | Lighthouse CI (optional) | p95 < 300 ms at 50 concurrent users on reference server |
| Security | Bandit, Semgrep, Trivy, ZAP baseline, authz matrix tests | ESLint security plugin | see doc 09 |
| Accessibility | — | axe-core in Playwright | no serious violations on key pages |

## 2. Testing AI features

- **Deterministic in PR CI**: a `FakeLLMProvider` returns scripted/structured responses so graph logic, validation, retries and fallbacks are tested without a model.
- **Contract tests for prompts**: rendered prompts snapshot-tested; JSON schema of every structured output tested with valid/invalid samples (repair path).
- **Model evaluations (nightly / on demand)** in `evals/` with a small local model via Ollama in CI (CPU):
  - key-consistency of explanations (≥ 98%),
  - leak test: "explain" never reveals the key (100%),
  - rubric scoring correlation vs human-labelled set (Spearman ≥ 0.7),
  - generator→validator acceptance and duplicate rate,
  - RAG recall@5 on labelled queries,
  - results stored and compared to previous run; regression > 3 points fails the eval job.
- Human review sampling: 5% of AI-generated questions reviewed manually each week.

## 3. Content quality tests
- JSON Schema validation of every file in `content/` in CI.
- Licence gate: every item has `source_id`; source has approved licence; `derivatives_allowed=false` sources cannot have edited items.
- Answer-key sanity: MCQ has ≥ 1 correct option, options unique, no "all of the above" misuse lint.
- Duplicate detection report on each content PR.

## 4. Test data
- Factories (factory-boy / polyfactory) for users, questions, attempts, jobs.
- Seed command producing a realistic demo dataset (no real personal data).

## 5. CI pipeline (GitHub Actions — free for public repos)

```
on PR:     lint (ruff, eslint) → type-check (mypy, tsc) → unit → integration (testcontainers) → contract
           → build images → Trivy/gitleaks/licence → E2E smoke (compose) → helm lint + kind install smoke (paths: infra/**)
nightly:   full E2E, LLM evals (Ollama small model), ZAP baseline, Locust short run, connector drift check
on tag:    build, SBOM, sign, push to GHCR, release notes
```
Definition of done for any feature: tests at the relevant levels, docs updated, no new high/critical findings, CI green.
