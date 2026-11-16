# 01 — Functional Specification

## 1. Product vision

CareerPilot AI helps a technical professional **prepare for interviews, understand recruitment assessments,
improve professional and English skills, and discover jobs early** — in one self-hostable, free platform.

The first career track is **DevOps / Cloud / AI Engineer**. Tracks are data, not code: adding
"Data Engineer" or "Frontend Engineer" later means adding taxonomy + content, not new modules.

## 2. Personas & roles

| Role | Description | Key permissions |
|------|-------------|-----------------|
| `guest` | Not logged in | Browse public catalogue, try 1 sample test |
| `learner` | Registered user (default) | Take tests, coach, challenges, English, job radar, own analytics |
| `contributor` | Trusted learner | Propose questions / tests (go to review queue) |
| `reviewer` | Content moderator | Approve/reject imported, AI-generated and contributed content |
| `admin` | Operator | Sources, imports, users, feature flags, system settings |

The initial deployment is **single-user / small-group self-hosted**, but the model is multi-user from day one.

## 3. Content taxonomy (shared by all modules)

```
Track (DevOps/Cloud/AI Engineer)
 └── Domain (Kubernetes, Cloud, IaC, CI/CD, Monitoring, DevSecOps, AI Eng, MLOps, Backend, System Design, Linux, Scripting, HR/Soft skills, Logic/Psychometric)
      └── Skill (e.g. "K8s networking", "Terraform state", "RAG retrieval", "PromQL")
           └── Topic tags (free-form: "NetworkPolicy", "remote backend", "rerankers"...)
```

Cross-cutting attributes on every content item:

- `difficulty` — 1..5 (Beginner → Expert) plus a numeric calibrated rating (see Analytics).
- `seniority` — junior / mid / senior / staff.
- `question_type` — `mcq_single`, `mcq_multi`, `true_false`, `short_answer`, `open_ended`, `code`,
  `scenario` (multi-step troubleshooting), `ordering`, `matching`, `likert` (personality).
- `provenance` — `official_public`, `community_licensed`, `ai_generated`, `user_created` (see doc 11).
- `license_spdx`, `source_url`, `attribution` — mandatory for imported items.
- `verification_status` — `unverified`, `reviewed`, `validated_by_stats` (good discrimination in real usage).

### 3.1 Coverage of the first track

| Domain | Skills (initial) |
|--------|------------------|
| Linux & SysAdmin | processes, filesystems, permissions, systemd, networking, troubleshooting, performance |
| Scripting | Bash, Python automation |
| Containers | Docker images/layers, networking, volumes, security, Compose |
| Kubernetes | workloads, services/ingress, storage, RBAC, scheduling, troubleshooting, Helm, operators |
| CI/CD & GitOps | Jenkins, GitHub Actions, pipelines design, ArgoCD/Flux, release strategies |
| IaC & Config | Terraform/OpenTofu (state, modules, workspaces), Ansible (roles, idempotence) |
| Cloud | AWS, Azure, GCP core services, IAM, networking, cost; OpenStack |
| Observability | Prometheus/PromQL, Grafana, ELK/Loki, SLOs, alerting |
| DevSecOps | Trivy, SonarQube, SAST/DAST, OWASP Top 10, secrets management, supply chain |
| AI Engineering | Python, LLM fundamentals, prompting, RAG, embeddings, agents, evaluation |
| MLOps / LLMOps | MLflow, model serving (vLLM, Ollama), monitoring, feature stores |
| Backend | FastAPI, REST design, SQL, caching, queues |
| System Design | scalability, availability, consistency, security, cloud architecture |
| HR / Behavioural | STAR method, motivation, conflict, leadership, salary negotiation |
| Personality (practice) | Big-Five style self-assessment (IPIP public-domain items) |
| Psychometric / Logic | numerical, verbal, abstract (procedurally generated matrices), sequences, deduction |
| Verbal & reading | analogies, true/false/undetermined comprehension |
| Software testing & QA | test types, defects vocabulary, coverage, release strategies |
| Git & web basics | Git workflows, HTML/CSS/JS, React, Node.js (often in general dev tests) |

## 4. Module A — Interview Tests Hub

### Features
1. **Catalogue** — browse/filter by track, domain, skill, difficulty, type, provenance, company *topic tag*, duration.
2. **Test player** — timed (global or per question) or untimed; pause allowed only for untimed; autosave answers;
   keyboard navigation; flag-for-review; resume after disconnect.
3. **Test modes** — *Practice* (instant feedback per question), *Exam* (feedback at end), *Adaptive* (next question
   chosen by skill rating), *Spaced review* (due cards from mistakes).
4. **Custom tests** — user builds a test from filters ("20 Kubernetes questions, difficulty 3–4, 30 min") or by hand-picking.
5. **Company preparation pages** — for a company: links to its **official** public prep resources, publicly
   documented interview process, and **community-reported topics** (with source). Never a fake "Company X test".
6. **Import system (admin/reviewer)** — import JSON, CSV, YAML, Markdown; PDF only when the licence permits;
   each import is a job with preview, validation report, licence check, dedup and review queue.
7. **Question management** — CRUD, versioning (edits create a new version; attempts reference the version they used),
   bulk tagging, retire/restore, duplicate detection (embedding similarity).
8. **Personal question bank** — the user imports their own notes of tests they took (`personal_capture`), visible only to them. The coach can work on these items: it solves them, proposes an answer key that the user confirms, and explains. Captured tests often have no answer key, so keys start as `unverified`.
9. **Results** — score, time per question, per-skill breakdown, comparison with own history, explanation access.

### Acceptance criteria (MVP)
- A learner can take a 20-question timed MCQ test, refresh the browser mid-test without losing answers, and see a per-skill breakdown.
- Every question displays its provenance badge and, if imported, its source and licence.
- An admin can import a JSON file of 500 questions; invalid rows are reported, nothing is published before review.

## 5. Module B — Coding & Logic Challenges

### Features
1. **Code challenges** — Python, JavaScript/TypeScript, Java, Go, SQL, Bash (via sandbox). Editor: Monaco.
   Hidden + visible test cases; run vs submit; time/memory limits.
2. **Algorithms & data structures** track with progressive difficulty.
3. **Debugging challenges** — broken code + failing test; fix it.
4. **DevOps scenario challenges** (no real cloud required):
   - *Dockerfile*: build must succeed and pass hadolint/Trivy thresholds.
   - *Kubernetes manifests*: validated with kubeconform + kube-linter + custom policy assertions.
   - *Kubernetes troubleshooting*: simulated cluster state (events, logs, `kubectl` output) — choose actions
     step by step; optional "real mode" on a local kind cluster for self-hosters.
   - *IaC*: `tofu validate`/`tflint`/`checkov` checks; AWS behaviour mocked with Moto where needed.
   - *CI/CD*: write a GitHub Actions workflow validated by actionlint + structural assertions.
   - *Bash/Linux*: commands executed in an isolated container with assertions on resulting filesystem state.
5. **Logic games** — timed puzzles: sequences, matrices (procedurally generated), deduction grids, estimation, mental math.
6. **Gamification** — XP, streaks, badges, weekly challenges, leaderboards (opt-in, pseudonymous).

### Acceptance criteria (MVP)
- User submits Python solution → executed in sandbox with no network, ≤ 2 s CPU, ≤ 256 MB RAM → per-test-case result in < 5 s on a laptop.
- Malicious code (fork bomb, network call, file system escape attempt) is contained and reported as a failed run.

## 6. Module C — AI Interview Coach

### Features (per question)
1. **Explain the question** — reformulate, list concepts involved, without revealing the answer.
2. **Options** — for open questions, the coach can propose answer options (MCQ-ification) on request.
3. **Submit & evaluate** — MCQ correctness comes from the **stored answer key** (deterministic). Open answers
   are scored by the LLM against a rubric (stored per question, or generated + flagged).
4. **Reveal & explain** — correct answer, step-by-step reasoning, why each distractor is wrong, a real-world
   example ("in production this shows up as…").
5. **Similar questions** — generate N variants at same/higher difficulty (labelled `ai_generated`, unverified).
6. **Gap detection** — map errors to skills; update skill rating; propose focused drills.
7. **Mock interview mode** — conversational session with persona (Technical, System Design, HR/Behavioural,
   English-language), follow-up questions, timer, final report with scores per competency and transcript.
   Optional voice mode (Whisper STT + TTS).
8. **Grounding** — answers cite retrieved sources from the knowledge base (licensed docs, official documentation
   excerpts where licence permits, curated notes); the coach states uncertainty instead of inventing.

### Acceptance criteria (MVP)
- Works fully offline with a local model via Ollama (default: a ~4–8B instruct model, see stack doc).
- Explanations for MCQ never contradict the stored answer key (enforced by the prompt contract + output check).

## 7. Module D — English Academy

| Section | Features | Open tools |
|---------|----------|-----------|
| Speaking | Read-aloud & free-speech prompts, pronunciation feedback (phoneme-level comparison), fluency metrics (WPM, pauses, fillers), interview answer practice | faster-whisper, phonemizer/espeak-ng, LLM feedback |
| Listening | Audio + comprehension questions, dictation, speed control | Public-domain audio (LibriVox, VOA Learning English), TTS-generated dialogues |
| Reading | Graded texts (CEFR A2–C1), technical articles, comprehension & vocabulary-in-context | Simple English Wikipedia (CC BY-SA), Gutenberg, generated texts |
| Writing | Emails, cover letters, incident reports, README/docs; grammar + style + tone feedback | LanguageTool (self-hosted) + LLM rubric |
| Grammar | Explanations + exercises by topic & CEFR level | Generated + reviewed |
| Vocabulary | Spaced-repetition decks (FSRS): general (NGSL), technical (DevOps/Cloud/AI glossary), interview phrases | NGSL (CC BY-SA), own glossary |
| Professional English | Meetings, stand-ups, negotiation, emails | Generated + reviewed |
| Technical English | Explaining architecture, incidents, trade-offs | Coach + rubric |
| Interview English | Behavioural answers (STAR), self-introduction, salary talk | Mock interview persona |

Level placement test → CEFR estimate per skill (Speaking/Listening/Reading/Writing). UI languages: EN + FR (i18n-ready).

## 8. Module E — Global Job Radar

### Features
1. **Aggregation** from approved sources only (see doc 07), every 1–6 h per source depending on its rate rules.
2. **Normalisation** — title, company, location (country/city/remote type), seniority, salary (if given), skills extracted, posted date, apply URL (always links to the original).
3. **Deduplication** across sources (fuzzy title+company+location + embedding similarity).
4. **Filters** — countries: TN, FR, IT, PT, DE, AE, SA, QA, KW, BH, OM (+ Remote); categories: DevOps, Cloud, AI, MLOps, Platform, SRE, Backend, Software Engineer; seniority, remote/hybrid/onsite, visa/relocation mention, language required, date.
5. **Saved searches & alerts** — in-app notifications, Web Push, optional e-mail via user-configured SMTP; digest or instant.
6. **"Early discovery"** — company watchlist: poll a company's public ATS board directly (Greenhouse/Lever/Ashby/…) so new postings appear within the polling interval, often before aggregators.
7. **Match score** — job ↔ profile similarity + skill gap list ("you match 7/10 required skills; missing: ArgoCD, Go") with a link to targeted prep.
8. **Application kit** (idea taken from the MIT project ai-job-search, run on local models): evaluate a posting against the profile, tailor the CV (Markdown/LaTeX → PDF) and draft a cover letter. These are drafts that the user reviews, and nothing is ever sent automatically.
9. **Application tracker** — kanban: saved → applied → interview → offer/rejected, notes, dates.

## 9. Module F — Career Analytics

1. **Skill ratings** — Elo-style rating per skill updated after each graded attempt (question difficulty also rated → calibration).
2. **Dashboard** — progress over time, accuracy by domain, time per question, streaks, heatmap.
3. **Weakness identification** — lowest-rated skills with enough evidence; recurring error patterns (from coach).
4. **Interview readiness score** (0–100) per target role = weighted coverage × mastery × recency, with explanation of the formula shown to the user (no black box).
5. **Personalised roadmap** — ordered weekly plan (tests, challenges, English, reading) generated by rules + LLM wording; regenerated weekly or on demand.
6. **Export** — user can export all their data (JSON/CSV) and delete their account (GDPR).

## 10. Non-functional requirements

| Category | Requirement |
|----------|-------------|
| Cost | Runs on one machine with 16 GB RAM, no GPU, no paid service |
| Performance | p95 API < 300 ms (non-AI endpoints); LLM responses streamed, first token < 3 s on CPU for 4B model |
| Availability | Self-hosted single node; graceful degradation when LLM unavailable (tests still work) |
| Privacy | All user data stays on the operator's infrastructure; no telemetry by default |
| Accessibility | WCAG 2.1 AA target; keyboard-only test taking |
| i18n | EN and FR UI; content language tagged |
| Portability | `docker compose up` locally; Helm chart for Kubernetes |
| Observability | Metrics, logs, traces from day one (Prometheus, Loki, OpenTelemetry) |
