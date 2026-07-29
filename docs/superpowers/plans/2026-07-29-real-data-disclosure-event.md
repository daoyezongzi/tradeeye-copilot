# Real Data Disclosure Event Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the demo-only flow with real Tushare-driven single-company analysis, disclosure-day aggregation, RSS trigger hints, Feishu static push endpoints, and frontend API adapters.

**Architecture:** All triggers flow through one `AnalyzerService`: manual single-company analysis, Tushare `disclosure_date` batches, and RSS-triggered probe events. Tushare remains the only source for structured financial numbers; RSS only discovers candidate announcements. The frontend stays simple and talks to stable JSON API wrappers so the UI can be replaced later without changing backend contracts.

**Tech Stack:** Python 3.11+, FastAPI, pydantic, pandas, tushare, httpx, python-dotenv, SQLite store from existing core, vanilla HTML/CSS/JS.

---

## File Structure

Existing files to modify:

- Modify: `pyproject.toml` — dependency already has `python-dotenv`; keep package discovery unchanged.
- Modify: `config.yaml` — add RSS feed config under `rss`.
- Modify: `.env.example` — keep secret names documented; do not add real values.
- Modify: `copilot/config.py` — load `.env`, add `RssSettings`.
- Modify: `copilot/datasource/calendar.py` — keep existing disclosure event normalization; tests may add coverage for period fallback.
- Modify: `copilot/store/sqlite.py` — no schema change required; service uses existing snapshots/findings.
- Modify: `copilot/api/app.py` — add optional analysis/RSS/notify service protocols and routes.
- Modify: `copilot/api/dev_app.py` — keep demo compatible with new protocol methods.
- Modify: `copilot/report/builder.py` — no structural changes expected.
- Modify: `web/index.html` — add minimal input controls.
- Modify: `web/app.js` — add `api.*` wrapper and render paths.
- Modify: `web/styles.css` — minimal status block styling only.

New backend files:

- Create: `copilot/datasource/tushare_client.py` — Tushare `pro_api` factory; no token printing.
- Create: `copilot/service/__init__.py` — service package marker.
- Create: `copilot/service/report_cache.py` — in-memory company/daily cache.
- Create: `copilot/service/analyzer.py` — real analysis service and result models.
- Create: `copilot/rss/__init__.py` — RSS package marker.
- Create: `copilot/rss/announcements.py` — RSS XML parsing, title classification, period inference.
- Create: `copilot/rss/service.py` — poll configured feeds, dedupe, probe analyzer once.
- Create: `copilot/api/real_app.py` — real app wiring using `.env` and settings.
- Create: `start_real.bat` — one-click real app startup.

New tests:

- Create: `tests/test_tushare_client.py`
- Create: `tests/test_config_rss.py`
- Create: `tests/test_report_cache.py`
- Create: `tests/test_analyzer_service.py`
- Create: `tests/test_analyzer_disclosure_day.py`
- Create: `tests/test_api_analysis_routes.py`
- Create: `tests/test_rss_announcements.py`
- Create: `tests/test_rss_service.py`
- Create: `tests/test_api_rss_routes.py`
- Create: `tests/test_api_notify_routes.py`
- Create: `tests/test_real_app_startup.py`
- Create: `tests/test_frontend_contracts.py`

---

### Task 1: RSS Config and `.env` Loading

**Files:**
- Modify: `copilot/config.py`
- Modify: `config.yaml`
- Modify: `.env.example`
- Create: `tests/test_config_rss.py`

- [ ] **Step 1: Write failing config tests**

Create `tests/test_config_rss.py`:

```python
from pathlib import Path

from copilot.config import load_settings


def test_load_settings_reads_dotenv_without_printing_values(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
llm:
  base_url: https://maas.example.com/v1
  model: ascend-compatible-model
rss:
  feeds:
    - https://example.com/rss.xml
  max_entries: 25
""".strip(),
        encoding="utf-8",
    )
    env_path.write_text(
        "TUSHARE_TOKEN=token-from-dotenv\nFEISHU_WEBHOOK=https://open.feishu.cn/test\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    monkeypatch.delenv("FEISHU_WEBHOOK", raising=False)

    settings = load_settings(config_path, env_path=env_path)

    assert settings.tushare.token == "token-from-dotenv"
    assert settings.notify.feishu_webhook == "https://open.feishu.cn/test"
    assert settings.rss.feeds == ["https://example.com/rss.xml"]
    assert settings.rss.max_entries == 25


def test_load_settings_environment_overrides_dotenv(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
llm:
  base_url: https://maas.example.com/v1
  model: ascend-compatible-model
""".strip(),
        encoding="utf-8",
    )
    env_path.write_text("TUSHARE_TOKEN=token-from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("TUSHARE_TOKEN", "token-from-env")

    settings = load_settings(config_path, env_path=env_path)

    assert settings.tushare.token == "token-from-env"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_config_rss.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `load_settings()` has no `env_path` argument and `settings.rss` does not exist.

- [ ] **Step 3: Implement settings changes**

Replace `copilot/config.py` with:

```python
from pathlib import Path
import os

from dotenv import load_dotenv
import yaml
from pydantic import BaseModel, Field


class DatabaseSettings(BaseModel):
    path: Path


class TushareSettings(BaseModel):
    timeout_seconds: int = 30
    max_retries: int = 3
    token: str | None = None


class LLMSettings(BaseModel):
    base_url: str = "https://maas.example.com/v1"
    model: str = "ascend-compatible-model"
    timeout_seconds: int = 60
    api_key: str | None = None


class NarrativeSettings(BaseModel):
    pdf_cache_dir: Path = Path("data/pdf_cache")
    max_section_chars: int = 12000


class NotifySettings(BaseModel):
    feishu_enabled: bool = False
    feishu_webhook: str | None = None


class EvalSettings(BaseModel):
    coverage_pool: list[str] = Field(default_factory=list)
    start_date: str = "20250801"
    end_date: str = "20250831"
    benchmark_output: Path = Path("artifacts/benchmark.json")


class RssSettings(BaseModel):
    feeds: list[str] = Field(default_factory=list)
    max_entries: int = 50


class RuleThresholds(BaseModel):
    receivable_revenue_gap_pct: float = 30.0
    inventory_revenue_gap_pct: float = 30.0
    ocf_to_net_profit_pct: float = 50.0
    gross_margin_change_pct: float = 5.0
    non_recurring_profit_share_pct: float = 30.0


class RuleSettings(BaseModel):
    thresholds: RuleThresholds = Field(default_factory=RuleThresholds)


class Settings(BaseModel):
    database: DatabaseSettings
    tushare: TushareSettings = Field(default_factory=TushareSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    narrative: NarrativeSettings = Field(default_factory=NarrativeSettings)
    notify: NotifySettings = Field(default_factory=NotifySettings)
    eval: EvalSettings = Field(default_factory=EvalSettings)
    rss: RssSettings = Field(default_factory=RssSettings)
    rules: RuleSettings = Field(default_factory=RuleSettings)


def load_settings(path: str | Path = "config.yaml", env_path: str | Path = ".env") -> Settings:
    load_dotenv(env_path, override=False)
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    data.setdefault("tushare", {})["token"] = os.getenv("TUSHARE_TOKEN")
    data.setdefault("llm", {})["api_key"] = os.getenv("ASCEND_API_KEY")
    data.setdefault("notify", {})["feishu_webhook"] = os.getenv("FEISHU_WEBHOOK")
    return Settings.model_validate(data)
```

- [ ] **Step 4: Extend non-secret config**

Modify `config.yaml` by adding:

```yaml
rss:
  feeds: []
  max_entries: 50
```

Keep all existing sections unchanged.

- [ ] **Step 5: Keep `.env.example` secret-only**

Ensure `.env.example` remains exactly:

```dotenv
TUSHARE_TOKEN=
ASCEND_API_KEY=
FEISHU_WEBHOOK=
```

- [ ] **Step 6: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_config_rss.py tests/test_config.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add copilot/config.py config.yaml .env.example tests/test_config_rss.py
git commit -m "feat: load real data runtime settings"
```

---

### Task 2: Tushare Client Factory

**Files:**
- Create: `copilot/datasource/tushare_client.py`
- Create: `tests/test_tushare_client.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tushare_client.py`:

```python
import pytest

from copilot.datasource.tushare_client import TushareTokenMissing, create_tushare_pro


class FakeTushareModule:
    def __init__(self):
        self.received_token = None

    def pro_api(self, token):
        self.received_token = token
        return {"client": "ok"}


def test_create_tushare_pro_requires_token():
    with pytest.raises(TushareTokenMissing) as exc:
        create_tushare_pro(None, tushare_module=FakeTushareModule())

    assert "TUSHARE_TOKEN" in str(exc.value)
    assert "None" not in str(exc.value)


def test_create_tushare_pro_passes_token_without_logging_it(capsys):
    fake = FakeTushareModule()

    client = create_tushare_pro("secret-token", tushare_module=fake)

    assert client == {"client": "ok"}
    assert fake.received_token == "secret-token"
    captured = capsys.readouterr()
    assert "secret-token" not in captured.out
    assert "secret-token" not in captured.err
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_tushare_client.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `copilot.datasource.tushare_client` does not exist.

- [ ] **Step 3: Implement Tushare factory**

Create `copilot/datasource/tushare_client.py`:

```python
class TushareTokenMissing(RuntimeError):
    pass


def create_tushare_pro(token: str | None, tushare_module=None):
    if not token:
        raise TushareTokenMissing("TUSHARE_TOKEN is required to create a Tushare client")
    if tushare_module is None:
        import tushare as tushare_module
    return tushare_module.pro_api(token)
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_tushare_client.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/datasource/tushare_client.py tests/test_tushare_client.py
git commit -m "feat: create tushare client from environment token"
```

---

### Task 3: Report Cache

**Files:**
- Create: `copilot/service/__init__.py`
- Create: `copilot/service/report_cache.py`
- Create: `tests/test_report_cache.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_report_cache.py`:

```python
from copilot.models import Context
from copilot.report.builder import build_company_card, build_daily_summary
from copilot.service.report_cache import ReportCache


def test_report_cache_stores_company_cards(make_snapshot):
    cache = ReportCache()
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])

    cache.put_company(card)

    assert cache.get_company("000001.SZ", "20250630") == card
    assert cache.get_company("000001.SZ", "20240630") is None


def test_report_cache_stores_daily_summaries(make_snapshot):
    cache = ReportCache()
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    summary = build_daily_summary("20250821", 42, [card])

    cache.put_daily(summary)

    assert cache.get_daily("20250821") == summary
    assert cache.get_daily("20250822") is None
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_report_cache.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `copilot.service.report_cache` does not exist.

- [ ] **Step 3: Implement cache**

Create `copilot/service/__init__.py`:

```python
"""Application services."""
```

Create `copilot/service/report_cache.py`:

```python
from copilot.report.builder import CompanyCard, DailySummary


class ReportCache:
    def __init__(self):
        self._companies: dict[tuple[str, str], CompanyCard] = {}
        self._daily: dict[str, DailySummary] = {}

    def put_company(self, card: CompanyCard) -> None:
        self._companies[(card.ts_code, card.period)] = card

    def get_company(self, ts_code: str, period: str) -> CompanyCard | None:
        return self._companies.get((ts_code, period))

    def put_daily(self, summary: DailySummary) -> None:
        self._daily[summary.date] = summary

    def get_daily(self, date: str) -> DailySummary | None:
        return self._daily.get(date)
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_report_cache.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/service/__init__.py copilot/service/report_cache.py tests/test_report_cache.py
git commit -m "feat: cache latest analysis reports"
```

---

### Task 4: Analyzer Service Single Company

**Files:**
- Create: `copilot/service/analyzer.py`
- Create: `tests/test_analyzer_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_analyzer_service.py`:

```python
from copilot.checks.reconcile import CheckStatus
from copilot.context import prior_quarter_period, prior_year_period
from copilot.models import PeriodSnapshot
from copilot.service.analyzer import AnalyzerService, CompanyAnalysisStatus


class FakeFundamentals:
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.calls = []

    def fetch_snapshot(self, ts_code, period):
        self.calls.append((ts_code, period))
        snapshot = self.snapshots.get((ts_code, period))
        if snapshot is None:
            return PeriodSnapshot(ts_code=ts_code, period=period)
        return snapshot


class FakeStore:
    def __init__(self):
        self.snapshots = {}
        self.findings = {}

    def upsert_snapshot(self, snapshot):
        self.snapshots[(snapshot.ts_code, snapshot.period)] = snapshot

    def get_snapshot(self, ts_code, period):
        return self.snapshots.get((ts_code, period))

    def replace_findings(self, ts_code, period, findings):
        self.findings[(ts_code, period)] = findings


def snapshot(ts_code="000001.SZ", period="20250630", revenue=100.0, net_profit=10.0, gross_margin_pct=30.0, operating_cash_flow=8.0, **overrides):
    data = {
        "ts_code": ts_code,
        "period": period,
        "ann_date": "20250821",
        "revenue": revenue,
        "net_profit": net_profit,
        "deducted_net_profit": 9.0,
        "gross_margin_pct": gross_margin_pct,
        "operating_cash_flow": operating_cash_flow,
        "accounts_receivable": 20.0,
        "inventory": 15.0,
    }
    data.update(overrides)
    return PeriodSnapshot(**data)


def test_analyze_company_fetches_three_periods_and_returns_card():
    current = snapshot(period="20250630", revenue=112.0, accounts_receivable=147.0)
    prior_quarter = snapshot(period="20250331")
    prior_year = snapshot(period="20240630", revenue=100.0, accounts_receivable=100.0)
    fundamentals = FakeFundamentals({
        ("000001.SZ", "20250630"): current,
        ("000001.SZ", "20250331"): prior_quarter,
        ("000001.SZ", "20240630"): prior_year,
    })
    store = FakeStore()
    service = AnalyzerService(fundamentals=fundamentals, store=store)

    result = service.analyze_company("000001.SZ", "20250630")

    assert result.status == CompanyAnalysisStatus.OK
    assert result.card.ts_code == "000001.SZ"
    assert result.card.period == "20250630"
    assert fundamentals.calls == [
        ("000001.SZ", "20250630"),
        ("000001.SZ", "20250331"),
        ("000001.SZ", "20240630"),
    ]
    assert store.findings[("000001.SZ", "20250630")][0].rule_id == "receivable_revenue_divergence"


def test_analyze_company_returns_data_not_ready_when_current_snapshot_missing_required_values():
    fundamentals = FakeFundamentals({})
    service = AnalyzerService(fundamentals=fundamentals, store=FakeStore())

    result = service.analyze_company("000001.SZ", "20250630")

    assert result.status == CompanyAnalysisStatus.DATA_NOT_READY
    assert "Tushare 暂未返回" in result.message
    assert result.card is None


def test_analyze_company_returns_data_incomplete_when_hard_check_fails():
    current = snapshot(period="20250630", revenue=-1.0)
    fundamentals = FakeFundamentals({
        ("000001.SZ", "20250630"): current,
        ("000001.SZ", "20250331"): snapshot(period="20250331"),
        ("000001.SZ", "20240630"): snapshot(period="20240630"),
    })
    service = AnalyzerService(fundamentals=fundamentals, store=FakeStore())

    result = service.analyze_company("000001.SZ", "20250630")

    assert result.status == CompanyAnalysisStatus.DATA_INCOMPLETE
    assert "current.revenue is negative" in result.message
    assert result.card is None
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_analyzer_service.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `copilot.service.analyzer` does not exist.

- [ ] **Step 3: Implement analyzer service**

Create `copilot/service/analyzer.py`:

```python
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel

from copilot.checks.reconcile import CheckStatus, run_hard_checks
from copilot.config import RuleThresholds
from copilot.context import assemble_context, prior_quarter_period, prior_year_period
from copilot.models import PeriodSnapshot
from copilot.report.builder import CompanyCard, DailySummary, build_company_card, build_daily_summary
from copilot.rules.registry import build_rules, run_rules


class FundamentalsProvider(Protocol):
    def fetch_snapshot(self, ts_code: str, period: str) -> PeriodSnapshot: ...


class SnapshotStore(Protocol):
    def upsert_snapshot(self, snapshot: PeriodSnapshot) -> None: ...
    def get_snapshot(self, ts_code: str, period: str) -> PeriodSnapshot | None: ...
    def replace_findings(self, ts_code: str, period: str, findings) -> None: ...


class CompanyAnalysisStatus(StrEnum):
    OK = "OK"
    DATA_INCOMPLETE = "DATA_INCOMPLETE"
    DATA_NOT_READY = "DATA_NOT_READY"
    ERROR = "ERROR"


class CompanyAnalysisResult(BaseModel):
    status: CompanyAnalysisStatus
    message: str
    card: CompanyCard | None = None


_REQUIRED_CURRENT_FIELDS = ["revenue", "net_profit", "gross_margin_pct", "operating_cash_flow"]


class AnalyzerService:
    def __init__(self, fundamentals: FundamentalsProvider, store: SnapshotStore, thresholds: RuleThresholds | None = None, coverage_pool: list[str] | None = None, calendar=None):
        self.fundamentals = fundamentals
        self.store = store
        self.thresholds = thresholds or RuleThresholds()
        self.coverage_pool = coverage_pool or []
        self.calendar = calendar

    def _fetch_and_store(self, ts_code: str, period: str) -> PeriodSnapshot:
        snapshot = self.fundamentals.fetch_snapshot(ts_code, period)
        self.store.upsert_snapshot(snapshot)
        return snapshot

    def _current_ready(self, snapshot: PeriodSnapshot) -> bool:
        return all(snapshot.value(field) is not None for field in _REQUIRED_CURRENT_FIELDS)

    def analyze_company(self, ts_code: str, period: str) -> CompanyAnalysisResult:
        current = self._fetch_and_store(ts_code, period)
        self._fetch_and_store(ts_code, prior_quarter_period(period))
        self._fetch_and_store(ts_code, prior_year_period(period))

        if not self._current_ready(current):
            return CompanyAnalysisResult(
                status=CompanyAnalysisStatus.DATA_NOT_READY,
                message=f"Tushare 暂未返回 {ts_code} {period} 的完整财务快照",
            )

        ctx = assemble_context(self.store, ts_code, period)
        check = run_hard_checks(ctx)
        if check.status != CheckStatus.OK:
            return CompanyAnalysisResult(
                status=CompanyAnalysisStatus.DATA_INCOMPLETE,
                message="；".join(check.messages),
            )

        findings = run_rules(ctx, build_rules(self.thresholds))
        self.store.replace_findings(ts_code, period, findings)
        card = build_company_card(ctx, findings)
        return CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=card)
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_analyzer_service.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/service/analyzer.py tests/test_analyzer_service.py
git commit -m "feat: analyze real company fundamentals"
```

---

### Task 5: Analyzer Disclosure-Day Aggregation

**Files:**
- Modify: `copilot/service/analyzer.py`
- Create: `tests/test_analyzer_disclosure_day.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_analyzer_disclosure_day.py`:

```python
from copilot.datasource.calendar import DisclosureEvent
from copilot.models import PeriodSnapshot
from copilot.service.analyzer import AnalyzerService


class FakeCalendar:
    def fetch_events(self, date, coverage_pool):
        assert date == "20250821"
        assert coverage_pool == {"000001.SZ", "600000.SH"}
        return [
            DisclosureEvent(ts_code="000001.SZ", ann_date="20250821", period="20250630"),
            DisclosureEvent(ts_code="600000.SH", ann_date="20250821", period="20250630"),
        ]


class EmptyCalendar:
    def fetch_events(self, date, coverage_pool):
        return []


class FakeFundamentals:
    def fetch_snapshot(self, ts_code, period):
        return PeriodSnapshot(
            ts_code=ts_code,
            period=period,
            ann_date="20250821",
            revenue=100.0,
            net_profit=10.0,
            deducted_net_profit=9.0,
            gross_margin_pct=30.0,
            operating_cash_flow=8.0,
            accounts_receivable=20.0,
            inventory=15.0,
        )


class FakeStore:
    def __init__(self):
        self.snapshots = {}
        self.findings = {}

    def upsert_snapshot(self, snapshot):
        self.snapshots[(snapshot.ts_code, snapshot.period)] = snapshot

    def get_snapshot(self, ts_code, period):
        return self.snapshots.get((ts_code, period))

    def replace_findings(self, ts_code, period, findings):
        self.findings[(ts_code, period)] = findings


def test_analyze_disclosure_day_builds_summary_for_coverage_events():
    service = AnalyzerService(
        fundamentals=FakeFundamentals(),
        store=FakeStore(),
        coverage_pool=["000001.SZ", "600000.SH"],
        calendar=FakeCalendar(),
    )

    summary = service.analyze_disclosure_day("20250821")

    assert summary.date == "20250821"
    assert summary.coverage_count == 2
    assert summary.disclosed_count == 2
    assert [card.ts_code for card in summary.cards] == ["000001.SZ", "600000.SH"]


def test_analyze_disclosure_day_returns_empty_summary_when_no_events():
    service = AnalyzerService(
        fundamentals=FakeFundamentals(),
        store=FakeStore(),
        coverage_pool=["000001.SZ"],
        calendar=EmptyCalendar(),
    )

    summary = service.analyze_disclosure_day("20250821")

    assert summary.coverage_count == 1
    assert summary.disclosed_count == 0
    assert summary.cards == []
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_analyzer_disclosure_day.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `AnalyzerService.analyze_disclosure_day` does not exist.

- [ ] **Step 3: Implement disclosure-day method**

In `copilot/service/analyzer.py`, add this method inside `AnalyzerService`:

```python
    def analyze_disclosure_day(self, date: str) -> DailySummary:
        if self.calendar is None:
            return build_daily_summary(date, coverage_count=len(self.coverage_pool), cards=[])
        events = self.calendar.fetch_events(date, set(self.coverage_pool))
        cards: list[CompanyCard] = []
        for event in events:
            result = self.analyze_company(event.ts_code, event.period)
            if result.card is not None:
                cards.append(result.card)
        return build_daily_summary(date, coverage_count=len(self.coverage_pool), cards=cards)
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_analyzer_disclosure_day.py tests/test_analyzer_service.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/service/analyzer.py tests/test_analyzer_disclosure_day.py
git commit -m "feat: analyze disclosure day summaries"
```

---

### Task 6: Analysis API Routes

**Files:**
- Modify: `copilot/api/app.py`
- Modify: `copilot/api/dev_app.py`
- Create: `tests/test_api_analysis_routes.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_api_analysis_routes.py`:

```python
from fastapi.testclient import TestClient

from copilot.api.app import create_app
from copilot.models import Context
from copilot.report.builder import build_company_card, build_daily_summary, build_quarterly_review
from copilot.eval.backtest import BacktestSummary
from copilot.service.analyzer import CompanyAnalysisResult, CompanyAnalysisStatus


class FakeFullService:
    def __init__(self, make_snapshot):
        self.card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
        self.summary = build_daily_summary("20250821", 1, [self.card])
        self.quarterly = build_quarterly_review(
            BacktestSummary(start_date="20250801", end_date="20250831", coverage_count=1, disclosed_count=1, ok_count=1, data_incomplete_count=0, finding_count=0, finding_distribution={}, company_results=[]),
            precision_pct=None,
        )

    def get_company_card(self, ts_code, period):
        return self.card

    def get_daily_summary(self, date):
        return self.summary

    def get_evidence(self, ts_code, period, rule_id):
        return []

    def get_quarterly_review(self):
        return self.quarterly

    def analyze_company(self, ts_code, period):
        return CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=self.card)

    def analyze_disclosure_day(self, date):
        return self.summary


def test_analyze_company_route(make_snapshot):
    client = TestClient(create_app(FakeFullService(make_snapshot)))

    response = client.post("/api/analyze/company", json={"ts_code": "000001.SZ", "period": "20250630"})

    assert response.status_code == 200
    assert response.json()["status"] == "OK"
    assert response.json()["card"]["ts_code"] == "000001.SZ"


def test_analyze_disclosure_day_route(make_snapshot):
    client = TestClient(create_app(FakeFullService(make_snapshot)))

    response = client.post("/api/analyze/disclosure-day", json={"date": "20250821"})

    assert response.status_code == 200
    assert response.json()["date"] == "20250821"
    assert response.json()["disclosed_count"] == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_api_analysis_routes.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `/api/analyze/company` and `/api/analyze/disclosure-day` do not exist.

- [ ] **Step 3: Implement routes**

Modify `copilot/api/app.py` imports:

```python
from pydantic import BaseModel
from copilot.service.analyzer import CompanyAnalysisResult
```

Add request models above `create_app`:

```python
class AnalyzeCompanyRequest(BaseModel):
    ts_code: str
    period: str


class AnalyzeDisclosureDayRequest(BaseModel):
    date: str
```

Add to `ReportService` protocol:

```python
    def analyze_company(self, ts_code: str, period: str) -> CompanyAnalysisResult: ...

    def analyze_disclosure_day(self, date: str) -> DailySummary: ...
```

Add routes before existing static mount:

```python
    @app.post("/api/analyze/company", response_model=CompanyAnalysisResult)
    def analyze_company(request: AnalyzeCompanyRequest):
        return report_service.analyze_company(request.ts_code, request.period)

    @app.post("/api/analyze/disclosure-day", response_model=DailySummary)
    def analyze_disclosure_day(request: AnalyzeDisclosureDayRequest):
        return report_service.analyze_disclosure_day(request.date)
```

- [ ] **Step 4: Update demo service to satisfy protocol**

In `copilot/api/dev_app.py`, import:

```python
from copilot.service.analyzer import CompanyAnalysisResult, CompanyAnalysisStatus
```

Add methods to `DemoReportService`:

```python
    def analyze_company(self, ts_code, period):
        if ts_code == self.card.ts_code and period == self.card.period:
            return CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=self.card)
        return CompanyAnalysisResult(status=CompanyAnalysisStatus.DATA_NOT_READY, message="demo service only contains 000001.SZ 20250630")

    def analyze_disclosure_day(self, date):
        if date == self.summary.date:
            return self.summary
        return build_daily_summary(date, 42, [])
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_api_analysis_routes.py tests/test_api_app.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add copilot/api/app.py copilot/api/dev_app.py tests/test_api_analysis_routes.py
git commit -m "feat: expose analysis API routes"
```

---

### Task 7: Real App Wiring and Start Script

**Files:**
- Create: `copilot/api/real_app.py`
- Create: `start_real.bat`
- Create: `tests/test_real_app_startup.py`

- [ ] **Step 1: Write failing startup tests**

Create `tests/test_real_app_startup.py`:

```python
from pathlib import Path

from copilot.api.real_app import app


def test_real_app_exports_fastapi_app():
    assert app.title == "TradeEye Copilot"


def test_start_real_bat_launches_real_app():
    content = Path("start_real.bat").read_text(encoding="utf-8")

    assert "python -m pip install -e .[dev]" in content
    assert "uvicorn copilot.api.real_app:app --reload" in content
    assert "http://127.0.0.1:8000/" in content
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_real_app_startup.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `copilot.api.real_app` and `start_real.bat` do not exist.

- [ ] **Step 3: Implement real app**

Create `copilot/api/real_app.py`:

```python
from copilot.api.app import create_app
from copilot.config import load_settings
from copilot.datasource.calendar import TushareDisclosureCalendarClient
from copilot.datasource.fundamentals import TushareFundamentalsClient
from copilot.datasource.tushare_client import create_tushare_pro, TushareTokenMissing
from copilot.report.builder import build_daily_summary, build_quarterly_review
from copilot.eval.backtest import BacktestSummary
from copilot.service.analyzer import AnalyzerService, CompanyAnalysisResult, CompanyAnalysisStatus
from copilot.service.report_cache import ReportCache
from copilot.store.sqlite import SQLiteStore


class RealReportService:
    def __init__(self):
        self.settings = load_settings()
        self.cache = ReportCache()
        self.store = SQLiteStore(self.settings.database.path)
        self.store.init_schema()
        try:
            pro = create_tushare_pro(self.settings.tushare.token)
        except TushareTokenMissing:
            pro = None
        self.analyzer = None
        if pro is not None:
            self.analyzer = AnalyzerService(
                fundamentals=TushareFundamentalsClient(pro, max_retries=self.settings.tushare.max_retries),
                store=self.store,
                thresholds=self.settings.rules.thresholds,
                coverage_pool=self.settings.eval.coverage_pool,
                calendar=TushareDisclosureCalendarClient(pro),
            )

    def get_company_card(self, ts_code, period):
        return self.cache.get_company(ts_code, period)

    def get_daily_summary(self, date):
        return self.cache.get_daily(date)

    def get_evidence(self, ts_code, period, rule_id):
        card = self.cache.get_company(ts_code, period)
        if card is None:
            return []
        for finding in card.findings:
            if finding.rule_id == rule_id:
                return finding.evidence
        return []

    def get_quarterly_review(self):
        return build_quarterly_review(
            BacktestSummary(
                start_date=self.settings.eval.start_date,
                end_date=self.settings.eval.end_date,
                coverage_count=len(self.settings.eval.coverage_pool),
                disclosed_count=0,
                ok_count=0,
                data_incomplete_count=0,
                finding_count=0,
                finding_distribution={},
                company_results=[],
            ),
            precision_pct=None,
        )

    def analyze_company(self, ts_code, period):
        if self.analyzer is None:
            return CompanyAnalysisResult(status=CompanyAnalysisStatus.ERROR, message="未配置 TUSHARE_TOKEN")
        result = self.analyzer.analyze_company(ts_code, period)
        if result.card is not None:
            self.cache.put_company(result.card)
        return result

    def analyze_disclosure_day(self, date):
        if self.analyzer is None:
            summary = build_daily_summary(date, len(self.settings.eval.coverage_pool), [])
            self.cache.put_daily(summary)
            return summary
        summary = self.analyzer.analyze_disclosure_day(date)
        for card in summary.cards:
            self.cache.put_company(card)
        self.cache.put_daily(summary)
        return summary


app = create_app(RealReportService())
```

- [ ] **Step 4: Create real start script**

Create `start_real.bat`:

```bat
@echo off
setlocal

cd /d "%~dp0"

echo [TradeEye Copilot] Installing local dependencies...
python -m pip install -e .[dev]
if errorlevel 1 (
    echo.
    echo Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo [TradeEye Copilot] Opening dashboard: http://127.0.0.1:8000/
start "" "http://127.0.0.1:8000/"

echo.
echo [TradeEye Copilot] Starting real data server...
echo Press Ctrl+C to stop.
python -m uvicorn copilot.api.real_app:app --reload --host 127.0.0.1 --port 8000

endlocal
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_real_app_startup.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add copilot/api/real_app.py start_real.bat tests/test_real_app_startup.py
git commit -m "feat: wire real data app startup"
```

---

### Task 8: RSS Announcement Parser

**Files:**
- Create: `copilot/rss/__init__.py`
- Create: `copilot/rss/announcements.py`
- Create: `tests/test_rss_announcements.py`

- [ ] **Step 1: Write failing parser tests**

Create `tests/test_rss_announcements.py`:

```python
from copilot.rss.announcements import AnnouncementEvent, classify_announcement, parse_rss_entries


def test_classify_announcement_accepts_half_year_report():
    event = classify_announcement(
        title="平安银行：2025年半年度报告",
        link="https://example.com/a",
        company_to_ts_code={"平安银行": "000001.SZ"},
    )

    assert event == AnnouncementEvent(ts_code="000001.SZ", title="平安银行：2025年半年度报告", link="https://example.com/a", period="20250630", status="SEEN")


def test_classify_announcement_excludes_summary_and_corrections():
    company_to_ts_code = {"平安银行": "000001.SZ"}

    assert classify_announcement("平安银行：2025年半年度报告摘要", "u", company_to_ts_code) is None
    assert classify_announcement("平安银行：2025年半年度报告更正公告", "u", company_to_ts_code) is None


def test_classify_announcement_infers_common_periods():
    company_to_ts_code = {"平安银行": "000001.SZ"}

    assert classify_announcement("平安银行：2025年年度报告", "u", company_to_ts_code).period == "20251231"
    assert classify_announcement("平安银行：2025年第一季度报告", "u", company_to_ts_code).period == "20250331"
    assert classify_announcement("平安银行：2025年第三季度报告", "u", company_to_ts_code).period == "20250930"


def test_parse_rss_entries_extracts_title_and_link():
    xml = """
    <rss><channel>
      <item><title>平安银行：2025年半年度报告</title><link>https://example.com/a</link></item>
      <item><title>其他公告</title><link>https://example.com/b</link></item>
    </channel></rss>
    """

    entries = parse_rss_entries(xml, max_entries=10)

    assert entries == [
        ("平安银行：2025年半年度报告", "https://example.com/a"),
        ("其他公告", "https://example.com/b"),
    ]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_rss_announcements.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `copilot.rss.announcements` does not exist.

- [ ] **Step 3: Implement parser**

Create `copilot/rss/__init__.py`:

```python
"""RSS announcement trigger utilities."""
```

Create `copilot/rss/announcements.py`:

```python
from pydantic import BaseModel
import re
import xml.etree.ElementTree as ET


class AnnouncementEvent(BaseModel):
    ts_code: str
    title: str
    link: str
    period: str
    status: str = "SEEN"


_EXCLUDE_KEYWORDS = ["摘要", "取消", "更正", "补充", "英文版"]


def parse_rss_entries(xml_text: str, max_entries: int) -> list[tuple[str, str]]:
    root = ET.fromstring(xml_text)
    entries: list[tuple[str, str]] = []
    for item in root.findall(".//item")[:max_entries]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title:
            entries.append((title, link))
    return entries


def _infer_year(title: str) -> str | None:
    match = re.search(r"(20\d{2})年", title)
    return match.group(1) if match else None


def _infer_period(title: str) -> str | None:
    year = _infer_year(title)
    if year is None:
        return None
    if "第一季度报告" in title or "一季报" in title:
        return f"{year}0331"
    if "半年度报告" in title or "半年报" in title:
        return f"{year}0630"
    if "第三季度报告" in title or "三季报" in title:
        return f"{year}0930"
    if "年度报告" in title or "年报" in title:
        return f"{year}1231"
    return None


def classify_announcement(title: str, link: str, company_to_ts_code: dict[str, str]) -> AnnouncementEvent | None:
    if any(keyword in title for keyword in _EXCLUDE_KEYWORDS):
        return None
    period = _infer_period(title)
    if period is None:
        return None
    for company_name, ts_code in company_to_ts_code.items():
        if company_name in title:
            return AnnouncementEvent(ts_code=ts_code, title=title, link=link, period=period)
    return None
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_rss_announcements.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/rss/__init__.py copilot/rss/announcements.py tests/test_rss_announcements.py
git commit -m "feat: classify financial report rss announcements"
```

---

### Task 9: RSS Poll Service

**Files:**
- Create: `copilot/rss/service.py`
- Create: `tests/test_rss_service.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_rss_service.py`:

```python
import httpx

from copilot.models import Context
from copilot.report.builder import build_company_card
from copilot.rss.service import RssPollService
from copilot.service.analyzer import CompanyAnalysisResult, CompanyAnalysisStatus


class FakeAnalyzer:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def analyze_company(self, ts_code, period):
        self.calls.append((ts_code, period))
        return self.result


def test_rss_poll_service_analyzes_matched_announcements(make_snapshot):
    xml = """
    <rss><channel>
      <item><title>平安银行：2025年半年度报告</title><link>https://example.com/a</link></item>
    </channel></rss>
    """
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    analyzer = FakeAnalyzer(CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=card))

    def handler(request):
        return httpx.Response(200, text=xml)

    service = RssPollService(
        feeds=["https://example.com/rss.xml"],
        max_entries=10,
        company_to_ts_code={"平安银行": "000001.SZ"},
        analyzer=analyzer,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = service.poll()

    assert result.seen_count == 1
    assert result.matched_count == 1
    assert result.analyzed_count == 1
    assert result.pending_count == 0
    assert result.events[0].status == "ANALYZED"
    assert analyzer.calls == [("000001.SZ", "20250630")]


def test_rss_poll_service_marks_pending_when_tushare_not_ready():
    xml = """
    <rss><channel>
      <item><title>平安银行：2025年半年度报告</title><link>https://example.com/a</link></item>
    </channel></rss>
    """
    analyzer = FakeAnalyzer(CompanyAnalysisResult(status=CompanyAnalysisStatus.DATA_NOT_READY, message="not ready"))

    def handler(request):
        return httpx.Response(200, text=xml)

    service = RssPollService(
        feeds=["https://example.com/rss.xml"],
        max_entries=10,
        company_to_ts_code={"平安银行": "000001.SZ"},
        analyzer=analyzer,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = service.poll()

    assert result.analyzed_count == 0
    assert result.pending_count == 1
    assert result.events[0].status == "DATA_PENDING"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_rss_service.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `copilot.rss.service` does not exist.

- [ ] **Step 3: Implement RSS service**

Create `copilot/rss/service.py`:

```python
from typing import Protocol

import httpx
from pydantic import BaseModel

from copilot.rss.announcements import AnnouncementEvent, classify_announcement, parse_rss_entries
from copilot.service.analyzer import CompanyAnalysisResult, CompanyAnalysisStatus


class AnalyzerLike(Protocol):
    def analyze_company(self, ts_code: str, period: str) -> CompanyAnalysisResult: ...


class RssPollResult(BaseModel):
    seen_count: int
    matched_count: int
    analyzed_count: int
    pending_count: int
    events: list[AnnouncementEvent]


class RssPollService:
    def __init__(self, feeds: list[str], max_entries: int, company_to_ts_code: dict[str, str], analyzer: AnalyzerLike, http_client: httpx.Client | None = None):
        self.feeds = feeds
        self.max_entries = max_entries
        self.company_to_ts_code = company_to_ts_code
        self.analyzer = analyzer
        self.http_client = http_client or httpx.Client(timeout=10)
        self._seen_keys: set[tuple[str, str, str]] = set()

    def poll(self) -> RssPollResult:
        seen_count = 0
        matched: list[AnnouncementEvent] = []
        for feed in self.feeds:
            response = self.http_client.get(feed)
            response.raise_for_status()
            entries = parse_rss_entries(response.text, self.max_entries)
            seen_count += len(entries)
            for title, link in entries:
                event = classify_announcement(title, link, self.company_to_ts_code)
                if event is None:
                    continue
                key = (event.ts_code, event.period, event.link)
                if key in self._seen_keys:
                    continue
                self._seen_keys.add(key)
                result = self.analyzer.analyze_company(event.ts_code, event.period)
                event.status = "ANALYZED" if result.status == CompanyAnalysisStatus.OK else "DATA_PENDING"
                matched.append(event)
        return RssPollResult(
            seen_count=seen_count,
            matched_count=len(matched),
            analyzed_count=sum(1 for event in matched if event.status == "ANALYZED"),
            pending_count=sum(1 for event in matched if event.status == "DATA_PENDING"),
            events=matched,
        )
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_rss_service.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/rss/service.py tests/test_rss_service.py
git commit -m "feat: poll rss announcements as trigger hints"
```

---

### Task 10: RSS API Route

**Files:**
- Modify: `copilot/api/app.py`
- Modify: `copilot/api/dev_app.py`
- Modify: `copilot/api/real_app.py`
- Create: `tests/test_api_rss_routes.py`

- [ ] **Step 1: Write failing API test**

Create `tests/test_api_rss_routes.py`:

```python
from fastapi.testclient import TestClient

from copilot.api.app import create_app
from copilot.rss.service import RssPollResult


class FakeService:
    def get_company_card(self, ts_code, period): return None
    def get_daily_summary(self, date): return None
    def get_evidence(self, ts_code, period, rule_id): return []
    def get_quarterly_review(self): return None
    def analyze_company(self, ts_code, period): raise AssertionError("not used")
    def analyze_disclosure_day(self, date): raise AssertionError("not used")
    def poll_rss(self):
        return RssPollResult(seen_count=2, matched_count=1, analyzed_count=0, pending_count=1, events=[])


def test_rss_poll_route_returns_poll_result():
    client = TestClient(create_app(FakeService()))

    response = client.post("/api/rss/poll")

    assert response.status_code == 200
    assert response.json()["seen_count"] == 2
    assert response.json()["pending_count"] == 1
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_api_rss_routes.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `/api/rss/poll` does not exist.

- [ ] **Step 3: Add route and protocol method**

In `copilot/api/app.py`, import:

```python
from copilot.rss.service import RssPollResult
```

Add to `ReportService` protocol:

```python
    def poll_rss(self) -> RssPollResult: ...
```

Add route before static mount:

```python
    @app.post("/api/rss/poll", response_model=RssPollResult)
    def poll_rss():
        return report_service.poll_rss()
```

- [ ] **Step 4: Update demo service**

In `copilot/api/dev_app.py`, import:

```python
from copilot.rss.service import RssPollResult
```

Add method:

```python
    def poll_rss(self):
        return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])
```

- [ ] **Step 5: Update real service**

In `copilot/api/real_app.py`, import:

```python
from copilot.rss.service import RssPollResult, RssPollService
```

Inside `RealReportService.__init__`, after analyzer setup, add:

```python
        self.rss_service = None
        if self.analyzer is not None:
            company_to_ts_code = {ts_code: ts_code for ts_code in self.settings.eval.coverage_pool}
            self.rss_service = RssPollService(
                feeds=self.settings.rss.feeds,
                max_entries=self.settings.rss.max_entries,
                company_to_ts_code=company_to_ts_code,
                analyzer=self.analyzer,
            )
```

Add method:

```python
    def poll_rss(self):
        if self.rss_service is None:
            return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])
        return self.rss_service.poll()
```

Note: `company_to_ts_code` is initially identity mapping because `coverage_pool` currently stores only `ts_code`. Future work can add display names to config.

- [ ] **Step 6: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_api_rss_routes.py tests/test_api_app.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add copilot/api/app.py copilot/api/dev_app.py copilot/api/real_app.py tests/test_api_rss_routes.py
git commit -m "feat: expose rss poll API"
```

---

### Task 11: Feishu Disclosure-Day Notify Route

**Files:**
- Modify: `copilot/api/app.py`
- Modify: `copilot/api/dev_app.py`
- Modify: `copilot/api/real_app.py`
- Create: `tests/test_api_notify_routes.py`

- [ ] **Step 1: Write failing notify route tests**

Create `tests/test_api_notify_routes.py`:

```python
from fastapi.testclient import TestClient
from pydantic import BaseModel

from copilot.api.app import create_app
from copilot.models import Context
from copilot.report.builder import build_company_card, build_daily_summary
from copilot.rss.service import RssPollResult


class NotifyResult(BaseModel):
    sent: bool
    reason: str


class FakeNotifyService:
    def __init__(self, make_snapshot, summary):
        self.summary = summary
        self.card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])

    def get_company_card(self, ts_code, period): return self.card
    def get_daily_summary(self, date): return self.summary
    def get_evidence(self, ts_code, period, rule_id): return []
    def get_quarterly_review(self): return None
    def analyze_company(self, ts_code, period): raise AssertionError("not used")
    def analyze_disclosure_day(self, date): return self.summary
    def poll_rss(self): return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])
    def notify_feishu_disclosure_day(self, date):
        return NotifyResult(sent=self.summary.disclosed_count > 0, reason="ok" if self.summary.disclosed_count > 0 else "no_disclosures")


def test_notify_feishu_disclosure_day_sends_when_summary_has_cards(make_snapshot):
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    summary = build_daily_summary("20250821", 1, [card])
    client = TestClient(create_app(FakeNotifyService(make_snapshot, summary)))

    response = client.post("/api/notify/feishu/disclosure-day/20250821")

    assert response.status_code == 200
    assert response.json() == {"sent": True, "reason": "ok"}


def test_notify_feishu_disclosure_day_skips_when_no_disclosures(make_snapshot):
    summary = build_daily_summary("20250821", 1, [])
    client = TestClient(create_app(FakeNotifyService(make_snapshot, summary)))

    response = client.post("/api/notify/feishu/disclosure-day/20250821")

    assert response.status_code == 200
    assert response.json() == {"sent": False, "reason": "no_disclosures"}
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_api_notify_routes.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `/api/notify/feishu/disclosure-day/{date}` does not exist.

- [ ] **Step 3: Implement API result model and route**

In `copilot/api/app.py`, add:

```python
class NotifyResult(BaseModel):
    sent: bool
    reason: str
```

Add to `ReportService` protocol:

```python
    def notify_feishu_disclosure_day(self, date: str) -> NotifyResult: ...
```

Add route before static mount:

```python
    @app.post("/api/notify/feishu/disclosure-day/{date}", response_model=NotifyResult)
    def notify_feishu_disclosure_day(date: str):
        return report_service.notify_feishu_disclosure_day(date)
```

- [ ] **Step 4: Update demo service**

In `copilot/api/dev_app.py`, import:

```python
from copilot.api.app import NotifyResult
```

Add method:

```python
    def notify_feishu_disclosure_day(self, date):
        if date != self.summary.date:
            return NotifyResult(sent=False, reason="no_disclosures")
        return NotifyResult(sent=False, reason="webhook_not_configured")
```

- [ ] **Step 5: Update real service**

In `copilot/api/real_app.py`, import:

```python
from copilot.api.app import NotifyResult
from copilot.notify.feishu import FeishuNotifier, render_daily_summary_text
```

Add method:

```python
    def notify_feishu_disclosure_day(self, date):
        summary = self.cache.get_daily(date)
        if summary is None:
            summary = self.analyze_disclosure_day(date)
        if summary.disclosed_count == 0:
            return NotifyResult(sent=False, reason="no_disclosures")
        webhook = self.settings.notify.feishu_webhook
        if not webhook:
            return NotifyResult(sent=False, reason="webhook_not_configured")
        sent = FeishuNotifier(webhook).send_text(render_daily_summary_text(summary))
        return NotifyResult(sent=sent, reason="ok" if sent else "send_failed")
```

- [ ] **Step 6: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_api_notify_routes.py tests/test_notify_feishu.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add copilot/api/app.py copilot/api/dev_app.py copilot/api/real_app.py tests/test_api_notify_routes.py
git commit -m "feat: expose feishu disclosure notification API"
```

---

### Task 12: Frontend API Adapter and Minimal Controls

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Create: `tests/test_frontend_contracts.py`

- [ ] **Step 1: Write failing frontend contract tests**

Create `tests/test_frontend_contracts.py`:

```python
from pathlib import Path


def test_frontend_defines_api_wrapper_methods():
    content = Path("web/app.js").read_text(encoding="utf-8")

    assert "analyzeCompany(tsCode, period)" in content
    assert "analyzeDisclosureDay(date)" in content
    assert "sendFeishuDisclosureDay(date)" in content
    assert "pollRss()" in content
    assert "/api/analyze/company" in content
    assert "/api/analyze/disclosure-day" in content
    assert "/api/notify/feishu/disclosure-day/" in content
    assert "/api/rss/poll" in content


def test_frontend_has_minimal_real_data_controls():
    content = Path("web/index.html").read_text(encoding="utf-8")

    assert "company-ts-code" in content
    assert "company-period" in content
    assert "analyze-company" in content
    assert "disclosure-date" in content
    assert "analyze-disclosure-day" in content
    assert "send-feishu" in content
    assert "poll-rss" in content
    assert "operation-status" in content
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_frontend_contracts.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because frontend does not yet expose these controls/wrappers.

- [ ] **Step 3: Update HTML controls**

In `web/index.html`, inside `<main class="page">` after the hero section, insert:

```html
    <section class="controls">
      <div class="control-group">
        <h2>单票研判</h2>
        <input id="company-ts-code" type="text" value="000001.SZ" aria-label="股票代码" />
        <input id="company-period" type="text" value="20250630" aria-label="报告期" />
        <button id="analyze-company">生成单票研判</button>
      </div>
      <div class="control-group">
        <h2>披露日汇总</h2>
        <input id="disclosure-date" type="text" value="20250821" aria-label="披露日期" />
        <button id="analyze-disclosure-day">生成披露日汇总</button>
        <button id="send-feishu">发送飞书</button>
      </div>
      <div class="control-group">
        <h2>RSS 触发</h2>
        <button id="poll-rss">轮询 RSS</button>
      </div>
      <pre id="operation-status" class="operation-status"></pre>
    </section>
```

Keep existing cards and quarterly sections.

- [ ] **Step 4: Replace JavaScript with API wrapper version**

Replace `web/app.js` with:

```javascript
const dateInput = document.querySelector("#date-input");
const title = document.querySelector("#summary-title");
const summaryLine = document.querySelector("#summary-line");
const cards = document.querySelector("#cards");
const dialog = document.querySelector("#evidence-dialog");
const evidenceContent = document.querySelector("#evidence-content");
const closeDialog = document.querySelector("#close-dialog");
const quarterlyReview = document.querySelector("#quarterly-review");
const operationStatus = document.querySelector("#operation-status");

const api = {
  async analyzeCompany(tsCode, period) {
    const response = await fetch("/api/analyze/company", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ts_code: tsCode, period }),
    });
    return response.json();
  },

  async analyzeDisclosureDay(date) {
    const response = await fetch("/api/analyze/disclosure-day", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date }),
    });
    return response.json();
  },

  async sendFeishuDisclosureDay(date) {
    const response = await fetch(`/api/notify/feishu/disclosure-day/${date}`, { method: "POST" });
    return response.json();
  },

  async pollRss() {
    const response = await fetch("/api/rss/poll", { method: "POST" });
    return response.json();
  },
};

function setStatus(payload) {
  operationStatus.textContent = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
}

function severityClass(card) {
  if (card.max_severity === "RED") return "red";
  if (card.max_severity === "YELLOW") return "yellow";
  return "ok";
}

function severityIcon(card) {
  if (card.max_severity === "RED") return "🔴";
  if (card.max_severity === "YELLOW") return "🟡";
  return "✅";
}

async function showEvidence(card, finding) {
  const response = await fetch(`/api/evidence/${card.ts_code}/${card.period}/${finding.rule_id}`);
  const evidence = await response.json();
  evidenceContent.textContent = JSON.stringify(evidence, null, 2);
  dialog.showModal();
}

function renderCard(card) {
  const el = document.createElement("article");
  el.className = `card ${severityClass(card)}`;
  el.innerHTML = `
    <h2>${severityIcon(card)} ${card.ts_code} ${card.period}</h2>
    <p>${card.fact_line}</p>
    <div class="findings"></div>
    <p>${card.attribution || "归因生成失败或未启用"}</p>
    <p>${card.market_line}</p>
  `;
  const findingsEl = el.querySelector(".findings");
  if (card.findings.length === 0) {
    findingsEl.innerHTML = `<p>未见异常</p>`;
  } else {
    for (const finding of card.findings) {
      const item = document.createElement("div");
      item.className = "finding";
      item.innerHTML = `<strong>${finding.title}</strong><p>${finding.detail}</p>`;
      const button = document.createElement("button");
      button.textContent = "依据";
      button.addEventListener("click", () => showEvidence(card, finding));
      item.appendChild(button);
      findingsEl.appendChild(item);
    }
  }
  return el;
}

function renderDaily(summary) {
  title.textContent = `${summary.date} 财报研判 · 覆盖池 ${summary.coverage_count} 只`;
  summaryLine.textContent = `今日披露 ${summary.disclosed_count} 家 | 需优先关注 ${summary.red_count} | 留意 ${summary.yellow_count} | 未见异常 ${summary.ok_count}`;
  cards.innerHTML = "";
  for (const card of summary.cards) {
    cards.appendChild(renderCard(card));
  }
}

async function loadDaily(date) {
  const response = await fetch(`/api/daily/${date}`);
  if (!response.ok) return;
  renderDaily(await response.json());
}

async function loadQuarterly() {
  const response = await fetch("/api/quarterly");
  if (!response.ok) return;
  const review = await response.json();
  quarterlyReview.innerHTML = `
    <div class="metric"><span>区间</span><strong>${review.period_label}</strong></div>
    <div class="metric"><span>覆盖池</span><strong>${review.coverage_count}</strong></div>
    <div class="metric"><span>已披露</span><strong>${review.disclosed_count}</strong></div>
    <div class="metric"><span>命中</span><strong>${review.finding_count}</strong></div>
    <div class="metric"><span>精确率</span><strong>${review.precision_pct ?? "待复核"}</strong></div>
  `;
  for (const item of review.top_rules) {
    const metric = document.createElement("div");
    metric.className = "metric";
    metric.innerHTML = `<span>${item.rule_id}</span><strong>${item.count}</strong>`;
    quarterlyReview.appendChild(metric);
  }
}

closeDialog.addEventListener("click", () => dialog.close());
dateInput.addEventListener("change", () => loadDaily(dateInput.value));

document.querySelector("#analyze-company").addEventListener("click", async () => {
  const tsCode = document.querySelector("#company-ts-code").value.trim();
  const period = document.querySelector("#company-period").value.trim();
  const result = await api.analyzeCompany(tsCode, period);
  setStatus(result);
  if (result.card) {
    cards.innerHTML = "";
    cards.appendChild(renderCard(result.card));
  }
});

document.querySelector("#analyze-disclosure-day").addEventListener("click", async () => {
  const date = document.querySelector("#disclosure-date").value.trim();
  const summary = await api.analyzeDisclosureDay(date);
  setStatus(summary);
  renderDaily(summary);
});

document.querySelector("#send-feishu").addEventListener("click", async () => {
  const date = document.querySelector("#disclosure-date").value.trim();
  setStatus(await api.sendFeishuDisclosureDay(date));
});

document.querySelector("#poll-rss").addEventListener("click", async () => {
  setStatus(await api.pollRss());
});

loadDaily(dateInput.value);
loadQuarterly();
```

- [ ] **Step 5: Add minimal CSS**

Append to `web/styles.css`:

```css
.controls {
  margin-top: 24px;
  display: grid;
  gap: 12px;
  background: white;
  border: 1px solid #e3e7f0;
  border-radius: 16px;
  padding: 20px;
}

.control-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.control-group h2 {
  width: 100%;
  margin: 0;
  font-size: 16px;
}

.control-group input {
  border: 1px solid #d5dbe8;
  border-radius: 8px;
  padding: 8px 10px;
}

.operation-status {
  margin: 0;
  padding: 12px;
  background: #101827;
  color: #d8def0;
  border-radius: 10px;
  min-height: 40px;
}
```

- [ ] **Step 6: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_frontend_contracts.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/index.html web/app.js web/styles.css tests/test_frontend_contracts.py
git commit -m "feat: add frontend real data API controls"
```

---

### Task 13: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run full test suite**

Run:

```bash
python -m pytest -q --basetemp=.pytest_tmp
```

Expected: all tests PASS.

- [ ] **Step 2: Verify editable install still works**

Run:

```bash
cmd.exe //C "python -m pip install -e .[dev]"
```

Expected: `Successfully installed tradeeye-copilot-0.1.0`; no `Multiple top-level packages discovered` error.

- [ ] **Step 3: Verify demo app import**

Run:

```bash
python -c "import copilot.api.dev_app; import copilot.api.real_app; print('apps import ok')"
```

Expected: prints `apps import ok`.

- [ ] **Step 4: Verify no secret values are committed**

Run:

```bash
git grep -n -E "(api[_-]?key|token|webhook|secret|Bearer )" -- ':!docs/superpowers/plans/*' ':!README.md' ':!docs/submission-checklist.md' ':!.env.example' ':!docs/development-log.md' ':!docs/superpowers/specs/*'
```

Expected: only variable names, config field names, and fake test values appear. No real secret appears.

- [ ] **Step 5: Commit final fixes if needed**

If any verification step required fixes:

```bash
git add copilot tests web config.yaml pyproject.toml start_real.bat .env.example
git commit -m "chore: finalize real data disclosure workflow"
```

Expected: Skip if no files changed.

---

## Definition of Done

- `python -m pytest -q --basetemp=.pytest_tmp` passes.
- `start_demo.bat` still starts the demo app.
- `start_real.bat` starts `copilot.api.real_app:app`.
- `POST /api/analyze/company` returns `CompanyAnalysisResult` with card or clear status.
- `POST /api/analyze/disclosure-day` returns `DailySummary`, including empty summary for no disclosures.
- `POST /api/rss/poll` returns seen/matched/analyzed/pending counts.
- `POST /api/notify/feishu/disclosure-day/{date}` returns `{sent, reason}`.
- Frontend calls backend only through `api.analyzeCompany`, `api.analyzeDisclosureDay`, `api.sendFeishuDisclosureDay`, and `api.pollRss` wrappers.
- No code reads or prints secret values; tests use fake tokens only.

## Self-Review Notes

Spec coverage: The plan covers real Tushare settings, token-safe client factory, single-company analyzer, disclosure-day summary, RSS parser, RSS poll service, Feishu notify route, real app startup, and frontend API adapters. Excluded items from the spec remain excluded: no Ascend real call, no Feishu callback, no scheduler, no frontend visual redesign. Placeholder scan: no TBD/TODO/fill-in instructions are present; `.env` examples use explicit placeholder dots only as conventional secret placeholders, not implementation gaps. Type consistency: `CompanyAnalysisResult`, `RssPollResult`, `NotifyResult`, `DailySummary`, and `CompanyCard` names are used consistently across routes, services, and tests.
