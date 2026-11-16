# 12 — Source Review (Nov 2026)

This review covers the material the project owner supplied: four PDFs of recruitment tests they took, and five links.
It decides how each source may be used. **No question text from the PDFs is reproduced in this public repository.**

## 1. The owner's captured recruitment tests (4 PDFs)

`Recueil_tests_techniques.pdf` (56 pages) is a superset of the other three PDFs (`QCM_questions.pdf`,
`Test_Neoshore_questions.pdf` and `Test_Neoshore_DevOps_Docker_AWS_Terraform_Ansible.pdf`). Together they hold about
**280 MCQ items, 4 coding challenges and 1 oral interview report**.

| Section | Delivered via | Items (captured / total) | Areas covered |
|---------|---------------|--------------------------|---------------|
| Hydatis technical test | — | 55 / 59 | Logical reasoning (10), AI fundamentals (agents, tool idempotency, prompt injection, eval statistics, data leakage, skills/context), algorithms, software quality (canary, coverage, backups), cybersecurity (secrets in git history…), technical knowledge, teamwork, profile/salary |
| Neoshore — critical thinking, QA, Linux | TestGorilla | ~52 / 56 | Verbal analogies, true/false/undetermined reading comprehension, software testing/QA vocabulary, Linux processes/systems/networking |
| Neoshore — DevOps track | TestGorilla | ~95 + 16 practice | DevOps (20: networking, Linux troubleshooting, architecture patterns such as Saga), Docker (15), AWS (16), Terraform (16), Ansible (12) |
| xTECH Technology | Coderbyte | 20 MCQ + 4 challenges | Git, Node.js, SQL, JavaScript, CSS, React; challenges: array manipulation, Node `fs`/`child_process`, React Context API, an array/maths puzzle |
| Neoshore / Hilbert interview | Oral | 10 themes | AWS VPC design, Linux troubleshooting, VPN/firewall/CIDR/IAM, Terraform state & secrets, Ansible, backup/DR (RTO/RPO), 5xx incident after a deployment, SonarQube + ZAP in CI/CD, Kubernetes/ArgoCD/Helm, monitoring |

Observations:
- **None of the PDFs include answer keys.** A key must be proposed (coach plus user confirmation) before an item can be graded.
- Some questions are marked "not captured", so the sets are incomplete.
- The tests match the platform's first track closely: the DevOps/Cloud/AI taxonomy in doc 01 already covers almost every area.
  **Gaps to add to the taxonomy:** *verbal reasoning (analogies)*, *reading comprehension (true/false/undetermined)*,
  *software testing & QA*, *web front-end basics (HTML/CSS/JS/React)* and *Git*.

### Decision
| Use | Allowed? |
|-----|----------|
| Import into the owner's **private** bank (`personal_capture`, from git-ignored `private_content/`) and practise with the coach | ✅ |
| Commit the PDFs or their questions to this public repo, seed them, or show them to other users | ❌ TestGorilla, Coderbyte and employer content is copyrighted, and candidates usually accept confidentiality terms |
| Publish **company-topic profiles** (for example "Neoshore DevOps process: TestGorilla tests on DevOps/Docker/AWS/Terraform/Ansible, then an oral interview on AWS VPC, IaC and DR"), with the evidence "personal experience, 2026" | ✅ topic level only, never question text |
| Write or generate **original** questions for the same skills and formats (MCQ, scenario "which action should you take?", analogies, T/F/U) | ✅ labelled `ai_generated` or `user_created`; similarity to captures must be ≤ 0.85 |
| Use the PDFs to calibrate difficulty and question style | ✅ internal and aggregate only |

**Storage decision (approved): a separate private repository.** Captures live in a private repo,
`careerpilot-private-content`. This public repo holds only the code and the documentation. The app reads the captures
from `PRIVATE_CONTENT_DIR`, which points to a local clone, and imports them as private items owned by the operator account.
Each item follows the normal question schema, plus `provenance: personal_capture`, `visibility: private`, `company`,
`platform`, `taken_at` and `answer_key_status: unknown|proposed|confirmed`.

## 2. Suggested links

| Link | What it is | Licence / terms | Decision |
|------|-----------|-----------------|----------|
| [iam-veeramalla/DevOps-Interview-Guide](https://github.com/iam-veeramalla/DevOps-Interview-Guide) (`SquareOps/DevOps_Engineer.md`) | Fork of `litu54/DevOps-Interview-Guide`: 151 real interview write-ups from 85 companies, one Markdown file per experience | **No LICENSE file found**, so all rights are reserved by default | **Link only.** Index the company → role → file URL and extract `company_topics`. Copy no text. Ask the authors (via an issue) to add a CC BY licence. That would allow import. |
| [ai-job-search-dev/ai-job-search](https://github.com/ai-job-search-dev/ai-job-search) | Very popular job application framework built on Claude Code: posting evaluation, CV tailoring (LaTeX), cover letters, interview prep, pluggable "portal" skills | **MIT** | **Reuse ideas and patterns.** These feed the new *Application kit* feature (doc 01 §8). Not adopted: its need for a paid Claude subscription (we use Ollama), its WebSearch-based scraping, and its LinkedIn portal ("personal use only"). Its "postings are untrusted input" warning matches our guardrails. |
| estudyme.com/fr | English exam preparation (TOEIC/IELTS/TOEFL) | **Not verified.** The host is blocked by this session's network policy | Link-out from the English Academy until its terms are reviewed. Do not copy content. |
| toeflresources.com | TOEFL resources | **Not verified.** Host blocked | Link-out until reviewed |
| leamratech.com | Unknown | **Not verified.** Host blocked | Link-out until reviewed |

To review the three websites, the hosts `estudyme.com`, `www.toeflresources.com` and `leamratech.com` must be allowed in
this cloud environment's network settings. Alternatively, the owner can paste their terms of use.

## 3. Resulting changes in the design
- New provenance `personal_capture`, plus `visibility` / `owner_id` on questions (docs 03 and 11).
- `.gitignore` excludes `private_content/`, `*.private.yaml` and `*.private.json`.
- Tests Hub gets a private *Personal question bank* (doc 01 §4.8). Job Radar gets the *Application kit* (doc 01 §8.8).
- Taxonomy additions: verbal reasoning, reading comprehension, software testing/QA, Git, web front-end basics.
- Phase 1 seed priority: original questions on the areas these real tests emphasise: Linux troubleshooting, networking (DNS, ARP, ports, CIDR), Docker, AWS, Terraform state/modules, Ansible, CI/CD and canary releases, AI-agent safety (idempotency, prompt injection), evaluation statistics, logic/numerical reasoning.
