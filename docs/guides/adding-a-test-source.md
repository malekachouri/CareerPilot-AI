# Adding a test source

Most sources need **no code**: you register them, and the licence policy and the parsers do the rest.

## 1. Register the source

Either add an entry to `content/sources.yaml`, which `careerpilot seed` applies at startup:

```yaml
- slug: my-open-bank            # unique, lowercase
  name: My open question bank
  kind: github_repo             # github_repo | url | directory | file | website
  url: https://github.com/owner/repo          # or a sub-folder: .../tree/main/questions
  categories: [kubernetes]      # default topics when an item has none
  attribution: "Owner and contributors, CC BY 4.0"
  config:                       # optional
    include: ["questions/*.md"] # glob filters; without it only question-like paths + READMEs are read
    exclude: ["drafts/*"]
```

Or call the admin API: `POST /api/v1/admin/sources` with the same fields.

| kind | What is read | Licence |
|------|--------------|---------|
| `github_repo` | Repository metadata, README, files that look like question banks (`quiz`, `question`, `interview`, `qcm`, `test`… in the path), pinned to the current commit | Detected from GitHub (`license.spdx_id`) |
| `url` | One or more public HTTPS files (`config.urls`) | You set `license_spdx` |
| `directory` / `file` | Files under `CONTENT_DIRS` / `PRIVATE_CONTENT_DIR` only | You set `license_spdx` |
| `website` | Nothing is downloaded: reference and link only | — |

## 2. Inspect, then import

```bash
# Dry run: licence decision, README and detected question banks. Nothing is stored.
POST /api/v1/admin/sources/{id}/inspect
# Import in the background; items go to the review queue unless publish=true
POST /api/v1/admin/sources/{id}/import?publish=false
GET  /api/v1/jobs/{job_id}           # progress and the import report
GET  /api/v1/admin/review            # reviewers publish or reject
```

The licence policy (`modules/content/licensing.py`, docs/11) decides:
- **approved**: MIT, Apache-2.0, BSD, CC0, CC BY, CC BY-SA (share-alike flagged), and CC BY-NC unless `COMMERCIAL_MODE=true`.
- **link_only**: no licence, CC BY-ND / NC-ND, or a `website`. Only the reference and link are kept; no content is copied.
- **pending_review**: GPL-family licences applied to text, or anything unknown. A human decides.

## 3. Supported formats

| Format | Convention |
|--------|-----------|
| JSON / YAML | A list, or `{questions: [...]}`. Keys: `stem`/`question`, `options`/`choices` (strings or `{id, text}`), `answer` (letters, 0-based indexes or the option text), `explanation`, `distractor_explanations`, `category`/`categories`, `difficulty` (1–4 or beginner…expert), `type`, `context`, `id`. A file-level `company`, `category` or `language` applies to every item. |
| CSV | Header row; `question`, `option_a`…`option_f` or `options` (pipe-separated), `answer`, `explanation`, `category`, `difficulty` |
| Markdown | `#### Q1. Question` then a task list: `- [x] right` / `- [ ] wrong`. Code blocks become context; `Explanation:` lines become the explanation. |
| Text / PDF | `1. Question` or `Q1 — Question`, options `   A. text`, optional `Answer: B`. PDFs are imported only when the source licence allows it. |

Every import reports the rows it could not use and the categories it did not recognise. Add an alias to
`modules/taxonomy/seed.py` (e.g. `"k8s"` → Kubernetes) to map a bank's own topic names.

Imports are safe to re-run: unchanged items are skipped, changed ones get a new version (attempts keep the
version they used), and duplicates (same content, or ≥ 90% similar stem + context) are not stored twice.

## 4. When code *is* needed

- **A new place to read from** (e.g. a public quiz API): write a class with `describe()` and `files()` in
  `modules/content/adapters.py`, then register it in `ADAPTERS`.
- **A new file format**: write a `parse_x(text, ctx) -> ParseResult` in `modules/content/parsers.py` and add it to `PARSERS`.

## Private content

Your own notes of tests you took are imported only into your account, never into a public source:

```bash
docker compose run --rm -v /path/to/careerpilot-private-content/captures:/private:ro \
  api careerpilot import-captures --owner you@example.org --path /private
```

You can also use **Tests → Import my questions** in the web app, which accepts JSON, YAML, CSV, Markdown and PDF.
Personal captures are always private (enforced by a database constraint). Each captured test becomes a
private company collection, and you can set the answer keys you confirm from the results page.
