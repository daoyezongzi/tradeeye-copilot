# Backend Remaining Work Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish non-frontend production-readiness work for TradeEye Copilot after the formal Feishu smoke: faster single-pass analysis, complete backend notification behavior, real watchlist management, industry-aware rules, automation, evaluation, observability, and attribution.

**Architecture:** Keep the current FastAPI/service boundaries and do not add frontend work in this plan. The highest-priority change is to make disclosure-day analysis single-pass: fetch each company once, produce `CompanyAnalysisResult` records, derive both `DailySummary` and `DisclosureScanResult` from those records, then render/send Feishu without a second Tushare sweep. Later batches add operational wrappers around that core path: watchlist loading, Feishu segmentation, schedulers/retries, industry rule packs, benchmark evaluation, and optional PDF/LLM attribution.

**Tech Stack:** Python 3.11+, FastAPI, pydantic, pytest, SQLite store, Tushare client, Feishu webhook text sender, existing RSS service, optional OpenAI-compatible LLM adapter.

---

## Scope Boundaries

This plan explicitly excludes frontend changes. Do not modify files under `web/` while executing this plan.

Current known state:

- Formal Feishu text send succeeded for `20250825`.
- Current smoke pool has 100 codes in `config.yaml` with `company_industries` and `company_names`.
- Current formal notify path calls `analyze_disclosure_day(date)` and then `scan_disclosure_day(date)`, which can duplicate Tushare work.
- Current formal text sends all red/yellow abnormal cards and summarizes normal companies.
- True industry rule packs beyond minimal bank hard-check routing are not implemented.

---

## File Structure

Existing files to modify:

- Modify: `copilot/service/analyzer.py` — add single-pass disclosure analysis that returns reusable company results and derives both summary and diagnostics.
- Modify: `copilot/service/disclosure_scan.py` — add `DisclosureAnalysisBundle` model and builder helpers.
- Modify: `copilot/api/real_app.py` — make notify/analyze/scan reuse one bundle path and cache outputs.
- Modify: `copilot/notify/feishu.py` — add safe segmentation helper while preserving “all abnormalities are sent”.
- Modify: `copilot/config.py` — add backend-only settings for notification chunk size, scheduler dates, and watchlist source if needed.
- Modify: `config.yaml` — keep smoke pool for now; later replace from user-provided watchlist file or explicit list.
- Modify: `copilot/rss/service.py` — later add retry-ready pending event semantics if scheduler/RSS work is executed.
- Modify: `copilot/rules/registry.py` — route future industry rule packs.
- Modify: `copilot/checks/reconcile.py` — add industry-specific hard-check requirements as real failures are found.
- Modify: `copilot/models.py` — add fields only when a selected industry rule requires them.
- Modify: `copilot/datasource/fundamentals.py` — add new Tushare field mapping only when a rule requires it.
- Modify: `copilot/report/builder.py` — add backend-only summary helpers if bundle-to-summary should live outside analyzer.
- Modify: `docs/development-log.md` — record execution results and remaining work after each batch.

New files likely to create:

- Create: `copilot/service/disclosure_bundle.py` only if `disclosure_scan.py` becomes too broad; otherwise keep bundle code in `disclosure_scan.py`.
- Create: `copilot/notify/feishu_delivery.py` — if Feishu segmentation/send orchestration becomes too large for `feishu.py`.
- Create: `copilot/watchlist.py` — loader for a user-provided YAML/CSV watchlist when replacing the smoke pool.
- Create: `copilot/scheduler.py` — manual/scheduled backend job runner after the single-pass path is stable.
- Create: `copilot/rules/bank.py` — true bank rules after fields are identified.
- Create: `copilot/rules/industry_checks.py` — industry-specific hard-check helpers if `checks/reconcile.py` grows too broad.
- Create: `copilot/eval/real_backtest.py` — real benchmark runner over a date range and coverage pool.
- Create: `copilot/observability.py` — simple timing/call-count diagnostics if not kept local to services.

New tests:

- Create: `tests/test_disclosure_analysis_bundle.py`
- Create: `tests/test_real_app_single_pass_notify.py`
- Create: `tests/test_feishu_delivery_segments.py`
- Create: `tests/test_watchlist_loader.py`
- Create: `tests/test_scheduler.py`
- Create: `tests/test_bank_rules.py` or extend current file with true metric tests
- Create: `tests/test_real_backtest.py`
- Create: `tests/test_observability.py`

---

### Task 1: Single-Pass Disclosure Analysis Bundle

**Files:**
- Modify: `copilot/service/disclosure_scan.py`
- Modify: `copilot/service/analyzer.py`
- Create: `tests/test_disclosure_analysis_bundle.py`

- [ ] **Step 1: Write failing bundle model tests**

Create `tests/test_disclosure_analysis_bundle.py`:

```python
from copilot.models import Finding, Severity
from copilot.report.builder import CompanyCard
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureScanEvent, build_analysis_bundle


def test_build_analysis_bundle_derives_summary_and_scan_from_one_result_set():
    card = CompanyCard(
        ts_code="603026.SH",
        period="20250630",
        fact_line="fact",
        findings=[Finding(rule_id="x", severity=Severity.RED, title="异常", detail="证据", evidence=[], score=99.0)],
        max_severity=Severity.RED,
        max_score=99.0,
    )
    results = [
        ("603026.SH", "20250630", "generic", CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=card)),
        ("000001.SZ", "20250630", "bank", CompanyAnalysisResult(status=CompanyAnalysisStatus.DATA_NOT_READY, message="missing", card=None)),
    ]

    bundle = build_analysis_bundle(date="20250825", coverage_count=2, results=results)

    assert bundle.date == "20250825"
    assert bundle.summary.coverage_count == 2
    assert bundle.summary.disclosed_count == 2
    assert bundle.summary.red_count == 1
    assert [card.ts_code for card in bundle.summary.cards] == ["603026.SH"]
    assert bundle.scan.coverage_count == 2
    assert bundle.scan.disclosed_count == 2
    assert bundle.scan.data_not_ready_count == 1
    assert bundle.scan.events == [
        DisclosureScanEvent(ts_code="603026.SH", period="20250630", status=CompanyAnalysisStatus.OK, message="ok", has_card=True, industry="generic"),
        DisclosureScanEvent(ts_code="000001.SZ", period="20250630", status=CompanyAnalysisStatus.DATA_NOT_READY, message="missing", has_card=False, industry="bank"),
    ]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_disclosure_analysis_bundle.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `build_analysis_bundle` does not exist.

- [ ] **Step 3: Implement bundle model and builder**

Modify `copilot/service/disclosure_scan.py`:

```python
from pydantic import BaseModel

from copilot.report.builder import DailySummary, build_daily_summary


class DisclosureAnalysisBundle(BaseModel):
    date: str
    summary: DailySummary
    scan: DisclosureScanResult


def build_analysis_bundle(date: str, coverage_count: int, results) -> DisclosureAnalysisBundle:
    cards = [result.card for _, _, _, result in results if result.card is not None]
    events = [
        DisclosureScanEvent(
            ts_code=ts_code,
            period=period,
            status=result.status,
            message=result.message,
            has_card=result.card is not None,
            industry=industry,
        )
        for ts_code, period, industry, result in results
    ]
    scan = build_scan_result(date=date, coverage_count=coverage_count, events=events)
    summary = build_daily_summary(date=date, coverage_count=coverage_count, cards=cards, disclosed_count=len(results))
    return DisclosureAnalysisBundle(date=date, summary=summary, scan=scan)
```

- [ ] **Step 4: Run test to verify pass**

Run:

```bash
python -m pytest tests/test_disclosure_analysis_bundle.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Add analyzer method test**

Append to `tests/test_disclosure_analysis_bundle.py`:

```python
from copilot.datasource.calendar import DisclosureEvent
from copilot.models import PeriodSnapshot
from copilot.service.analyzer import AnalyzerService


class BundleCalendar:
    def fetch_events(self, date, coverage_pool):
        return [
            DisclosureEvent(ts_code="603026.SH", ann_date=date, period="20250630"),
            DisclosureEvent(ts_code="000001.SZ", ann_date=date, period="20250630"),
        ]


class BundleFundamentals:
    def __init__(self):
        self.calls = []

    def fetch_snapshot(self, ts_code, period):
        self.calls.append((ts_code, period))
        if ts_code == "000001.SZ":
            return PeriodSnapshot(ts_code=ts_code, period=period)
        return PeriodSnapshot(
            ts_code=ts_code,
            period=period,
            revenue=100.0,
            net_profit=10.0,
            deducted_net_profit=9.0,
            gross_margin_pct=30.0,
            operating_cash_flow=8.0,
            accounts_receivable=20.0,
            inventory=15.0,
        )


class BundleStore:
    def __init__(self):
        self.snapshots = {}

    def upsert_snapshot(self, snapshot):
        self.snapshots[(snapshot.ts_code, snapshot.period)] = snapshot

    def get_snapshot(self, ts_code, period):
        return self.snapshots.get((ts_code, period))

    def replace_findings(self, ts_code, period, findings):
        pass


def test_analyzer_analyze_disclosure_day_bundle_fetches_each_event_once():
    fundamentals = BundleFundamentals()
    service = AnalyzerService(
        fundamentals=fundamentals,
        store=BundleStore(),
        coverage_pool=["603026.SH", "000001.SZ"],
        calendar=BundleCalendar(),
        company_industries={"603026.SH": "generic", "000001.SZ": "bank"},
    )

    bundle = service.analyze_disclosure_day_bundle("20250825")

    assert bundle.summary.disclosed_count == 2
    assert bundle.scan.disclosed_count == 2
    assert len([call for call in fundamentals.calls if call[0] == "603026.SH" and call[1] == "20250630"]) == 1
    assert len([call for call in fundamentals.calls if call[0] == "000001.SZ" and call[1] == "20250630"]) == 1
```

- [ ] **Step 6: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_disclosure_analysis_bundle.py::test_analyzer_analyze_disclosure_day_bundle_fetches_each_event_once -q --basetemp=.pytest_tmp
```

Expected: FAIL because `AnalyzerService.analyze_disclosure_day_bundle()` does not exist.

- [ ] **Step 7: Implement analyzer bundle method and refactor old methods**

Modify `copilot/service/analyzer.py` imports:

```python
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureAnalysisBundle, DisclosureScanEvent, DisclosureScanResult, build_analysis_bundle, build_scan_result
```

Add method inside `AnalyzerService`:

```python
    def analyze_disclosure_day_bundle(self, date: str) -> DisclosureAnalysisBundle:
        if self.calendar is None:
            return build_analysis_bundle(date, coverage_count=len(self.coverage_pool), results=[])
        events = self.calendar.fetch_events(date, set(self.coverage_pool))
        results = []
        for event in events:
            result = self.analyze_company(event.ts_code, event.period)
            industry = industry_for_ts_code(event.ts_code, self.company_industries).value
            results.append((event.ts_code, event.period, industry, result))
        return build_analysis_bundle(date=date, coverage_count=len(self.coverage_pool), results=results)
```

Refactor existing methods:

```python
    def analyze_disclosure_day(self, date: str) -> DailySummary:
        return self.analyze_disclosure_day_bundle(date).summary

    def scan_disclosure_day(self, date: str) -> DisclosureScanResult:
        return self.analyze_disclosure_day_bundle(date).scan
```

- [ ] **Step 8: Run bundle and existing disclosure tests**

Run:

```bash
python -m pytest tests/test_disclosure_analysis_bundle.py tests/test_disclosure_scan.py tests/test_analyzer_disclosure_day.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add copilot/service/disclosure_scan.py copilot/service/analyzer.py tests/test_disclosure_analysis_bundle.py
git commit -m "feat: build disclosure summaries from single analysis pass"
```

---

### Task 2: Real App Notify Uses Single Bundle

**Files:**
- Modify: `copilot/api/real_app.py`
- Create: `tests/test_real_app_single_pass_notify.py`

- [ ] **Step 1: Write failing test with fake service subclass**

Create `tests/test_real_app_single_pass_notify.py`:

```python
from copilot.api.app import NotifyResult
from copilot.api.real_app import RealReportService
from copilot.models import Finding, Severity
from copilot.report.builder import CompanyCard
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureScanEvent, build_analysis_bundle
from copilot.service.analyzer import CompanyAnalysisResult


class FakeNotifier:
    def __init__(self):
        self.sent_text = None

    def send_text(self, text):
        self.sent_text = text
        return True


class FakeAnalyzer:
    def __init__(self):
        self.bundle_calls = 0

    def analyze_disclosure_day_bundle(self, date):
        self.bundle_calls += 1
        card = CompanyCard(
            ts_code="603026.SH",
            period="20250630",
            fact_line="fact",
            findings=[Finding(rule_id="x", severity=Severity.RED, title="异常", detail="证据", evidence=[], score=99.0)],
            max_severity=Severity.RED,
            max_score=99.0,
        )
        return build_analysis_bundle(
            date=date,
            coverage_count=1,
            results=[("603026.SH", "20250630", "generic", CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=card))],
        )


class FakeSettings:
    class Notify:
        feishu_webhook = "https://example.test/webhook"

    class Eval:
        company_names = {"603026.SH": "石大胜华"}
        coverage_pool = ["603026.SH"]
        start_date = "20250801"
        end_date = "20250831"

    notify = Notify()
    eval = Eval()


class BundleNotifyService(RealReportService):
    def __init__(self):
        self.settings = FakeSettings()
        self.analyzer = FakeAnalyzer()
        self.notifier = FakeNotifier()
        self.cache = None

    def _send_feishu_text(self, text):
        return self.notifier.send_text(text)


def test_notify_feishu_uses_one_bundle_call():
    service = BundleNotifyService()

    result = service.notify_feishu_disclosure_day("20250825")

    assert result == NotifyResult(sent=True, reason="ok")
    assert service.analyzer.bundle_calls == 1
    assert "603026.SH 石大胜华" in service.notifier.sent_text
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_real_app_single_pass_notify.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `notify_feishu_disclosure_day()` does not use `analyze_disclosure_day_bundle()` and `_send_feishu_text()` does not exist.

- [ ] **Step 3: Implement send wrapper and bundle notify path**

Modify `copilot/api/real_app.py`:

```python
    def _send_feishu_text(self, text):
        webhook = self.settings.notify.feishu_webhook
        if not webhook:
            return False
        return FeishuNotifier(webhook).send_text(text)
```

Modify `analyze_disclosure_day()`:

```python
    def analyze_disclosure_day(self, date):
        if self.analyzer is None:
            raise HTTPException(status_code=503, detail="未配置 TUSHARE_TOKEN")
        bundle = self.analyzer.analyze_disclosure_day_bundle(date)
        for card in bundle.summary.cards:
            self.cache.put_company(card)
        self.cache.put_daily(bundle.summary)
        return bundle.summary
```

Modify `scan_disclosure_day()`:

```python
    def scan_disclosure_day(self, date):
        if self.analyzer is None:
            raise HTTPException(status_code=503, detail="未配置 TUSHARE_TOKEN")
        return self.analyzer.analyze_disclosure_day_bundle(date).scan
```

Modify `notify_feishu_disclosure_day()`:

```python
    def notify_feishu_disclosure_day(self, date):
        if self.analyzer is None:
            raise HTTPException(status_code=503, detail="未配置 TUSHARE_TOKEN")
        bundle = self.analyzer.analyze_disclosure_day_bundle(date)
        for card in bundle.summary.cards:
            self.cache.put_company(card)
        self.cache.put_daily(bundle.summary)
        if bundle.summary.disclosed_count == 0 and bundle.scan.disclosed_count == 0:
            return NotifyResult(sent=False, reason="no_disclosures")
        if not self.settings.notify.feishu_webhook:
            return NotifyResult(sent=False, reason="webhook_not_configured")
        text = render_formal_disclosure_text(bundle.summary, bundle.scan, self.settings.eval.company_names)
        sent = self._send_feishu_text(text)
        return NotifyResult(sent=sent, reason="ok" if sent else "send_failed")
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_real_app_single_pass_notify.py tests/test_real_app_notify.py tests/test_real_app_startup.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

Run:

```bash
python -m pytest -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add copilot/api/real_app.py tests/test_real_app_single_pass_notify.py
git commit -m "perf: reuse disclosure analysis for Feishu notify"
```

---

### Task 3: Feishu Full-Abnormal Delivery Segmentation

**Files:**
- Modify: `copilot/notify/feishu.py`
- Create: `tests/test_feishu_delivery_segments.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_feishu_delivery_segments.py`:

```python
from copilot.notify.feishu import split_feishu_text


def test_split_feishu_text_keeps_short_message_single_part():
    assert split_feishu_text("short", max_chars=20) == ["short"]


def test_split_feishu_text_splits_on_line_boundaries_with_part_headers():
    text = "title\n" + "\n".join(f"line-{index}" for index in range(1, 8))

    parts = split_feishu_text(text, max_chars=40)

    assert len(parts) > 1
    assert all(len(part) <= 40 for part in parts)
    assert parts[0].startswith("[1/")
    assert "line-1" in parts[0]
    assert "line-7" in parts[-1]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_feishu_delivery_segments.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `split_feishu_text` does not exist.

- [ ] **Step 3: Implement segmentation helper**

Modify `copilot/notify/feishu.py`:

```python
def split_feishu_text(text: str, max_chars: int = 3500) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[list[str]] = [[]]
    current_len = 0
    for line in text.splitlines():
        line_len = len(line) + 1
        if chunks[-1] and current_len + line_len > max_chars - 12:
            chunks.append([])
            current_len = 0
        chunks[-1].append(line)
        current_len += line_len
    total = len(chunks)
    return [f"[{index}/{total}]\n" + "\n".join(lines) for index, lines in enumerate(chunks, start=1)]
```

- [ ] **Step 4: Add notifier send-many helper test**

Append to `tests/test_feishu_delivery_segments.py`:

```python
from copilot.notify.feishu import FeishuNotifier


class FakeHttpClient:
    def __init__(self):
        self.payloads = []

    def post(self, url, json):
        self.payloads.append(json)
        return FakeResponse()


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"StatusCode": 0}


def test_send_text_parts_sends_every_part():
    client = FakeHttpClient()
    notifier = FeishuNotifier("https://example.test/webhook", http_client=client)

    sent = notifier.send_text_parts(["one", "two"])

    assert sent is True
    assert [payload["content"]["text"] for payload in client.payloads] == ["one", "two"]
```

- [ ] **Step 5: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_feishu_delivery_segments.py::test_send_text_parts_sends_every_part -q --basetemp=.pytest_tmp
```

Expected: FAIL because `send_text_parts` does not exist.

- [ ] **Step 6: Implement send_text_parts**

Modify `FeishuNotifier` in `copilot/notify/feishu.py`:

```python
    def send_text_parts(self, parts: list[str]) -> bool:
        return all(self.send_text(part) for part in parts)
```

- [ ] **Step 7: Run tests**

Run:

```bash
python -m pytest tests/test_feishu_delivery_segments.py tests/test_feishu_formal_summary.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add copilot/notify/feishu.py tests/test_feishu_delivery_segments.py
git commit -m "feat: split long Feishu disclosure text"
```

---

### Task 4: Watchlist Replacement Loader

**Files:**
- Create: `copilot/watchlist.py`
- Create: `tests/test_watchlist_loader.py`
- Modify: `docs/development-log.md`

- [ ] **Step 1: Write failing tests**

Create `tests/test_watchlist_loader.py`:

```python
from copilot.watchlist import load_watchlist_yaml


def test_load_watchlist_yaml_reads_codes_names_and_industries(tmp_path):
    path = tmp_path / "watchlist.yaml"
    path.write_text(
        """
coverage_pool:
  - 000001.SZ
  - 603026.SH
company_names:
  000001.SZ: 平安银行
  603026.SH: 石大胜华
company_industries:
  000001.SZ: bank
  603026.SH: generic
""".strip(),
        encoding="utf-8",
    )

    watchlist = load_watchlist_yaml(path)

    assert watchlist.coverage_pool == ["000001.SZ", "603026.SH"]
    assert watchlist.company_names == {"000001.SZ": "平安银行", "603026.SH": "石大胜华"}
    assert watchlist.company_industries == {"000001.SZ": "bank", "603026.SH": "generic"}


def test_load_watchlist_yaml_requires_every_code_to_have_name_and_industry(tmp_path):
    path = tmp_path / "watchlist.yaml"
    path.write_text(
        """
coverage_pool:
  - 000001.SZ
company_names: {}
company_industries: {}
""".strip(),
        encoding="utf-8",
    )

    try:
        load_watchlist_yaml(path)
    except ValueError as exc:
        assert "000001.SZ" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_watchlist_loader.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `copilot.watchlist` does not exist.

- [ ] **Step 3: Implement watchlist loader**

Create `copilot/watchlist.py`:

```python
from pathlib import Path

from pydantic import BaseModel, Field
import yaml


class Watchlist(BaseModel):
    coverage_pool: list[str] = Field(default_factory=list)
    company_names: dict[str, str] = Field(default_factory=dict)
    company_industries: dict[str, str] = Field(default_factory=dict)


def load_watchlist_yaml(path: str | Path) -> Watchlist:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    watchlist = Watchlist.model_validate(data)
    missing = [
        code
        for code in watchlist.coverage_pool
        if code not in watchlist.company_names or code not in watchlist.company_industries
    ]
    if missing:
        raise ValueError(f"watchlist missing name or industry for: {', '.join(missing)}")
    return watchlist
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_watchlist_loader.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Record usage in development log**

Append to `docs/development-log.md` under backend remaining work:

```markdown
### Watchlist replacement path

The current 100-stock pool is a smoke pool. The production replacement path should use a YAML watchlist with:

```yaml
coverage_pool:
  - 000001.SZ
company_names:
  000001.SZ: 平安银行
company_industries:
  000001.SZ: bank
```

The backend loader validates that every code has both a display name and an industry route before replacing the smoke pool.
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
python -m pytest tests/test_watchlist_loader.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

Commit:

```bash
git add copilot/watchlist.py tests/test_watchlist_loader.py docs/development-log.md
git commit -m "feat: validate coverage watchlist files"
```

---

### Task 5: Backend Job Runner for Manual/Scheduled Disclosure Sends

**Files:**
- Create: `copilot/scheduler.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_scheduler.py`:

```python
from copilot.scheduler import DisclosureSendJob, run_disclosure_send_job


class FakeReportService:
    def __init__(self):
        self.sent_dates = []

    def notify_feishu_disclosure_day(self, date):
        self.sent_dates.append(date)
        return {"sent": True, "reason": "ok"}


def test_run_disclosure_send_job_calls_notify_once():
    service = FakeReportService()
    job = DisclosureSendJob(date="20250825")

    result = run_disclosure_send_job(job, service)

    assert service.sent_dates == ["20250825"]
    assert result.sent is True
    assert result.reason == "ok"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_scheduler.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `copilot.scheduler` does not exist.

- [ ] **Step 3: Implement backend job runner**

Create `copilot/scheduler.py`:

```python
from pydantic import BaseModel

from copilot.api.app import NotifyResult


class DisclosureSendJob(BaseModel):
    date: str


def run_disclosure_send_job(job: DisclosureSendJob, report_service) -> NotifyResult:
    result = report_service.notify_feishu_disclosure_day(job.date)
    if isinstance(result, NotifyResult):
        return result
    return NotifyResult.model_validate(result)
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_scheduler.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/scheduler.py tests/test_scheduler.py
git commit -m "feat: add disclosure send job runner"
```

---

### Task 6: Observability for Tushare Workload and Runtime

**Files:**
- Create: `copilot/observability.py`
- Create: `tests/test_observability.py`
- Modify: `copilot/service/disclosure_scan.py`
- Modify: `copilot/service/analyzer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_observability.py`:

```python
from copilot.observability import RuntimeStats


def test_runtime_stats_records_company_and_snapshot_counts():
    stats = RuntimeStats()
    stats.record_company()
    stats.record_snapshot_fetch()
    stats.record_snapshot_fetch()

    assert stats.company_count == 1
    assert stats.snapshot_fetch_count == 2
    assert stats.as_lines() == ["companies=1", "snapshot_fetches=2"]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_observability.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `copilot.observability` does not exist.

- [ ] **Step 3: Implement runtime stats**

Create `copilot/observability.py`:

```python
from pydantic import BaseModel


class RuntimeStats(BaseModel):
    company_count: int = 0
    snapshot_fetch_count: int = 0

    def record_company(self) -> None:
        self.company_count += 1

    def record_snapshot_fetch(self) -> None:
        self.snapshot_fetch_count += 1

    def as_lines(self) -> list[str]:
        return [f"companies={self.company_count}", f"snapshot_fetches={self.snapshot_fetch_count}"]
```

- [ ] **Step 4: Run test**

Run:

```bash
python -m pytest tests/test_observability.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Decide integration point**

Add `RuntimeStats | None = None` to `AnalyzerService.__init__`, defaulting to `None`. In `_fetch_and_store()`, call `self.runtime_stats.record_snapshot_fetch()` when present. In `analyze_company()`, call `self.runtime_stats.record_company()` once at the start when present.

Exact implementation in `copilot/service/analyzer.py`:

```python
from copilot.observability import RuntimeStats
```

```python
        runtime_stats: RuntimeStats | None = None,
```

```python
        self.runtime_stats = runtime_stats
```

```python
        if self.runtime_stats is not None:
            self.runtime_stats.record_snapshot_fetch()
```

```python
        if self.runtime_stats is not None:
            self.runtime_stats.record_company()
```

- [ ] **Step 6: Add integration test**

Append to `tests/test_observability.py`:

```python
from copilot.models import PeriodSnapshot
from copilot.observability import RuntimeStats
from copilot.service.analyzer import AnalyzerService


class StatsFundamentals:
    def fetch_snapshot(self, ts_code, period):
        return PeriodSnapshot(
            ts_code=ts_code,
            period=period,
            revenue=100.0,
            net_profit=10.0,
            deducted_net_profit=9.0,
            gross_margin_pct=30.0,
            operating_cash_flow=8.0,
            accounts_receivable=20.0,
            inventory=15.0,
        )


class StatsStore:
    def __init__(self):
        self.snapshots = {}

    def upsert_snapshot(self, snapshot):
        self.snapshots[(snapshot.ts_code, snapshot.period)] = snapshot

    def get_snapshot(self, ts_code, period):
        return self.snapshots.get((ts_code, period))

    def replace_findings(self, ts_code, period, findings):
        pass


def test_analyzer_records_runtime_stats():
    stats = RuntimeStats()
    service = AnalyzerService(fundamentals=StatsFundamentals(), store=StatsStore(), runtime_stats=stats)

    service.analyze_company("603026.SH", "20250630")

    assert stats.company_count == 1
    assert stats.snapshot_fetch_count == 3
```

- [ ] **Step 7: Run tests**

Run:

```bash
python -m pytest tests/test_observability.py tests/test_analyzer_service.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add copilot/observability.py copilot/service/analyzer.py tests/test_observability.py
git commit -m "feat: record disclosure analysis runtime stats"
```

---

### Task 7: Industry Rule Pack Selection From Real Failures

**Files:**
- Modify: `copilot/rules/registry.py`
- Modify: `copilot/checks/reconcile.py`
- Possible create: `copilot/rules/bank.py`
- Test: `tests/test_bank_rules.py`

- [ ] **Step 1: Use latest scan output to choose one industry group**

Use `DisclosureScanResult` from the formal pool and choose the largest non-generic or most economically important failing group. With current smoke pool, there are no data problems and no bank names in the 100-stock set, so do not implement speculative securities/insurance/real-estate/utilities packs from this smoke pool.

- [ ] **Step 2: Preserve current bank hard-check regression**

Run:

```bash
python -m pytest tests/test_bank_rules.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 3: Record industry-rule block if no concrete field set exists**

If the latest scan still has no bank/securities/insurance/real-estate/utilities failures with known Tushare fields, append this exact note to `docs/development-log.md`:

```markdown
### Industry rule pack gate

The current smoke pool does not provide enough concrete industry-specific failure samples to implement another rule pack safely. Do not add securities, insurance, real-estate, utilities, or true bank metric rules until a real sample identifies the exact Tushare fields and expected finding logic.
```

- [ ] **Step 4: Run tests and commit the gate note if added**

Run:

```bash
python -m pytest tests/test_bank_rules.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

If the gate note was added, commit it:

```bash
git add docs/development-log.md
git commit -m "docs: record industry rule gate"
```

Do not modify `copilot/rules/registry.py`, `copilot/checks/reconcile.py`, or `copilot/rules/bank.py` in this task unless real fields and failing tests are available.

---

### Task 8: Real Backtest and Manual Review Precision Scaffold

**Files:**
- Create: `copilot/eval/real_backtest.py`
- Create: `tests/test_real_backtest.py`
- Modify: `docs/development-log.md`

- [ ] **Step 1: Write failing aggregation test**

Create `tests/test_real_backtest.py`:

```python
from copilot.eval.real_backtest import summarize_scan_counts
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureScanEvent, build_scan_result


def test_summarize_scan_counts_aggregates_multiple_days():
    day1 = build_scan_result(
        date="20250825",
        coverage_count=2,
        events=[
            DisclosureScanEvent(ts_code="603026.SH", period="20250630", status=CompanyAnalysisStatus.OK, message="ok", has_card=True, industry="generic"),
            DisclosureScanEvent(ts_code="000001.SZ", period="20250630", status=CompanyAnalysisStatus.ERROR, message="timeout", has_card=False, industry="bank"),
        ],
    )
    day2 = build_scan_result(
        date="20250826",
        coverage_count=2,
        events=[
            DisclosureScanEvent(ts_code="600151.SH", period="20250630", status=CompanyAnalysisStatus.DATA_NOT_READY, message="missing", has_card=False, industry="generic"),
        ],
    )

    summary = summarize_scan_counts([day1, day2])

    assert summary == {
        "days": 2,
        "disclosed_count": 3,
        "ok_count": 1,
        "data_not_ready_count": 1,
        "data_incomplete_count": 0,
        "error_count": 1,
    }
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_real_backtest.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `copilot.eval.real_backtest` does not exist.

- [ ] **Step 3: Implement aggregation helper**

Create `copilot/eval/real_backtest.py`:

```python
def summarize_scan_counts(scans) -> dict[str, int]:
    return {
        "days": len(scans),
        "disclosed_count": sum(scan.disclosed_count for scan in scans),
        "ok_count": sum(scan.ok_count for scan in scans),
        "data_not_ready_count": sum(scan.data_not_ready_count for scan in scans),
        "data_incomplete_count": sum(scan.data_incomplete_count for scan in scans),
        "error_count": sum(scan.error_count for scan in scans),
    }
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_real_backtest.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/eval/real_backtest.py tests/test_real_backtest.py
git commit -m "feat: aggregate real disclosure scan backtests"
```

---

### Task 9: PDF/LLM Attribution Reconnection Plan Gate

**Files:**
- Modify: `docs/development-log.md`

- [ ] **Step 1: Record gate conditions**

Append to `docs/development-log.md`:

```markdown
### PDF / LLM attribution gate

Do not connect LLM attribution into real Feishu cards until these gate conditions are met:

- Stable source PDF retrieval for the exact report announcement.
- Deterministic extraction of management discussion text.
- Token/latency budget measured on at least 20 real cards.
- Attribution text remains evidence-linked and never replaces arithmetic rule findings.
- If LLM call fails, card still sends with rule evidence.
```

- [ ] **Step 2: Run tests**

Run:

```bash
python -m pytest -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add docs/development-log.md
git commit -m "docs: define LLM attribution readiness gate"
```

---

## Suggested Execution Order

1. Task 1 — single-pass bundle.
2. Task 2 — real app notify uses bundle.
3. Task 3 — Feishu segmentation while still sending all abnormalities.
4. Task 6 — observability for runtime/call counts.
5. Task 4 — watchlist loader.
6. Task 5 — backend job runner.
7. Task 8 — real backtest aggregation.
8. Task 7 — only when real industry failures and fields exist.
9. Task 9 — documentation gate for PDF/LLM attribution.

---

## Definition of Done

- No frontend files are modified while executing this plan.
- `python -m pytest -q --basetemp=.pytest_tmp` passes after every implementation batch.
- Formal Feishu notify runs through one disclosure-day analysis pass, not separate summary and scan sweeps.
- Feishu delivery preserves the product requirement that all red/yellow abnormalities are sent; segmentation is allowed when one text is too long.
- Runtime stats make Tushare workload visible in tests and logs.
- Smoke 100-stock pool remains replaceable by a validated watchlist path.
- No speculative industry rules are added without real data fields and failing tests.
- Development log records what changed and what remains blocked.
- No tokens, webhooks, or secrets are printed or committed.

## Self-Review Notes

Spec coverage: This plan covers non-frontend remaining work only: performance, formal Feishu delivery, watchlist replacement, automation/job runner, industry rules, real backtest, observability, and PDF/LLM readiness gating. It excludes frontend work as requested. Completeness scan: Most tasks include concrete tests, implementation snippets, commands, and commits. The only intentional stop point is Task 7, where speculative industry rules are explicitly forbidden until real fields are identified; the plan gives a concrete stop action instead of fake implementation. Type consistency: `DisclosureAnalysisBundle`, `build_analysis_bundle`, `analyze_disclosure_day_bundle`, `split_feishu_text`, `send_text_parts`, `Watchlist`, `DisclosureSendJob`, and `RuntimeStats` are named consistently across tests and implementation steps.
