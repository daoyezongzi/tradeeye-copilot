# TradeEye Copilot

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-teal.svg)](https://fastapi.tiangolo.com/)

**TradeEye Copilot** is an A-share earnings-disclosure triage system for buy-side researchers (PMs / analysts). After earnings reports are disclosed, it outputs **structured financial facts**, **rule-driven anomaly findings**, **traceable evidence**, **attribution summaries**, and **market context** — not another long report summary to read.

> [简体中文](README.md) | English

---

## Table of Contents

- [What is this?](#what-is-this)
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

## What is this?

TradeEye Copilot is a lightweight collaborative research assistant purpose-built for buy-side institutions. During disclosure peaks, researchers do not lack earnings summaries; they lack **prioritization** and **reproducible anomaly detection**.

The project reframes the core task from “summarize the earnings report” to “**find the questions worth asking**”.

The system covers a configurable watchlist (default: **100 A-share companies**), scans disclosure calendar events every working day, runs deterministic financial checks, and delivers:

- **Daily briefing**: full coverage view sorted by anomaly severity
- **Company research card**: facts → anomalies → attribution → market context
- **Evidence traceability**: every finding carries `Evidence(source, field, period, value)` and can drill down to source values
- **Quarterly recap**: coverage pool, disclosed count, hit count, and rule distribution
- **Feishu push**: formal disclosure summary text to group chats; GitHub Actions can send serverless reminders from the Tushare disclosure calendar

## Why this design

| Problem | TradeEye Copilot's answer |
| --- | --- |
| LLMs hallucinate numbers in serious financial workflows | **LLM never touches arithmetic.** Financial numbers come from Tushare + pandas and are hard-checked by scripts; LLM is only used for wording comparison and textual attribution |
| Multi-agent dynamic negotiation is slow and token-heavy | **Single-pass analysis**: one scan produces both the daily briefing and scan results; Feishu/Web do not re-request Tushare |
| Chatbot prompts create friction for analysts | **Zero-prompt main path + optional Agent**: the Web workbench supports one-click scans and in-place refresh; the Agent floating layer answers questions about the current card and asks for analyst confirmation before refetch/rescan actions |
| Hard-check failures silently degrade quality | **Hard gate**: incomplete data or failed cross-validation blocks the research card instead of fabricating a “no anomaly” conclusion |

## Core design principles

1. **Deterministic pipeline first.** All core financial metrics are extracted and cross-checked by deterministic code; accuracy does not depend on model luck.
2. **Evidence over assertions.** Every anomaly finding is bound to `Evidence(source, field, period, value)`, and the UI can drill down into it.
3. **Single analysis pass.** Disclosure-day analysis is aggregated once; Web / Feishu / automation all reuse the same result.
4. **Resumable and cancellable scans.** Disclosure scans are job-based and persisted in SQLite; partial runs can resume via `skip_ts_codes`, and cancellation stops safely between companies/tables.
5. **Bank-aware rules.** Banks use a minimal hard-check branch instead of fabricated industry logic.
6. **Facts are the only interface.** `CompanyCard.facts` is the single fact interface for Agent interaction; agents never compute financial numbers (see [Agent fact contract](#agent-fact-contract)).

## Features

### Disclosure scanning
- Triggered by the **Tushare disclosure calendar**; RSS is only an optional fallback reminder source and never auto-fetches Tushare data or creates cards
- Pulls three periods (current / previous quarter / year-ago) across four tables (income statement / balance sheet / cash flow / financial indicators)
- **SQLite persistence**: snapshots, jobs, review labels, notification logs, editable stock pool
- **Resumable job store**: `POST /api/disclosure-day/jobs`, `resume_from_job_id`, `X-TradeEye-Owner` isolation, frontend 1-second polling
- **Pause / resume / stop**: scan controls support start, pause, resume, and stop; unavailable or incomplete data produces `BLOCKED` cards instead of silently missing cards

### Rule engine (deterministic arithmetic)
Six arithmetic rules with thresholds from `config.yaml` (`rules.thresholds`):

| Rule | Trigger |
| --- | --- |
| Receivable divergence | Receivable growth vs. revenue growth gap ≥ 30 pp |
| Inventory divergence | Inventory growth vs. revenue growth gap ≥ 30 pp |
| Cash-flow quality | Operating cash flow / net profit < 50% |
| Gross-margin movement | \|gross margin change\| ≥ 5 pp |
| Profit/revenue direction divergence | Net profit and revenue move in opposite directions |
| Non-recurring profit share | Non-recurring profit / net profit ≥ 30% |

Plus a **management tone weakened** finding (`management_tone_weakened`, YELLOW): the LLM compares the PDF management discussion section against the year-ago period.

### Research workbench (Web)
- **Daily briefing** — header, lead-in, severity distribution bar (red / yellow / OK / data issues)
- **Company research cards** — name-first display, code and report period as auxiliary identifiers; expandable with the highest-severity card expanded by default
- **Single-company analysis** — enter a stock code or company name and report period to generate one company card
- **Stock pool** — primary navigation page for editing the coverage pool; changes affect subsequent disclosure scans and reminder matching
- **Agent floating layer** — bottom-right robot entry, docked right by default, draggable/snap-back; answers questions about the current card and suggests refetch/rescan actions only after confirmation
- **Evidence drill-down popup** — per finding, showing the original `Evidence` payload
- **Quarterly recap** — coverage pool, disclosed count, hit count, and rule distribution; human-review metrics stay in backend evaluation APIs, not in the analyst main path
- **Diagnostics & developer tools** — collapsed fold with scan status, jobs, automation integration, and notification logs
- **Export** — JSON / CSV menus; deep links `#/day/{date}`, `#/company/{ts_code}/{period}`

### Feishu notifications
- Formal disclosure summary text (overview + all red/yellow anomalies + data issues; “no anomaly” companies counted only)
- **Long-text segmentation** (`split_feishu_text`, 3500 chars/segment with `[i/n]` headers)
- Idempotent de-duplication per date, send logs, preview, and manual resend APIs; the formal UI currently hides the manual preview/send button
- Interactive card **callback** endpoint with challenge / verification token checks, no public inbound webhook required
- GitHub Actions can send “earnings disclosed today” reminders from Tushare `disclosure_date`; without `TUSHARE_TOKEN`, it can fall back to `RSS_FEEDS`

### Automation
- `POST /api/automation/disclosure-day/cron`, protected by `X-Automation-Token` (`AUTOMATION_TRIGGER_TOKEN`)
- GitHub Actions workflow `disclosure-automation.yml`: cron `"30 10 * * 1-5"` (weekdays 10:30 UTC) + `workflow_dispatch` (`date` / `notify` inputs)

## Architecture

```text
Disclosure calendar -> Context assembly -> Hard checks -> Rule engine -> Report orchestration -> Web / Feishu
                                      \-> PDF extraction -> LLM tone comparison / attribution
```

- **Deterministic pipeline**: Tushare → pandas → SQLite → hard checks → rules. Numbers never pass through an LLM.
- **Narrative module**: extracts management-discussion sections from PDFs, uses an OpenAI-compatible LLM (temperature 0.0) to compare wording vs. year-ago text, and emits strict-JSON tone findings with PDF-section evidence.
- **API layer**: `create_app()` factory, used by `real_app` (production app with real services); demo data app has been removed.
- **Frontend**: dependency-free vanilla JS workbench (`web/`) mounted by FastAPI, no build step.

### Module layout

```text
copilot/
├── api/            # FastAPI: real_app.py (production entry), app.py (create_app factory)
├── checks/         # reconcile: cross-validation / hard checks
├── datasource/     # tushare_client, calendar, fundamentals
├── eval/           # backtest summary, real_backtest, manual review precision
├── llm/            # OpenAI-compatible client, failures degrade to None
├── narrative/      # PDF extraction + tone comparison
├── notify/         # Feishu rendering, long-text splitting
├── report/         # company research card / quarterly recap builders
├── rss/            # announcement trigger hint + polling service
├── rules/          # arithmetic rule engine: base, divergence, caliber, registry
├── service/        # analyzer, disclosure_scan, disclosure_jobs, review_store, notify_store
├── store/          # SQLite store
├── scheduler.py    # automation cron trigger handler
├── watchlist.py    # coverage YAML validation (code + name + industry)
└── models.py       # pydantic models: Context, Evidence, Finding, PeriodSnapshot, ...
```

## Quick start

### Prerequisites

- Python **≥ 3.11**
- [Tushare](https://tushare.pro/) token (financial data)
- *(Optional)* OpenAI-compatible LLM endpoint (Agent Q&A and tone findings)
- *(Optional)* Feishu custom-bot webhook (group push)

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

Secrets can stay in the repository-local `.env` file (ignored by `.gitignore`), or be split into a physically isolated directory outside the repository:

```text
C:\Users\Soyo\Documents\.secrets\
  .tushare              # TUSHARE_TOKEN
  .feishu               # FEISHU_WEBHOOK / FEISHU_VERIFICATION_TOKEN
  .deepseek             # LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
  tradeeye-copilot.env  # automation / PUBLIC_BASE_URL project-specific values
```

Load order:

```text
system environment variables
→ .tushare / .feishu / .deepseek / tradeeye-copilot.env under TRADEEYE_SECRETS_DIR
→ same files under C:\Users\Soyo\Documents\.secrets
→ repository-local .env
→ non-secret config.yaml
```

Example:

```env
# .env, or C:\Users\Soyo\Documents\.secrets\.tushare
TUSHARE_TOKEN=...

# .env, or C:\Users\Soyo\Documents\.secrets\.feishu
FEISHU_WEBHOOK=...
FEISHU_VERIFICATION_TOKEN=...

# .env, or C:\Users\Soyo\Documents\.secrets\.deepseek
LLM_API_KEY=...
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# .env, or C:\Users\Soyo\Documents\.secrets\tradeeye-copilot.env
AUTOMATION_TRIGGER_TOKEN=...
PUBLIC_BASE_URL=...
```

For temporary testing, you can set variables only in the current shell; those values have the highest priority and disappear when the shell closes.

`.env.example` only keeps the variable list and must not contain real values.

Non-secret settings live in `config.yaml`: coverage pool (100 companies), company names, industry routing, rule thresholds, LLM defaults, PDF cache, and evaluation window.

### Run

**Windows one-click start:**

```bat
start_real.bat
```

The script installs dependencies, opens `http://127.0.0.1:8000/`, and starts:

```bash
python -m uvicorn copilot.api.real_app:app --reload --host 127.0.0.1 --port 8000
```

After opening the workbench, click `依据` on any finding to inspect source evidence JSON.

### Verify

```bash
pytest -q
```

## Usage

### Analyst workflow (workbench)

1. Open `http://127.0.0.1:8000/` and enter the disclosure-day view.
2. Select a disclosure date and click **Start scan** (stop / cancel / resume are supported; partial jobs are persisted).
3. The **daily briefing** shows the severity distribution bar (red / yellow / OK / data issues).
4. Click a company row to expand its **research card** (facts → anomalies → attribution → market).
5. Click `依据` on a finding to open the **evidence drill-down popup** with exact source values.
6. For follow-up questions, click the bottom-right robot to open the **Agent floating layer**; the Agent answers using the current card and requires confirmation before refetch/rescan actions.
7. Click **Preview Feishu summary** to review text, then **Send** (disabled unless webhook is configured).
8. Check **notification logs** for delivery results.

After deployment, GitHub Actions cron (or any scheduler) can call the [automation endpoint](#automated-scheduling) for unattended runs.

### API quick tour

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/meta` | App metadata / capabilities |
| `GET` | `/api/daily/{date}` | Daily briefing for a disclosure date (`YYYYMMDD`) |
| `GET` | `/api/company/{ts_code}/{period}` | Company research card |
| `GET` | `/api/evidence/{ts_code}/{period}/{rule_id}` | Evidence for one finding |
| `GET` | `/api/quarterly` | Quarterly recap aggregate |
| `POST` | `/api/analyze/company` | Analyze one company |
| `POST` | `/api/analyze/disclosure-day` | Analyze a disclosure day (single-pass aggregation) |
| `POST` | `/api/scan/disclosure-day` | Scan a disclosure day |
| `POST` | `/api/disclosure-day/bundle` | Build analysis bundle |
| `POST` | `/api/disclosure-day/jobs` | Start a resumable scan job |
| `GET` | `/api/disclosure-day/jobs` | List jobs |
| `GET` | `/api/disclosure-day/jobs/{job_id}` | Get job status |
| `POST` | `/api/disclosure-day/jobs/{job_id}/cancel` | Cancel job (safe stop) |
| `DELETE` | `/api/disclosure-day/jobs?keep_recent=N` | Clean up old jobs |
| `GET` | `/api/reviews/labels.csv` | Internal evaluation: review labels as CSV |
| `GET` | `/api/reviews/metrics` | Internal evaluation: precision breakdowns |
| `POST` / `GET` | `/api/reviews/labels` | Internal evaluation: upsert / list review labels |
| `DELETE` | `/api/reviews/labels/{ts_code}/{period}/{rule_id}` | Internal evaluation: delete a label |
| `GET` | `/api/stock-pool` | List the editable stock pool |
| `POST` | `/api/stock-pool` | Add or update a stock-pool company |
| `DELETE` | `/api/stock-pool/{ts_code}` | Remove a stock-pool company |
| `POST` | `/api/rss/poll` | Poll RSS feeds (fallback trigger hint) |
| `POST` | `/api/rss/poll/notify` | Poll RSS and send a reminder (local developer panel) |
| `GET` | `/api/notify/logs?limit=20` | Notification send logs |
| `POST` | `/api/notify/feishu/callback` | Feishu interactive card callback |
| `POST` | `/api/notify/feishu/disclosure-day/{date}/preview` | Preview summary text |
| `POST` | `/api/notify/feishu/disclosure-day/{date}` | Send summary to webhook |
| `POST` | `/api/automation/disclosure-day` | Automation trigger (no token) |
| `POST` | `/api/automation/disclosure-day/cron` | Automation trigger (requires `X-Automation-Token`) |

Interactive FastAPI docs are available at `http://127.0.0.1:8000/docs` when running locally.

## Configuration reference

### Environment variables (secrets only)

| Variable | Required | Description |
| --- | --- | --- |
| `TUSHARE_TOKEN` | Yes | Tushare data access token |
| `LLM_API_KEY` | No | OpenAI-compatible external LLM API key (Agent Q&A and tone comparison) |
| `LLM_BASE_URL` | No | OpenAI-compatible endpoint; environment variable overrides `config.yaml` |
| `LLM_MODEL` | No | OpenAI-compatible model name; environment variable overrides `config.yaml` |
| `FEISHU_WEBHOOK` | No | Feishu custom-bot webhook URL (group push) |
| `AUTOMATION_TRIGGER_TOKEN` | No | Access token for cron automation endpoint |
| `FEISHU_VERIFICATION_TOKEN` | No | Verification token for Feishu card callback |
| `PUBLIC_BASE_URL` | No | Public base URL for card detail links (`notify.public_base_url`) |

`.env` is loaded automatically and environment variables take precedence; secrets are only checked for presence and are never printed.

### config.yaml sections

| Section | Purpose |
| --- | --- |
| `database` | SQLite path (default `data/tradeeye_copilot.sqlite`) |
| `tushare` | Timeout / retry settings |
| `llm` | Default `base_url`, `model`, and `timeout_seconds` for OpenAI-compatible endpoints |
| `narrative` | PDF cache directory and max section characters |
| `notify` | `feishu_enabled` flag |
| `eval` | `coverage_pool` (100 codes), `company_names`, `company_industries`, benchmark window and output path; the reminder Action reads this coverage pool |
| `rss` | Fallback RSS feed list and `max_entries`; with `TUSHARE_TOKEN`, Actions default to Tushare instead of RSS |
| `rules.thresholds` | Six arithmetic rule thresholds |

## Rule engine

Rules are **pure arithmetic functions** in `copilot/rules/` (`divergence.py`, `caliber.py`, `base.py`) and do not involve LLMs. Thresholds are configured in `config.yaml`; missing data yields `DATA_INCOMPLETE` / `NOT_EVALUATED` states and never fabricates “no anomaly”. Banks use a minimal hard-check branch (receivable / inventory / gross-margin rules exempted) without invented industry logic.

## Feishu notifications

- Rendered by `copilot/notify/feishu.py` (`render_formal_disclosure_text`)
- Long messages split into 3500-character segments with `[i/n]` headers
- Idempotent per date, send logs stored in SQLite, preview and manual resend APIs
- Interactive card callback endpoint verifies the verification token (challenge-style), no public inbound webhook required

## Automated scheduling

- GitHub Actions: `.github/workflows/disclosure-automation.yml`
  - cron `"30 10 * * 1-5"` (weekdays 10:30 UTC)
  - `workflow_dispatch` supports `date` and `notify` inputs
  - Requires Secrets `TRADEEYE_API_BASE_URL` and `AUTOMATION_TRIGGER_TOKEN`
- The workflow posts to `/api/automation/disclosure-day/cron` with `X-Automation-Token`; `copilot/scheduler.py` dispatches disclosure-day automation and optional Feishu notification.
- Serverless reminder workflow: `.github/workflows/rss-feishu-reminder.yml`
  - `workflow_dispatch` accepts `date=YYYYMMDD`; the `20250825` Action flow has been verified successfully
  - Prefer Secret `TUSHARE_TOKEN` and Tushare `disclosure_date`, filtered by the `config.yaml` coverage pool
  - Requires Secret `FEISHU_WEBHOOK` for delivery; optional `RSS_FEEDS` acts as fallback when no Tushare token is available

## LLM usage (external LLM API)

- `copilot/llm/client.py` — OpenAI-compatible client; failures return `None` and the pipeline degrades gracefully
- `copilot/narrative/extract.py` — extracts management discussion from PDFs (cached under `narrative.pdf_cache_dir`)
- `copilot/narrative/tone.py` — temperature **0.0**, strict JSON output, compares current vs. year-ago wording → `management_tone_weakened` finding with PDF-section evidence
- **Guardrails**: LLM never computes numbers; rules and hard checks contain no LLM; attribution is an additional finding and never replaces rule evidence

## Agent fact contract

The Agent is integrated into the analyst frontend as a floating Q&A layer rather than a primary navigation page. The contract (spec: [2026-08-01 Agent fact contract design](docs/superpowers/specs/2026-08-01-agent-fact-contract-design.md), [2026-08-02 Agent frontend design](docs/superpowers/specs/2026-08-02-agent-frontend-design.md)):

- **`CompanyCard.facts` is the single fact interface** — Agent must not derive numbers from rendered text
- `Fact` states: `VERIFIED` (requires value + evidence and period/value consistency) / `UNAVAILABLE` / `INVALID` / `NOT_APPLICABLE`
- Every fact carries `FactEvidence(evidence_id, source, field, period, value)` for traceability
- `RuleResultStatus`: `HIT` / `MISS` / `NOT_EVALUATED` / `BLOCKED` — insufficient data must not masquerade as `MISS`
- `CardStatus`: `OK` / `PARTIAL` / `BLOCKED` (partial blocking)
- Agent answers never override `facts` / `findings` / `rule_results`
- The Agent suggests only `refetch_company` / `rescan_disclosure_day`; the frontend executes existing analysis APIs only after confirmation, and the Agent itself writes no business data

## Evaluation & benchmark

- `eval/run_backtest.py` — deterministic benchmark scaffold, outputs `artifacts/benchmark.json`
- `copilot/eval/real_backtest.py` — multi-day scan aggregation (`summarize_scan_counts`, failures grouped by status/industry/message)
- `copilot/eval/manual_review.py` — `compute_precision_breakdown()`: overall / by rule / by severity / by industry; only TRUE/FALSE labels count, `UNREVIEWED` is excluded
- `eval/manual_review_template.csv` — manual review template (`ts_code, period, rule_id, label, notes, severity, industry`)
- Review labels and precision remain available through `/api/reviews/*` for internal evaluation; they are not shown in the analyst frontend main path

## Project structure

```text
.
├── copilot/          # Backend package (API, services, rules, store, notify)
├── web/              # Vanilla JS frontend workbench (index.html, app.js, components.js, styles.css)
├── eval/             # Benchmark / manual review tools
├── tests/            # pytest + Node frontend tests
├── config.yaml       # Non-secret configuration
├── start_real.bat    # One-click local startup (production app)
├── .github/workflows/disclosure-automation.yml
├── .github/workflows/rss-feishu-reminder.yml
└── docs/             # Development log, specs, and plans
```

## Testing

```bash
python -m pytest --basetemp=.pytest_tmp -q
npm test
node --check web/app.js && node --check web/agent-chat.js && node --check web/agent-panel.js
```

Current main-branch validation scale: 250 pytest and 18 Node frontend tests. The suite covers API routes, rule arithmetic, disclosure scan bundles, job store persistence/resume/pause, Feishu rendering and segmentation, Tushare Action disclosure reminders, RSS fallback, editable stock pool, review storage and internal evaluation metrics, configuration validation, coverage-pool validation, frontend productization contracts, and Agent panel/chat pure logic.

## Compliance boundary

TradeEye Copilot only presents facts, rule-triggered anomalies, source evidence, and market-reaction context. It does **not** output investment advice, target prices, or buy/sell ratings.

## Related projects

- [daoyezongzi/TradeEye](https://github.com/daoyezongzi/TradeEye) — data acquisition, perception pipeline, and Feishu push mechanism
- [daoyezongzi/PlatoAcademy](https://github.com/daoyezongzi/PlatoAcademy) — headless Skill Agent orchestration, RAG retrieval, and inference (interaction reference)

## Docs & references

- [Development log](docs/development-log.md) — chronological implementation notes
- [Specs & plans](docs/superpowers/) — design specs and implementation plans:
  - [Agent fact contract design](docs/superpowers/specs/2026-08-01-agent-fact-contract-design.md)
  - [Real-data disclosure event design](docs/superpowers/specs/2026-07-29-real-data-disclosure-event-design.md)
  - [Scan entry consolidation design](docs/superpowers/specs/2026-07-31-scan-entry-consolidation-design.md)
- [Submission checklist](docs/submission-checklist.md)
