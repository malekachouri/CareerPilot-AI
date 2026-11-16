# 07 — Job Aggregation Strategy (Global Job Radar)

## 1. Legal & ethical rules (non-negotiable)

1. **Only sources with `legal_status = approved`** in the source registry are polled. Approval requires: terms of use read
   and linked, permitted use documented, rate limits and attribution requirements recorded, reviewer + date.
2. **No scraping in violation of ToS** — LinkedIn, Indeed, Glassdoor, Bayt, GulfTalent, Naukrigulf, Tanitjobs, Keejob etc.
   are **link-out only** (deep links to *their* search pages pre-filled with the user's filters) unless an official API/partnership exists.
3. Respect `robots.txt`, rate limits, `ETag`/`If-Modified-Since`; identify with a descriptive User-Agent (generic project name + operator-configurable contact).
4. Never bypass logins, captchas, paywalls; never store credentials of third-party sites for users.
5. Always link to the original posting for applying; show attribution where required ("Jobs by X").
6. Store descriptions only as permitted; otherwise store a short summary + link. Raw payloads expire after 30 days.
7. API keys of free-tier sources are operator-provided secrets (env/secret store), never committed.

> ⚠️ The source list below reflects public information known at design time. **Each source must be re-verified
> (terms, availability, coverage, quotas) during Phase 3 before activation.** Status column is a hypothesis, not a legal opinion.

## 2. Source tiers

### Tier 1 — Public ATS job-board endpoints (best for "early discovery")
Companies publish these boards precisely so that jobs are distributed. We poll a **curated company list** (seeded with
companies hiring DevOps/Cloud/AI in target countries + remote-friendly companies; users can add companies to their watchlist).

| ATS | Public endpoint pattern (unauthenticated) | Notes |
|-----|-------------------------------------------|-------|
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` | Job Board API, documented as public |
| Lever | `api.lever.co/v0/postings/{company}?mode=json` | Postings API, public |
| Ashby | `api.ashbyhq.com/posting-api/job-board/{name}` | Public job posting API |
| SmartRecruiters | `api.smartrecruiters.com/v1/companies/{id}/postings` | Posting API, public |
| Recruitee | `{company}.recruitee.com/api/offers/` | Careers site API |
| Personio | `{company}.jobs.personio.de/xml` | XML feed — popular with DE companies |
| Workable | public widget/job feed per account | Verify terms before use |
| Workday / Oracle / SAP SuccessFactors | — | **No documented public API → link-out only** (common in Gulf enterprises) |

Company discovery: search engines are **not** scraped; the list is curated manually + from public ATS directories /
user contributions, and validated by a reviewer.

### Tier 2 — Official / government employment APIs

| Country | Source | Access | Status |
|---------|--------|--------|--------|
| 🇫🇷 France | France Travail — API *Offres d'emploi v2* (francetravail.io) | Free, OAuth2 client credentials after registration | Planned |
| 🇩🇪 Germany | Bundesagentur für Arbeit — Jobsuche API | Public, client-id header | Planned |
| 🇪🇺 EU | EURES portal | Investigate data access / partnership; otherwise link-out | To verify |
| 🇵🇹 Portugal | IEFP / net-empregos | No known public API → link-out | To verify |
| 🇮🇹 Italy | No national public API known → Adzuna + ATS | — | — |
| 🇹🇳 Tunisia | ANETI (emploi.nat.tn), Tanitjobs, Keejob | No known public API → link-out; contact for partnership/RSS | To verify |
| 🇦🇪 🇸🇦 🇶🇦 🇰🇼 🇧🇭 🇴🇲 Gulf | National portals (e.g. Jadarat 🇸🇦), Bayt, GulfTalent | No known public API → link-out; coverage mainly via ATS (Tier 1) + Jooble | To verify |

### Tier 3 — Aggregator APIs with free access (registration, quotas, attribution)

| Source | Coverage relevant to us | Access | Notes |
|--------|-------------------------|--------|-------|
| Adzuna API | FR, DE, IT (+ others; **not** all target countries) | Free key, daily quota | Attribution required |
| Jooble REST API | Many countries incl. MENA | Free key on request | Verify terms for storing |
| Arbeitnow API | DE + remote (Europe) | Public, free | |
| Remotive API | Remote | Public, low request rate, attribution | Do not poll more than allowed |
| RemoteOK API | Remote | Public JSON, attribution + link back required | |
| Himalayas API | Remote | Public JSON | |
| We Work Remotely | Remote | RSS feeds | |
| Hacker News "Who is hiring?" | Global/remote, often early | Official HN API (Firebase) / Algolia HN API | Parse monthly thread comments; link to comment |

### Tier 4 — Link-out integrations (no data ingestion)
Pre-filled search URLs for LinkedIn, Indeed, Glassdoor, Bayt, GulfTalent, Naukrigulf, Tanitjobs, Keejob, Welcome to the Jungle, StepStone, InfoJobs, etc.
The user can also set alerts natively on those platforms; we only provide the shortcut.

## 3. Ingestion pipeline

```
beat schedule ─► for each approved source due (poll_interval, jitter)
   └─► connector.fetch(since=last_success, etag)          # token bucket per source, timeout 20 s, 3 retries w/ backoff
        └─► raw_job_postings upsert (source_id, external_id, payload_hash)  # unchanged hash → skip
             └─► normalise
                   - title → normalized_title + category (rule-based classifier: keyword/alias tables, e.g. "SRE", "Site Reliability", "Platform")
                   - seniority (junior/mid/senior/lead/principal from title & text)
                   - location → country_code (ISO 3166), city, remote_type, remote_regions  (offline geocoding with GeoNames dump, CC BY 4.0)
                   - salary parsing (min/max/currency/period) when present
                   - description: HTML sanitised (bleach/nh3), converted to Markdown, length-capped
                   - skills: taxonomy alias matching (+ optional LLM for unknowns)
                   - language detection (lingua-py)
             └─► dedup → job_postings upsert + job_posting_sources link
             └─► embed (batch) → match against saved searches & watchlists → notifications
   └─► ingestion_runs row (stats) ; on N consecutive failures → source auto-suspended + admin alert
expiry job: postings not seen for X days (per source) → status=closed
```

### Connector interface

```python
class JobConnector(Protocol):
    kind: str
    async def fetch(self, source: JobSource, since: datetime | None) -> AsyncIterator[RawPosting]: ...
    def to_canonical(self, raw: RawPosting) -> CanonicalPosting: ...
```
Each connector has recorded HTTP fixtures (VCR-style cassettes) for tests; no live calls in CI.

## 4. Deduplication

1. **Exact**: same `(source, external_id)` → update.
2. **Cross-source key**: `dedup_key = hash(normalized_company, normalized_title, country, city|remote)`; posted within 30 days.
3. **Fuzzy**: candidates by trigram similarity on title (> 0.6) + same company → cosine similarity of description embeddings > 0.9 → merge; keep the ATS (primary) URL as canonical apply link.

## 5. Filters & categories

Category classifier output: `devops`, `cloud`, `ai`, `mlops`, `platform`, `sre`, `backend`, `software` (multi-label).
Countries: TN, FR, IT, PT, DE, AE, SA, QA, KW, BH, OM + `remote` (with region constraints: "EMEA", "EU only", "worldwide").
Extra signals: visa/relocation keywords, languages required (French/German/Arabic/English), salary transparency.

## 6. Alerts

- `instant`: evaluated after each ingestion batch (saved-search filter as SQL + optional min match score).
- `daily`/`weekly` digest: one notification per period.
- Channels: in-app (always), Web Push (VAPID keys generated locally, free), e-mail (only if operator configures SMTP), optional **ntfy** (self-hosted push).
- Anti-noise: max N alerts/day per search, dedup across searches.

## 7. Scale estimate (zero-budget sizing)

~500 watched ATS boards + 6 APIs, polled every 2–6 h → ~5–20k active postings, ~2k new/day.
Postgres with these volumes: < 2 GB. Embedding 2k descriptions/day with multilingual-e5-small on CPU: a few minutes. Fits the single-server profile.
