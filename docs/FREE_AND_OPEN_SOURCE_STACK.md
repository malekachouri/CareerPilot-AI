# Free & Open-Source Stack

This file is the **source of truth for every dependency** of CareerPilot AI. No dependency is added to the project
without an entry here (licence, maintenance, cost). Paid APIs require explicit owner approval.

> Licences reflect the state known at design time (Nov 2026). Licences change (e.g. Redis 2024, Terraform 2023,
> Piper 2025) — **re-check before adding or upgrading**; the CI licence gate (`pip-licenses`, `license-checker`) enforces an allow-list.

## Legend

| Status | Meaning |
|--------|---------|
| 🟢 **OSS** | Completely free and open source (OSI-approved licence), self-hostable |
| 🟡 **Free tier** | Free with limitations (quotas, registration, attribution); not unlimited |
| 🔵 **OSS + paid options** | Open source core; vendor sells optional services/enterprise features we do not use |
| 🔴 **Proprietary / paid** | Not used unless explicitly approved; listed only to explain why it was avoided |

Licence-type notes: **AGPL-3.0** components (Grafana, Loki, k6) are used *unmodified as separate services* — no
obligation on our code. **GPL-3.0** CLIs (Ansible, hadolint, espeak-ng, phonemizer) are invoked as separate programs/tools.

---

## 1. Frontend

| Tech | Purpose | Licence | Status | Resources | Cost | Install | Alternatives |
|------|---------|---------|--------|-----------|------|---------|--------------|
| Next.js | Web framework (App Router, SSR) | MIT | 🔵 (Vercel hosting optional — not used) | ~300–500 MB RAM at runtime (standalone output) | €0 | `pnpm create next-app`; `output: "standalone"` Docker image | Remix/React Router (MIT), SvelteKit (MIT) |
| React | UI library | MIT | 🟢 | — | €0 | npm | Preact (MIT) |
| TypeScript | Typed JS | Apache-2.0 | 🟢 | — | €0 | npm | — |
| Tailwind CSS | Styling | MIT | 🔵 (paid UI kits not used) | — | €0 | npm | UnoCSS (MIT) |
| shadcn/ui + Radix UI | Accessible components (copied into repo) | MIT | 🟢 | — | €0 | `npx shadcn add` | Headless UI (MIT), Mantine (MIT) |
| TanStack Query | Server-state caching | MIT | 🔵 | — | €0 | npm | SWR (MIT) |
| openapi-typescript / openapi-fetch | Typed client from OpenAPI | MIT | 🟢 | — | €0 | npm (CI generation) | orval (MIT) |
| playwright (Node) | E2E smoke test in CI | Apache-2.0 | 🟢 | Chromium ~150 MB (CI only) | €0 | `pnpm exec playwright install chromium` | — |
| next-intl | i18n EN/FR | MIT | 🟢 | — | €0 | npm | react-i18next (MIT) |
| Monaco Editor | Code editor | MIT | 🟢 | ~5 MB bundle (lazy-loaded) | €0 | `@monaco-editor/react` | CodeMirror 6 (MIT, lighter) |
| Recharts | Charts | MIT | 🟢 | — | €0 | npm | Apache ECharts (Apache-2.0) |
| wavesurfer.js | Audio waveform / recording UI | BSD-3 | 🟢 | — | €0 | npm | native MediaRecorder |
| Zustand | Local state | MIT | 🟢 | — | €0 | npm | Jotai (MIT) |
| lucide-react | Icons | ISC | 🟢 | — | €0 | npm | Heroicons (MIT) |
| pnpm | Package manager | MIT | 🟢 | — | €0 | `corepack enable` | npm |

## 2. Backend

| Tech | Purpose | Licence | Status | Resources | Cost | Install | Alternatives |
|------|---------|---------|--------|-----------|------|---------|--------------|
| Python 3.12 | Runtime | PSF-2.0 | 🟢 | — | €0 | `uv python install 3.12` | — |
| uv | Dependency & venv manager | MIT / Apache-2.0 | 🟢 | — | €0 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | Poetry (MIT), pip-tools |
| FastAPI | REST API | MIT | 🔵 (FastAPI Cloud optional — not used) | API process ~150–300 MB RAM | €0 | `uv add fastapi` | Litestar (MIT) |
| Uvicorn | ASGI server | BSD-3 | 🟢 | — | €0 | `uv add uvicorn[standard]` | Granian (BSD-3) |
| Pydantic v2 / pydantic-settings | Validation, config | MIT | 🟢 | — | €0 | uv | msgspec (BSD-3) |
| SQLAlchemy 2 + asyncpg | ORM / driver | MIT / Apache-2.0 | 🟢 | — | €0 | uv | SQLModel (MIT) |
| Alembic | Migrations | MIT | 🟢 | — | €0 | uv | — |
| Celery (+ beat) | Background tasks, schedules | BSD-3 | 🟢 | worker ~200–400 MB per process | €0 | uv; Compose services `worker`, `beat` | Dramatiq (LGPL-3.0), arq (MIT), RQ (BSD-2) |
| httpx | HTTP client (connectors) | BSD-3 | 🟢 | — | €0 | uv | aiohttp (Apache-2.0) |
| structlog | JSON logging | MIT / Apache-2.0 | 🟢 | — | €0 | uv | loguru (MIT) |
| OpenTelemetry SDK | Traces/metrics | Apache-2.0 | 🟢 | — | €0 | uv | — |
| argon2-cffi | Password hashing | MIT | 🟢 | — | €0 | uv | passlib (BSD, unmaintained) |
| pyotp | TOTP 2FA | MIT | 🟢 | — | €0 | uv | — |
| Authlib | OIDC (later) | BSD-3 | 🔵 | — | €0 | uv | — |
| nh3 | HTML sanitisation | MIT | 🟢 | — | €0 | uv | bleach (Apache-2.0, deprecated) |
| lingua-py | Language detection | Apache-2.0 | 🟢 | ~100 MB with all models (load subset) | €0 | uv | fastText lid (MIT/CC BY-SA model) |
| fsrs (py-fsrs) | Spaced repetition | MIT | 🟢 | — | €0 | uv | SM-2 (algorithm, free) |
| pypdf | PDF text extraction (licensed imports) | BSD-3 | 🟢 | — | €0 | uv | pdfplumber (MIT) |
| redis (redis-py) | Valkey client (protocol-compatible) | MIT | 🟢 | — | €0 | uv | valkey-py (MIT) |
| prometheus-client | `/metrics` endpoint | Apache-2.0 | 🟢 | — | €0 | uv | OpenTelemetry metrics |
| email-validator | E-mail validation (Pydantic `EmailStr`) | Unlicense | 🟢 | — | €0 | uv | — |

## 3. Data stores

| Tech | Purpose | Licence | Status | Resources | Cost | Install | Alternatives |
|------|---------|---------|--------|-----------|------|---------|--------------|
| PostgreSQL 16 | Main DB, full-text search | PostgreSQL Licence | 🟢 | 1 vCPU, 512 MB–2 GB RAM; disk 5–20 GB | €0 | Image `pgvector/pgvector:pg16` | — |
| pgvector | Vector search (HNSW) | PostgreSQL Licence | 🟢 | inside Postgres | €0 | `CREATE EXTENSION vector` | Qdrant (Apache-2.0), ChromaDB (Apache-2.0), FAISS (MIT) |
| pg_trgm | Fuzzy matching | PostgreSQL Licence | 🟢 | inside Postgres | €0 | `CREATE EXTENSION pg_trgm` | — |
| **Valkey 9** | Cache, sessions, rate limits, Celery broker | BSD-3 | 🟢 | 64–256 MB RAM | €0 | Image `valkey/valkey:9-alpine` | Redis 8 (AGPL-3.0 / RSAL / SSPL tri-licence), KeyDB (BSD-3, low activity) |
| Local filesystem volume | Audio, imports, exports | — | 🟢 | disk | €0 | Docker volume | SeaweedFS (Apache-2.0), Garage (AGPL-3.0) for S3-compatible storage; MinIO (AGPL-3.0, community edition reduced in 2025 — not chosen) |

Redis note: Redis 7.4+ moved to RSALv2/SSPLv1 (not OSI); Redis 8 added AGPLv3 as an option. Valkey (Linux Foundation fork) stays BSD-3 and is protocol-compatible, so the code works with either.

## 4. AI / LLM

| Tech | Purpose | Licence | Status | Resources | Cost | Install | Alternatives |
|------|---------|---------|--------|-----------|------|---------|--------------|
| **Ollama** | Local LLM runtime (OpenAI-compatible + native API, structured outputs) | MIT | 🔵 (Ollama cloud models exist — **disabled/not used**) | see model table; CPU OK, GPU optional | €0 | Compose service `ollama/ollama`; `ollama pull qwen3:4b` | llama.cpp `llama-server` (MIT), LocalAI (MIT) |
| vLLM | High-throughput GPU serving (optional, later) | Apache-2.0 | 🟢 | NVIDIA GPU ≥ 16 GB VRAM for 7–8B | €0 software; GPU hardware/rental is a cost | Docker `vllm/vllm-openai` | SGLang (Apache-2.0), TGI (Apache-2.0) |
| LangGraph | Agent graphs, Postgres checkpointer | MIT | 🔵 (LangGraph Platform/LangSmith paid — **not used**) | — | €0 | uv | Plain state machines; LlamaIndex workflows (MIT) |
| langchain-text-splitters | Chunking | MIT | 🟢 | — | €0 | uv | own splitter |
| sentence-transformers | Embeddings & rerankers in-process | Apache-2.0 | 🟢 | +~500 MB RAM (torch CPU) | €0 | uv (CPU torch wheel) | fastembed (Apache-2.0, ONNX, lighter), Ollama embed |
| Hugging Face Hub (downloads) | Model download | Apache-2.0 (client) | 🟡 free downloads, rate-limited | disk | €0 | `huggingface-cli download` | Ollama registry |

### Models (licences vary per model — check each model card)

| Model | Use | Licence | Commercial OK | RAM (Q4, CPU) | Note |
|-------|-----|---------|---------------|---------------|------|
| Qwen3 4B | `fast` profile (explain, hints, classification) | Apache-2.0 | ✅ | ~3 GB | **Default** |
| Qwen3 8B | `quality` profile (grading, mock interview, generation) | Apache-2.0 | ✅ | ~5–6 GB | **Default** if RAM ≥ 16 GB |
| Mistral 7B / Mistral Small (24B) | Alternative | Apache-2.0 | ✅ | ~5 GB / ~14 GB | Small needs 32 GB RAM or GPU |
| Phi-4-mini | Alternative small | MIT | ✅ | ~3 GB | |
| Llama 3.x | Alternative | Llama Community Licence (not OSI) | ✅ with conditions (attribution, AUP, >700M MAU clause) | ~5 GB (8B) | Only if owner accepts licence |
| Gemma 3 | Alternative | Gemma Terms of Use (not OSI) | ✅ with use restrictions | varies | Only if owner accepts |
| intfloat/multilingual-e5-small | Embeddings (384-d, multilingual) | MIT | ✅ | ~0.5 GB | **Default** |
| BAAI/bge-m3 | Better multilingual embeddings (1024-d) | MIT | ✅ | ~2.3 GB | Upgrade option |
| BAAI/bge-reranker-base | Reranking | MIT | ✅ | ~1 GB | Optional |

CPU performance expectation: 4B Q4 ≈ 8–20 tokens/s on a modern 8-core laptop; 8B ≈ 4–10 tokens/s. Acceptable with streaming.

## 5. Speech & English learning

| Tech | Purpose | Licence | Status | Resources | Cost | Install | Alternatives |
|------|---------|---------|--------|-----------|------|---------|--------------|
| faster-whisper (CTranslate2) | Speech-to-text, word timestamps | MIT (Whisper weights MIT) | 🟢 | `small` model ~1 GB RAM, int8 CPU; `base` ~500 MB | €0 | uv; model auto-download | whisper.cpp (MIT), Vosk (Apache-2.0, lighter, less accurate) |
| Piper TTS | Text-to-speech | **GPL-3.0** (active fork `OHF-Voice/piper1-gpl`; original `rhasspy/piper` MIT, archived 2025). Voices: per-voice licence | 🟢 | ~100–200 MB, very fast on CPU | €0 | Separate container/CLI (GPL isolated) | **Kokoro-82M** (Apache-2.0, high quality, CPU OK); avoid Coqui XTTS (non-commercial model licence) |
| LanguageTool (self-hosted server) | Grammar/spell/style check | LGPL-2.1 | 🔵 (Premium cloud — not used) | Java, 1–2 GB RAM; optional n-gram data ~8 GB disk | €0 | Compose service (community image, e.g. `erikvl87/languagetool`) or official zip + `java -jar` | Harper (Apache-2.0, English, lightweight) |
| phonemizer + espeak-ng | Phoneme transcription for pronunciation scoring | GPL-3.0 | 🟢 | small | €0 | apt `espeak-ng`, uv `phonemizer` (isolated in media worker) | g2p_en (Apache-2.0) |
| wav2vec2 phoneme model (e.g. `facebook/wav2vec2-lv-60-espeak-cv-ft`) | Phoneme recognition for pronunciation | Apache-2.0 | 🟢 | ~1.3 GB RAM | €0 | HF download | Skip (fluency-only feedback) |

Content (see doc 11): IPIP (public domain), NGSL/NAWL (CC BY-SA 4.0), Tatoeba (CC BY 2.0 FR), LibriVox (public domain),
VOA Learning English (US public domain, verify per item), Simple English Wikipedia (CC BY-SA 4.0), Common Voice (CC0), GeoNames (CC BY 4.0).

## 6. Code execution & DevOps challenge validators

| Tech | Purpose | Licence | Status | Resources | Cost | Install | Alternatives |
|------|---------|---------|--------|-----------|------|---------|--------------|
| Piston | Multi-language code execution engine | MIT | 🟢 | 1–2 vCPU, 1–2 GB RAM + language packages disk (~1–5 GB) | €0 | Docker `ghcr.io/engineer-man/piston` (privileged requirement reviewed; prefer gVisor runner if not acceptable) | Judge0 CE (GPL-3.0), own runner |
| gVisor (runsc) | Sandboxed container runtime | Apache-2.0 | 🟢 | small overhead | €0 | Install runsc, register Docker runtime | Kata Containers (Apache-2.0), nsjail (Apache-2.0), Firecracker (Apache-2.0) |
| kubeconform | K8s manifest schema validation | Apache-2.0 | 🟢 | tiny | €0 | static binary in validators image | kubeval (archived) |
| kube-linter | K8s best practices | Apache-2.0 | 🟢 | tiny | €0 | binary | Polaris (Apache-2.0) |
| hadolint | Dockerfile lint | GPL-3.0 | 🟢 | tiny | €0 | binary | Trivy config |
| actionlint | GitHub Actions lint | MIT | 🟢 | tiny | €0 | binary | — |
| OpenTofu (`tofu validate`) | IaC challenges | MPL-2.0 | 🟢 | tiny | €0 | binary | Terraform (BUSL) |
| tflint | Terraform/OpenTofu lint | MPL-2.0 | 🟢 | tiny | €0 | binary | — |
| Checkov | IaC security policies | Apache-2.0 | 🔵 (Prisma Cloud paid — not used) | ~300 MB | €0 | pip in validators image | Trivy config, KICS (Apache-2.0) |
| Moto | AWS API mocking for IaC/boto challenges | Apache-2.0 | 🟢 | small | €0 | pip | LocalStack (community edition licensing/registration changed — not relied on) |
| kind | Optional real K8s scenarios / CI | Apache-2.0 | 🟢 | ~2 GB RAM per cluster | €0 | `go install` / binary | k3d (MIT), minikube (Apache-2.0) |

## 7. DevOps, infrastructure & deployment

| Tech | Purpose | Licence | Status | Resources | Cost | Install | Alternatives |
|------|---------|---------|--------|-----------|------|---------|--------------|
| Docker Engine (Moby) | Containers | Apache-2.0 | 🟢 | — | €0 | `get.docker.com` on Linux | Podman (Apache-2.0) |
| Docker Desktop | — | Proprietary | 🔴 paid for companies > 250 staff or > $10M revenue | — | — | **Not required** | macOS/Windows: Rancher Desktop (Apache-2.0), Colima (MIT), Podman Desktop (Apache-2.0); Windows: WSL2 + Docker Engine |
| Docker Compose v2 | Local & single-server orchestration | Apache-2.0 | 🟢 | — | €0 | Docker plugin | podman-compose (GPL-2.0) |
| Caddy | Reverse proxy, automatic HTTPS | Apache-2.0 | 🟢 | ~30 MB | €0 | Compose service `caddy:2` | Traefik (MIT), Nginx (BSD-2) |
| Let's Encrypt | TLS certificates | free service (ISRG) | 🟡 free, rate limits | — | €0 | automatic via Caddy | ZeroSSL free tier |
| Kubernetes | Orchestration (later) | Apache-2.0 | 🟢 | — | €0 software | — | — |
| k3s | Lightweight single-node K8s for self-hosting | Apache-2.0 | 🟢 | 512 MB+ RAM overhead | €0 | `curl -sfL https://get.k3s.io \| sh -` | MicroK8s (Apache-2.0), k0s (Apache-2.0) |
| kind / Minikube | Local clusters, CI | Apache-2.0 | 🟢 | 2–4 GB RAM | €0 | binary | k3d (MIT) |
| Helm | Packaging | Apache-2.0 | 🟢 | — | €0 | binary | Kustomize (Apache-2.0) |
| Argo CD | GitOps (optional) | Apache-2.0 | 🟢 | ~500 MB–1 GB RAM | €0 | Helm chart | Flux (Apache-2.0, lighter) |
| **OpenTofu** | IaC | MPL-2.0 | 🟢 | — | €0 | `tofu` binary | Terraform CLI (BUSL-1.1, free to use for non-competing purposes; not OSI) |
| Ansible | Server provisioning/hardening | GPL-3.0 | 🔵 (AAP paid — not used) | — | €0 | `uv tool install ansible-core` | Pyinfra (MIT) |
| GitHub Actions | CI/CD | Proprietary service | 🟡 free & unlimited standard runners for **public** repos; private repos: 2,000 min/month on Free plan | — | €0 if repo public | `.github/workflows/` | Forgejo Actions (GPL-3.0) / Woodpecker CI (Apache-2.0) self-hosted; self-hosted GH runners (free) |
| GHCR | Container registry | Proprietary service | 🟡 free for public images | — | €0 public | `docker push ghcr.io/...` | Self-hosted Harbor (Apache-2.0), Zot (Apache-2.0) |
| restic | Encrypted backups | BSD-2 | 🟢 | small | €0 software; off-site storage may cost | binary | BorgBackup (BSD-3) |

## 8. Observability

| Tech | Purpose | Licence | Status | Resources | Cost | Install | Alternatives |
|------|---------|---------|--------|-----------|------|---------|--------------|
| Prometheus | Metrics | Apache-2.0 | 🟢 | ~200–500 MB RAM | €0 | Compose profile `observability` | VictoriaMetrics (Apache-2.0) |
| Grafana OSS | Dashboards | AGPL-3.0 | 🔵 (Grafana Cloud — not used) | ~150–300 MB | €0 | Compose / Helm | Perses (Apache-2.0) |
| Loki | Logs | AGPL-3.0 | 🔵 | ~200–500 MB | €0 | Compose / Helm | OpenSearch (Apache-2.0, heavier), ELK (Elastic licence/AGPL options) |
| Grafana Alloy | Log/metric/trace collector (Promtail is EOL) | Apache-2.0 | 🟢 | ~100 MB | €0 | Compose | OpenTelemetry Collector (Apache-2.0), Vector (MPL-2.0) |
| Tempo (optional) | Traces | AGPL-3.0 | 🔵 | ~200 MB | €0 | Compose | Jaeger (Apache-2.0) |
| Alertmanager | Alerts | Apache-2.0 | 🟢 | small | €0 | Compose | Grafana alerting |
| ntfy (optional) | Self-hosted push notifications | Apache-2.0 / GPL-2.0 dual | 🔵 (ntfy.sh hosted tiers — not required) | ~30 MB | €0 | Compose | Gotify (MIT) |
| Umami (optional) | Privacy-friendly analytics | MIT | 🔵 | ~200 MB | €0 | Compose | Plausible CE (AGPL-3.0) |

## 9. Security & quality tooling

| Tech | Purpose | Licence | Status | Resources | Cost | Install | Alternatives |
|------|---------|---------|--------|-----------|------|---------|--------------|
| Trivy (pinned 0.75.0 by image digest) | Vuln/IaC/secret/licence scanning | Apache-2.0 | 🔵 (Aqua commercial — not used) | ~500 MB DB cache | €0 | `aquasecurity/trivy-action` / binary | Grype (Apache-2.0) |
| SonarQube Community Build | Code quality/SAST | LGPL-3.0 | 🔵 (Developer/Enterprise editions paid — not used) | **2–4 GB RAM** + Postgres; run on demand, not 24/7 | €0 | Compose profile `quality` | SonarCloud (free for public repos, 🟡) |
| Semgrep CE | SAST | Engine LGPL-2.1; registry rules under Semgrep Rules Licence (internal use OK) | 🔵 | small | €0 | uv tool / action | Opengrep (LGPL-2.1 fork) |
| Bandit | Python SAST | Apache-2.0 | 🟢 | tiny | €0 | uv | Ruff `S` rules |
| gitleaks | Secret detection | MIT | 🟢 | tiny | €0 | pre-commit + action | TruffleHog (AGPL-3.0) |
| actionlint | GitHub Actions workflow lint (run on demand: `uvx --from actionlint-py actionlint`) | MIT | 🟢 | tiny | €0 | uvx | — |
| pip-audit | Python CVEs | Apache-2.0 | 🟢 | tiny | €0 | uv tool | Trivy |
| OWASP ZAP | DAST | Apache-2.0 | 🟢 | ~1 GB | €0 | Docker `zaproxy/zap-stable` | Nuclei (MIT) |
| Syft | SBOM | Apache-2.0 | 🟢 | tiny | €0 | action | Trivy SBOM |
| cosign (Sigstore) | Image signing | Apache-2.0 | 🟢 (public Sigstore infra free) | tiny | €0 | action | Notation (Apache-2.0) |
| Dependabot | Dependency updates | GitHub service | 🟡 free | — | €0 | `.github/dependabot.yml` | Renovate (AGPL-3.0, self-hostable) |
| Ruff / mypy / ESLint / Prettier / pre-commit | Lint, types, format | MIT | 🟢 | — | €0 | uv / pnpm | — |
| pip-licenses / license-checker | Licence gate in CI | MIT / BSD-3 | 🟢 | — | €0 | uv / pnpm | Trivy licence scan |

## 10. Testing

| Tech | Purpose | Licence | Status | Install | Alternatives |
|------|---------|---------|--------|---------|--------------|
| pytest (+ pytest-asyncio, pytest-cov) | Python tests | MIT / Apache-2.0 | 🟢 | uv | — |
| Testcontainers (Python) | Real Postgres/Valkey in tests | Apache-2.0 | 🔵 (Testcontainers Cloud — not used) | uv | docker compose in CI |
| polyfactory / factory-boy | Test data | MIT | 🟢 | uv | — |
| respx / vcrpy | HTTP mocking / cassettes | BSD-3 / MIT | 🟢 | uv | — |
| Schemathesis | API fuzzing from OpenAPI | MIT | 🔵 | uv | — |
| Vitest + Testing Library | Frontend unit | MIT | 🟢 | pnpm | Jest (MIT) |
| MSW | API mocking (frontend) | MIT | 🟢 | pnpm | — |
| Playwright | E2E (Chromium bundled) | Apache-2.0 | 🟢 | pnpm | Cypress (MIT, cloud paid) |
| axe-core | Accessibility | MPL-2.0 | 🟢 | pnpm | Pa11y (LGPL-3.0) |
| Locust | Load tests | MIT | 🟢 | uv | k6 (AGPL-3.0) |

## 11. Data & job sources (external services)

| Source | Status | Cost | Limitations |
|--------|--------|------|-------------|
| Greenhouse / Lever / Ashby / SmartRecruiters / Recruitee / Personio public boards | 🟡 free public endpoints | €0 | Per company only; be polite with rate; terms per vendor |
| France Travail API (Offres d'emploi) | 🟡 free with registration | €0 | Quotas, OAuth2 client credentials |
| Bundesagentur für Arbeit Jobsuche API | 🟡 free | €0 | Unofficial-documented rate limits; client-id header |
| Adzuna API | 🟡 free tier | €0 | Daily quota; attribution; not all target countries |
| Jooble API | 🟡 free key on request | €0 | Terms to verify for storage |
| Arbeitnow / Remotive / RemoteOK / Himalayas / WWR RSS | 🟡 free public | €0 | Attribution & request-rate rules |
| HN API (Firebase) / Algolia HN Search API | 🟡 free public | €0 | Rate limits |
| LinkedIn / Indeed / Glassdoor / Bayt / GulfTalent / Tanitjobs | 🔴 no authorised free API | — | **Link-out only** |

## 12. Hosting options & unavoidable costs

| Option | Status | Cost | Limitations / risks |
|--------|--------|------|---------------------|
| Own laptop / home server | 🟢 | €0 (electricity) | Not reachable publicly unless tunnelled; uptime depends on you |
| Cloudflare Tunnel / Tailscale (free plans) for remote access | 🟡 free tier, proprietary services | €0 | Vendor terms; alternatives: WireGuard (GPL-2.0) self-managed, Headscale (BSD-3) |
| Oracle Cloud "Always Free" (Ampere A1: up to 4 OCPU / 24 GB RAM) | 🟡 free tier | €0 | Capacity often unavailable in popular regions; idle instances can be reclaimed; account can be terminated; card required — **not guaranteed permanent infrastructure** |
| Low-cost VPS (e.g. 4 vCPU / 8–16 GB RAM) | 🔴 paid but cheap | ≈ €5–15/month | Recommended for an always-on public instance; without local LLM, 8 GB is enough |
| Domain name | 🔴 paid | ≈ €10/year | Optional (free subdomains via DuckDNS etc. exist) |
| GPU | 🔴 paid | hardware or hourly rental | **Optional** — only for faster/larger models; CPU works |
| SMTP e-mail | 🟡/🔴 | free tiers exist (proprietary, daily caps) | Optional; in-app + Web Push + ntfy are free alternatives; self-hosting mail has deliverability problems |
| Vercel / Netlify free tiers | 🟡 | €0 | Vercel Hobby is **non-commercial only**; not needed (Next.js runs in our container) |

## 13. Resource budget (Docker Compose profiles)

| Profile | Services | RAM (approx.) |
|---------|----------|---------------|
| `core` | postgres, valkey, api, worker, beat, web, caddy | ~2–3 GB |
| `ai` | ollama + qwen3:4b (+ embeddings in worker) | +3.5–4 GB (8B: +6–7 GB) |
| `sandbox` | piston / runner + validators | +1–2 GB |
| `english` | languagetool, media worker (faster-whisper small, TTS) | +2–3 GB |
| `observability` | prometheus, grafana, loki, alloy | +1–1.5 GB |
| `quality` (on demand) | sonarqube + its postgres | +3–4 GB |

**Minimum dev machine**: 4 cores, 16 GB RAM, 30 GB free disk, no GPU (run `core` + `ai` + one more profile at a time).
**Comfortable**: 8 cores, 32 GB RAM.

## 13b. Notes from Phase 0

- **Supply chain**: GitHub Actions are pinned to commit SHAs and tools to versions or image digests (Trivy). Tags
  can be moved by an attacker, as happened to some security-tool actions in 2026. Dependabot proposes updates weekly.
- **sharp / libvips (LGPL-3.0)**: Next.js ships libvips unmodified and dynamically linked for image optimisation.
  This is allowed as a reviewed exception in `apps/web/scripts/check-licenses.mjs`.
- **uv in the API image** is installed from PyPI (`pip install uv==…`), not copied from the ghcr.io image, so the
  build only needs PyPI access.

## 14. Rules for adding a dependency

1. Add an entry to this file (licence, status, maintenance — last release < 12 months, open-issues trend — cost, resources, alternatives).
2. Licence must be in the allow-list: MIT, BSD-2/3, Apache-2.0, ISC, MPL-2.0, PSF, PostgreSQL, Unlicense, CC0; LGPL/GPL/AGPL only as separate processes/services or with owner approval.
3. No paid API, trial account or "free tier" as hard dependency without explicit owner approval; every free-tier service must be optional or replaceable.
4. Never commit secrets; free-tier API keys go into the environment / secret store.
