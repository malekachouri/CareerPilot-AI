# 04 — Project Structure (monorepo)

```
CareerPilot-AI/
├── README.md
├── LICENSE                       # project licence — to be decided (see roadmap open decisions)
├── Makefile                      # make dev | test | lint | migrate | seed | up | down
├── .env.example                  # every variable documented, no real secrets
├── docker-compose.yml            # profiles: core, ai, english, sandbox, observability
├── docker-compose.override.yml   # dev: bind mounts, hot reload
│
├── apps/
│   ├── web/                      # Next.js (App Router, TypeScript, Tailwind)
│   │   ├── src/app/
│   │   │   ├── (marketing)/      # landing, about, licences/credits page
│   │   │   ├── (auth)/           # login, register, reset
│   │   │   └── (app)/
│   │   │       ├── dashboard/
│   │   │       ├── tests/        # catalogue, player, results, builder
│   │   │       ├── challenges/   # list, editor, scenario player, leaderboard
│   │   │       ├── coach/        # chat, mock interview
│   │   │       ├── english/      # speaking, listening, reading, writing, vocab...
│   │   │       ├── jobs/         # radar, saved searches, watchlist, applications
│   │   │       ├── analytics/    # skills, readiness, roadmap
│   │   │       └── admin/        # sources, imports, review queue, users
│   │   ├── src/components/       # ui/ (shadcn), shared feature components
│   │   ├── src/lib/api/          # generated OpenAPI client (do not edit)
│   │   ├── src/i18n/             # en.json, fr.json
│   │   ├── tests/                # vitest unit + playwright e2e
│   │   └── Dockerfile
│   │
│   └── api/                      # FastAPI backend (API + worker share this code)
│       ├── pyproject.toml        # uv-managed
│       ├── alembic/              # migrations
│       ├── src/careerpilot/
│       │   ├── main.py           # API entrypoint
│       │   ├── worker.py         # Celery app entrypoint
│       │   ├── core/             # config, db, security, logging, telemetry, errors, events, pagination, ratelimit
│       │   │   └── llm/          # provider interface, ollama, openai_compatible, embeddings, prompts registry
│       │   ├── modules/
│       │   │   ├── auth/  users/  taxonomy/  content/  assessments/
│       │   │   ├── challenges/   # incl. sandbox client + validators
│       │   │   ├── coach/        # agents/ (LangGraph graphs), retrieval/, prompts/
│       │   │   ├── english/      # speech/, writing/, srs/
│       │   │   ├── jobs/         # connectors/ (one file per source type), normalize/, dedup/, alerts/
│       │   │   ├── analytics/  notifications/  admin/
│       │   │   └── <each>: api.py schemas.py service.py repository.py models.py tasks.py events.py
│       │   └── cli.py            # admin CLI: import, seed, reindex, create-admin
│       ├── tests/
│       │   ├── unit/  integration/  contract/  security/
│       │   └── fixtures/         # recorded HTTP cassettes for job connectors
│       └── Dockerfile
│
├── services/
│   ├── sandbox/                  # Piston config / custom runner, language packages, seccomp profiles
│   └── validators/               # image with kubeconform, kube-linter, hadolint, actionlint, tflint, checkov, trivy, tofu
│
├── content/                      # seed content as reviewed files (version-controlled)
│   ├── schema/                   # JSON Schemas for question, challenge, english item, source
│   ├── sources.yaml              # registry of content sources with licence metadata
│   ├── questions/<domain>/*.yaml
│   ├── challenges/<kind>/*/      # statement.md, tests, starter code
│   ├── english/
│   └── job_sources.yaml          # approved job sources (no secrets)
│
├── evals/                        # LLM evaluation datasets & runners (promptfoo-style, pytest-based)
│
├── infra/
│   ├── docker/                   # shared base images, Caddyfile
│   ├── helm/careerpilot/         # chart: api, worker, beat, web, sandbox; deps optional (postgres, valkey)
│   ├── k8s/kind/                 # kind cluster config for local/CI
│   ├── opentofu/                 # modules/ + envs/ (vps, oracle-free-tier example)
│   ├── ansible/                  # roles: base-hardening, docker, caddy, backups, monitoring-agent
│   ├── argocd/                   # Application manifests (optional GitOps)
│   └── monitoring/               # prometheus rules, grafana dashboards (json), loki/alloy config
│
├── scripts/                      # dev helpers (bootstrap, pull-models, backup/restore)
│
├── docs/                         # this design set + ADRs + runbooks
│
└── .github/
    ├── workflows/                # ci.yml, security.yml, images.yml, e2e.yml, helm.yml, license-check.yml
    ├── dependabot.yml
    ├── ISSUE_TEMPLATE/  PULL_REQUEST_TEMPLATE.md
    └── CODEOWNERS
```

Tooling: **uv** (Python deps, MIT/Apache), **ruff** (lint/format), **mypy** (strict on `core/`),
**pnpm** (JS deps), **ESLint + Prettier**, **pre-commit** hooks (ruff, eslint, gitleaks, yaml lint).
