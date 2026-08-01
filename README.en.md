# TradeEye Copilot

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-teal.svg)](https://fastapi.tiangolo.com/)

**TradeEye Copilot** is an A-share (China) earnings-disclosure anomaly copilot for buy-side research analysts. When a company's quarterly report lands, it outputs **structured financial facts**, **rule-driven anomaly findings**, **traceable evidence**, **attribution summaries**, and **market context** — not another summary to read.

> [简体中文](README.md) | English

---

## Table of Contents

- [What is TradeEye Copilot?](#what-is-tradeeye-copilot)
- [Why this design](#why-this-design)
- [Core design principles](#core-design-principles)
- [Features](#features)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Usage](#usage)
- [Configuration reference](#configuration-reference)
- [Rule engine](#rule-engine)
- [Feishu notifications](#feishu-notifications)
- [Automated scheduling](#automated-scheduling)
- [LLM usage (external LLM API)](#llm-usage-external-llm-api)
- [Agent fact contract](#agent-fact-contract)
- [Evaluation & benchmark](#evaluation--benchmark)
- [Project structure](#project-structure)
- [Testing](#testing)
- [Compliance boundary](#compliance-boundary)
- [Related projects](#related-projects)
- [Docs & references](#docs--references)

---

## What is TradeEye Copilot?

TradeEye Copilot is a lightweight collaborative research assistant purpose-built for buy-side institutions (PMs and analysts). During disclosure season, analysts do not lack earnings summaries — they lack **prioritization** and **reproducible anomaly detection**.

The project reframes the core problem from *"summarize the earnings report"* to *"find the questions worth asking."*

The system covers a configurable watchlist (default: **100 A-share companies**), scans disclosure calendar events every working day, runs deterministic financial checks, and delivers:

- A **daily briefing** ranking companies by anomaly severity
- **Company research cards** with four layers: facts → anomalies → attribution → market context
- **Evidence drill-down** — every finding carries `Evidence(source, field, period, value)`
- **Quarterly review** of coverage, rule hits, and human-review precision
- **Feishu push** of a formal disclosure summary to a group chat

## Why this design

| Problem | TradeEye Copilot's answer |
| --- | --- |
| LLM hallucinates numbers in serious financial contexts | **LLM never touches arithmetic.** Financial figures come from Tushare + pandas and pass script-level hard checks; the LLM only judges wording and writes attribution |
| Multi-agent negotiation is slow and token-hungry | **Single-pass analysis**: one scan produces both the daily summary and the scan result — Feishu/Web never re-request Tushare |
| Chatbot prompts block non-technical users | **Zero-prompt GUI**: a Web workbench with one-click scan, in-place refresh, and Feishu card push; an Agent question bar is reserved as a future interface |
| Hard-check failures silently degrade quality | **Hard gate**: incomplete data or failed cross-validation blocks the research card instead of emitting a fake "no issue" verdict |

## Core design principles

1. **Deterministic pipeline first.** All core financial metrics are extracted and cross-validated by deterministic code. Accuracy does not depend on model luck.
2. **Evidence over assertion.** Every anomaly finding is bound to `Evidence(source, field, period, value)` and exposed in the UI for drill-down.
3. **Single analysis pass.** Disclosure-day analysis is aggregated once; downstream consumers (Web, Feishu, automation) reuse the result.
4. **Resumable, cancellable scans.** Disclosure scans are job-based and persisted in SQLite — partial runs can be resumed with `skip_ts_codes`, and cancellation is a safe stop between companies.
5. **Banking-aware rules.** Banks take a minimal hard-check branch (no fabricated industry rules) — coverage without hallucinated domain logic.
6. **Facts are the only interface.** `CompanyCard.facts` is the single fact interface for Agent interaction; agents never compute financial numbers (see [Agent fact contract](#agent-fact-contract)).

## Features

### Disclosure scanning
- Triggered by the **Tushare disclosure calendar**; optional RSS feed acts as a trigger hint (`copilot/rss/announcements.py` filters earnings titles, marks `DATA_PENDING` when Tushare is not ready)
- Pulls three periods (current, previous quarter, year-ago) of four statements (income / balance sheet / cash flow / financial indicators) per company
- **SQLite persistence** for snapshots, jobs, review labels, and notification logs
- **Job store with resume**: `POST /api/disclosure-day/jobs`, `resume_from_job_id`, owner isolation via `X-TradeEye-Owner`, frontend 1-second polling

### Rule engine (deterministic arithmetic)
Six arithmetic rules with thresholds from `config.yaml` (`rules.thresholds`):

| Rule | Trigger |
| --- | --- |
| Receivable divergence | Receivable growth vs. revenue growth gap ≥ 30 pp |
| Inventory divergence | Inventory growth vs. revenue growth gap ≥ 30 pp |
| Cash-flow quality | Operating cash flow / net profit < 50% |
| Gross-margin change | |Δ gross margin| ≥ 5 pp |
| Profit/revenue direction divergence | Net profit and revenue trend in opposite directions |
| Non-recurring profit share | Non-recurring profit ≥ 30% of net profit |

Plus a **management-tone finding** (`management_tone_weakened`, YELLOW) produced by the LLM comparing year-on-year wording of the PDF management discussion.

### Research workbench (Web)
- **Daily briefing** — header, lead-in, severity distribution bar (red / yellow / OK / data issues)
- **Company research cards** — expandable; highest-severity card expanded by default
- **Evidence drill-down popup** — per finding, showing the raw `Evidence` payload
- **Review queue** — label findings TRUE/FALSE, persisted in the backend (`ts_code/period/rule_id` primary key)
- **Quarterly review** — coverage pool, hits, rule distribution, human-review precision breakdowns (overall / by rule / by severity / by industry)
- **Diagnostics & developer tools** — collapsed fold with scan status, jobs, and meta endpoints
- **Export** — JSON / CSV menus; deep links `#/day/{date}`, `#/company/{ts_code}/{period}`

### Feishu notifications
- Formal disclosure summary text (overview + all red/yellow anomalies + data issues; "no anomaly" companies counted only)
- **Long-text segmentation** (`split_feishu_text`, 3500 chars/segment with `[i/n]` headers)
- Idempotent de-duplication per date, **send logs**, **preview** and **manual resend** endpoints
- Interactive card **callback** endpoint with challenge/verification-token checks (no public inbound webhook required)

### Automation
- `POST /api/automation/disclosure-day/cron` guarded by `X-Automation-Token` (`AUTOMATION_TRIGGER_TOKEN`)
- GitHub Actions workflow `disclosure-automation.yml`: cron `"30 10 * * 1-5"` (10:30 UTC on weekdays) + `workflow_dispatch` with date/notify inputs

## Architecture

```text
Disclosure calendar -> Context assembly -> Hard validation -> Rule engine -> Report orchestration -> Web / Feishu
                                          \-> PDF extraction -> LLM tone comparison / attribution
```

- **Deterministic pipeline**: Tushare → pandas → SQLite → hard check → rules. Numbers never pass through an LLM.
- **Narrative module**: extracts the management-discussion section from PDFs, then uses an OpenAI-compatible LLM (temperature 0.0) to compare wording vs. the prior period and emit a strict-JSON tone finding bound to the PDF section as evidence.
- **API layer**: one `create_app()` factory shared by `real_app` (production, real services) — demo data app was removed.
- **Frontend**: dependency-free vanilla JS workbench (`web/`) served by FastAPI static mounts, no build step.

### Module layout

```text
copilot/
├── api/            # FastAPI app: real_app.py (production), app.py (create_app factory)
├── checks/         # reconcile: cross-validation / hard checks
├── datasource/     # tushare_client, calendar, fundamentals
├── eval/           # backtest summary, real_backtest, manual review precision
├── llm/            # OpenAI-compatible client, failure degrades to None
├── narrative/      # PDF extraction + tone comparison
├── notify/         # Feishu rendering, long-text splitting
├── report/         # company card / quarterly review builders
├── rss/            # announcements trigger hint + polling service
├── rules/          # arithmetic rule engine: base, divergence, caliber, registry
├── service/        # analyzer, disclosure_scan (single-pass bundle), disclosure_jobs, review_store, notify_store
├── store/          # SQLite store
├── scheduler.py    # automation cron trigger handler
├── watchlist.py    # coverage pool YAML validation (code + name + industry)
└── models.py       # pydantic models: Context, Evidence, Finding, PeriodSnapshot, ...
```

## Quick start

### Prerequisites

- Python **≥ 3.11**
- A [Tushare](https://tushare.pro/) token (financial data)
- *(Optional)* An OpenAI-compatible LLM endpoint (narrative tone findings)
- *(Optional)* A Feishu custom-bot webhook (group push)

### Install

```bash
git clone git@github.com:daoyezongzi/tradeeye-copilot.git
cd tradeeye-copilot
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

### Configure

```bash
cp .env.example .env
```

Then fill in the secrets (see [Configuration reference](#configuration-reference)):

```bash
TUSHARE_TOKEN=...
ASCEND_API_KEY=...          # optional
FEISHU_WEBHOOK=...          # optional
AUTOMATION_TRIGGER_TOKEN=...  # optional, required for cron endpoint
FEISHU_VERIFICATION_TOKEN=... # optional, for card callback
PUBLIC_BASE_URL=...         # optional, public URL of the deployed app
```

Non-secret settings live in `config.yaml`: coverage pool (100 companies), company names, industry routing, rule thresholds, LLM endpoint, PDF cache, eval window.

### Run

**Windows (one click):**

```bat
start_real.bat
```

It installs deps, opens `http://127.0.0.1:8000/`, and starts:

```bash
python -m uvicorn copilot.api.real_app:app --reload --host 127.0.0.1 --port 8000
```

Open the dashboard and click `依据` (Evidence) on any finding to inspect the raw evidence JSON.

### Verify

```bash
pytest -q
```

## Usage

### Analyst workflow (dashboard)

1. Open `http://127.0.0.1:8000/` — the workbench shows the disclosure-day view.
2. Pick a disclosure date and click **Start scan** (you can stop / cancel / resume — partial jobs are persisted).
3. The **daily briefing** shows a severity distribution bar (red / yellow / OK / data issues).
4. Click a company row to open its **research card** (facts → anomalies → attribution → market context).
5. Click `依据` (Evidence) on any finding for the **evidence drill-down popup** with the exact source values.
6. Label findings as TRUE / FALSE in the review queue — labels are stored in the backend and feed precision metrics.
7. Click **Preview Feishu summary** to review the message, then **Send** (button disabled until a webhook is configured).
8. Check **notification logs** for delivery results.

After deployment, the GitHub Actions cron (or any scheduler) calls the [automation endpoint](#automated-scheduling) so the flow runs unattended.

### API quick tour

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/meta` | App meta / capabilities |
| `GET` | `/api/daily/{date}` | Daily briefing for a date (`YYYYMMDD`) |
| `GET` | `/api/company/{ts_code}/{period}` | Company research card |
| `GET` | `/api/evidence/{ts_code}/{period}/{rule_id}` | Evidence payload for one finding |
| `GET` | `/api/quarterly` | Quarterly review aggregates |
| `POST` | `/api/analyze/company` | Analyze one company |
| `POST` | `/api/analyze/disclosure-day` | Analyze a disclosure day (single pass) |
| `POST` | `/api/scan/disclosure-day` | Scan a disclosure day |
| `POST` | `/api/disclosure-day/bundle` | Build analysis bundle |
| `POST` | `/api/disclosure-day/jobs` | Start a resumable scan job |
| `GET` | `/api/disclosure-day/jobs` | List jobs |
| `GET` | `/api/disclosure-day/jobs/{job_id}` | Job status |
| `POST` | `/api/disclosure-day/jobs/{job_id}/cancel` | Cancel a job (safe stop) |
| `DELETE` | `/api/disclosure-day/jobs?keep_recent=N` | Clean up old jobs |
| `GET` | `/api/reviews/labels.csv` | Review labels as CSV |
| `GET` | `/api/reviews/metrics` | Precision breakdowns |
| `POST` / `GET` | `/api/reviews/labels` | Upsert / list review labels |
| `DELETE` | `/api/reviews/labels/{ts_code}/{period}/{rule_id}` | Delete a label |
| `POST` | `/api/rss/poll` | Poll RSS feeds (trigger hint) |
| `GET` | `/api/notify/logs?limit=20` | Notification send logs |
| `POST` | `/api/notify/feishu/callback` | Feishu interactive card callback |
| `POST` | `/api/notify/feishu/disclosure-day/{date}/preview` | Preview the summary text |
| `POST` | `/api/notify/feishu/disclosure-day/{date}` | Send the summary to the webhook |
| `POST` | `/api/automation/disclosure-day` | Automation trigger (no token) |
| `POST` | `/api/automation/disclosure-day/cron` | Automation trigger (requires `X-Automation-Token`) |

The FastAPI interactive docs are available at `http://127.0.0.1:8000/docs` when running with `--reload` (or via the OpenAPI schema).

## Configuration reference

### Environment variables (secrets only)

| Variable | Required | Description |
| --- | --- | --- |
| `TUSHARE_TOKEN` | Yes | Tushare data access token |
| `ASCEND_API_KEY` | No | External LLM API key (narrative tone) |
| `FEISHU_WEBHOOK` | No | Feishu custom-bot webhook URL (group push) |
| `AUTOMATION_TRIGGER_TOKEN` | No | Token required by the cron automation endpoint |
| `FEISHU_VERIFICATION_TOKEN` | No | Verification token for Feishu card callback |
| `PUBLIC_BASE_URL` | No | Public base URL used in card detail links (`notify.public_base_url`) |

`.env` is auto-loaded and environment variables take precedence; secrets are validated for presence only, never printed.

### config.yaml sections

| Section | Purpose |
| --- | --- |
| `database` | SQLite path (default `data/tradeeye_copilot.sqlite`) |
| `tushare` | Timeout / retry settings |
| `llm` | `base_url`, `model`, `timeout_seconds` for the OpenAI-compatible endpoint |
| `narrative` | PDF cache dir, max section chars |
| `notify` | `feishu_enabled` flag |
| `eval` | `coverage_pool` (100 codes), `company_names`, `company_industries`, benchmark window & output path |
| `rss` | Feed list, `max_entries` |
| `rules.thresholds` | Thresholds for the six arithmetic rules |

## Rule engine

Rules are **pure arithmetic functions** in `copilot/rules/` (`divergence.py`, `caliber.py`, `base.py`) — no LLM involved. Thresholds are configured in `config.yaml`; missing data yields `DATA_INCOMPLETE` / `NOT_EVALUATED` states instead of fake "no issue" verdicts. Banks route through a minimal hard-check branch (receivable / inventory / gross-margin rules exempted) — no fabricated industry logic.

## Feishu notifications

- Rendered by `copilot/notify/feishu.py` (`render_formal_disclosure_text`)
- Long messages are split into 3500-char segments with `[i/n]` headers
- One message per date (idempotent), send logs stored in SQLite, manual resend supported
- Interactive card callback endpoint verifies the verification token (challenge-style); no public inbound webhook is needed

## Automated scheduling

- GitHub Actions: `.github/workflows/disclosure-automation.yml`
  - cron `"30 10 * * 1-5"` (10:30 UTC, weekdays)
  - `workflow_dispatch` with `date` and `notify` inputs
  - Requires secrets `TRADEEYE_API_BASE_URL` and `AUTOMATION_TRIGGER_TOKEN`
- The workflow POSTs to `/api/automation/disclosure-day/cron` with `X-Automation-Token`; `copilot/scheduler.py` dispatches the disclosure-day automation with optional Feishu notify.

## LLM usage (external LLM API)

- `copilot/llm/client.py` — OpenAI-compatible client; on failure returns `None` and the pipeline degrades gracefully
- `copilot/narrative/extract.py` — extracts the management-discussion section from PDFs (cached in `narrative.pdf_cache_dir`)
- `copilot/narrative/tone.py` — temperature **0.0**, strict-JSON output, compares current vs. year-ago wording → `management_tone_weakened` finding with the PDF section as evidence
- **Guardrails**: the LLM never computes numbers; rules and hard checks are LLM-free; attribution is an *additional* finding, never a replacement for rule evidence.

## Agent fact contract

The system reserves a headless-Agent question bar (Agent interface endpoints are defined; the Web UI reuses the current workbench). The contract (spec: [2026-08-01 agent fact contract design](docs/superpowers/specs/2026-08-01-agent-fact-contract-design.md)):

- **`CompanyCard.facts` is the single fact interface** — agents must not derive numbers from rendered text
- `Fact` states: `VERIFIED` (requires value + evidence, period/value consistency checked) / `UNAVAILABLE` / `INVALID` / `NOT_APPLICABLE`
- Every fact carries `FactEvidence(evidence_id, source, field, period, value)` for traceability
- `RuleResultStatus`: `HIT` / `MISS` / `NOT_EVALUATED` / `BLOCKED` — insufficient data must not masquerade as `MISS`
- `CardStatus`: `OK` / `PARTIAL` / `BLOCKED` (partial blocking)
- Agent answers never override `facts` / `findings` / `rule_results`

## Evaluation & benchmark

- `eval/run_backtest.py` — deterministic benchmark scaffold; writes `artifacts/benchmark.json` (not committed)
- `copilot/eval/real_backtest.py` — multi-day scan aggregation (`summarize_scan_counts`, failure grouping by status/industry/message)
- `copilot/eval/manual_review.py` — `compute_precision_breakdown()`: overall / by rule / by severity / by industry; only TRUE/FALSE labels count, `UNREVIEWED` excluded
- `eval/manual_review_template.csv` — template for human review (`ts_code, period, rule_id, label, notes, severity, industry`)
- Review labels feed back through `/api/reviews/*`

## Project structure

```text
.
├── copilot/          # Backend package (API, services, rules, store, notify)
├── web/              # Vanilla JS frontend workbench (index.html, app.js, components.js, styles.css)
├── eval/             # Benchmark / manual review tooling
├── tests/            # pytest suite (180+ tests)
├── config.yaml       # Non-secret configuration
├── start_real.bat    # One-click local startup (production app)
├── .github/workflows/disclosure-automation.yml
└── docs/             # Development log, specs, and plans
```

## Testing

```bash
pytest -q
```

The suite covers API routes, rule arithmetic, disclosure scan bundles, job store persistence/resume, Feishu rendering & segmentation, review store & metrics, config validation, watchlist validation, and frontend contracts.

## Compliance boundary

TradeEye Copilot only presents facts, rule-triggered anomalies, source evidence, and market-reaction context. It does **not** output investment advice, target prices, or buy/sell/hold recommendations.

## Related projects

- [daoyezongzi/TradeEye](https://github.com/daoyezongzi/TradeEye) — data acquisition, perception pipeline, and Feishu push mechanism
- [daoyezongzi/PlatoAcademy](https://github.com/daoyezongzi/PlatoAcademy) — headless Skill-Agent orchestration, RAG retrieval, and inference (interaction reference)

## Docs & references

- [Development log](docs/development-log.md) — chronological implementation notes
- [Specs & plans](docs/superpowers/) — design specs and implementation plans:
  - [Agent fact contract design](docs/superpowers/specs/2026-08-01-agent-fact-contract-design.md)
  - [Real-data disclosure event design](docs/superpowers/specs/2026-07-29-real-data-disclosure-event-design.md)
  - [Scan entry consolidation design](docs/superpowers/specs/2026-07-31-scan-entry-consolidation-design.md)
- [Submission checklist](docs/submission-checklist.md)
