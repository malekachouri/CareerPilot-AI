# 09 — Security Requirements

## 1. Threat model (top risks)

| # | Threat | Asset | Controls |
|---|--------|-------|----------|
| T1 | Malicious code in challenges escapes sandbox | Host, DB, secrets | Isolated sandbox service, gVisor/nsjail, no network, non-root, seccomp, cgroups limits (CPU, mem, pids), read-only FS, ephemeral containers, separate network segment, escape test suite |
| T2 | Account takeover | User data | Argon2id, login rate-limit + progressive delay, TOTP (mandatory for admin), session rotation, breached-password check (offline k-anonymity list optional), secure cookies |
| T3 | Prompt injection via job descriptions / imported content / KB | Coach integrity, data leakage | Untrusted-data wrapping, no state-mutating tools for LLM, output schema validation, no secrets in prompts, per-user data scoping in retrieval |
| T4 | XSS via imported Markdown / job HTML | Users' sessions | Server-side sanitisation (nh3), Markdown rendered with safe renderer (no raw HTML), strict CSP, Trusted Types where possible |
| T5 | IDOR (reading others' attempts, sessions, applications) | Privacy | Ownership checks in service layer, UUIDs, automated authorisation tests per endpoint |
| T6 | Answer-key leakage | Assessment integrity | Keys never in question/attempt responses before submission; separate response schemas; tests asserting absence |
| T7 | SSRF via source URLs / imports | Internal network | Allow-listed source hosts, egress proxy for worker, block private IP ranges, no user-supplied fetch URLs except admin-approved sources |
| T8 | Malicious file uploads (PDF/CSV/audio) | Worker | Size/type limits, magic-byte checks, parsing in worker with timeouts, PDFs parsed in a restricted process, no macro formats |
| T9 | Secret leakage | API keys (free-tier sources, SMTP) | Env/secret store only, `.env` git-ignored, gitleaks pre-commit + CI, Kubernetes Secrets (+ optional SOPS/age), secrets never logged |
| T10 | Supply-chain compromise | Build & runtime | Lockfiles (uv.lock, pnpm-lock), Dependabot, Trivy fs/image scans, pinned base images by digest, SBOM (Syft) per image, cosign signing, minimal permissions in GitHub Actions, pinned action SHAs |
| T11 | Abuse / DoS of CPU-bound LLM & sandbox | Availability | Per-user and global rate limits, concurrency caps, queue depth limits, timeouts |
| T12 | ToS / licence violation | Legal | Source registry with legal review, licence enforcement in importer, takedown process (doc 11) |

## 2. Application security controls (OWASP ASVS L2 as target)

- Input validation with Pydantic (strict types, length limits) on every endpoint; output schemas whitelist fields.
- SQL only via SQLAlchemy parameterised queries.
- CSRF protection for cookie auth; CORS restricted to the web origin.
- Security headers via reverse proxy: CSP, HSTS, X-Content-Type-Options, Referrer-Policy, Permissions-Policy (microphone only on English/coach pages).
- Error responses without stack traces in production; correlation IDs instead.
- Audit log for admin actions, role changes, imports, source approvals.
- File storage paths are generated server-side (no user-controlled paths).

## 3. Data protection & privacy (GDPR-aligned)

- Data minimisation: no CV upload required; profile fields optional.
- Personal data inventory documented; lawful basis = contract/consent for self-hosted users.
- Encryption in transit (TLS via Caddy/Let's Encrypt, free) and at rest (disk encryption on host; TOTP secrets encrypted at app level with a key from env).
- Audio retention 30 days default; user can delete any recording, transcript, coach session.
- Export & delete account endpoints; deletion cascades within 30 days including backups rotation.
- No third-party analytics/telemetry by default; if enabled, self-hosted (e.g. Umami, MIT) with IP anonymisation.
- No user data is ever sent to an external LLM unless the operator explicitly enables such a provider; the UI then shows it.

## 4. Infrastructure security

- Containers: non-root, read-only root FS where possible, drop all capabilities, no privileged containers (sandbox uses gVisor runtime, not `--privileged`).
- Network: only reverse proxy exposed; DB/Valkey/Ollama on internal networks; Kubernetes NetworkPolicies default-deny.
- Host hardening via Ansible: SSH keys only, fail2ban, unattended security upgrades, UFW/nftables.
- Backups: encrypted (restic), off-site copy, restore drill each release.
- Kubernetes: Pod Security Admission `restricted`, resource limits, separate namespace for sandbox.

## 5. Security in CI/CD

| Check | Tool (free/OSS) | Gate |
|-------|-----------------|------|
| Secrets | gitleaks | block |
| Python SAST | Bandit, Ruff security rules (S) | block on high |
| Multi-language SAST | Semgrep CE (with OSS-licensed rules) | report → block high later |
| Dependencies | Trivy fs, pip-audit, pnpm audit | block critical |
| Container images | Trivy image | block critical |
| IaC | Checkov / Trivy config, tflint, kube-linter | block high |
| Dockerfiles | hadolint | warn |
| Code quality | SonarQube Community Build (self-hosted, optional) | report |
| DAST | OWASP ZAP baseline against compose stack | nightly report |
| Licences | `pip-licenses` + `license-checker` (pnpm) against allow-list | block non-approved |

## 6. Vulnerability management
`SECURITY.md` with private disclosure (GitHub security advisories, free), patch SLA: critical 7 days, high 30 days.
