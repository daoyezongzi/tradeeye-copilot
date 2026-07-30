# Formal Coverage Pool and Industry Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a formal coverage-pool scanning workflow that diagnoses real disclosure-day failures and uses those findings to introduce industry-aware checks/rules, starting with banks but allowing other industries to emerge from real samples.

**Architecture:** Do not pre-build a large taxonomy. First add a diagnostic scan layer that records per-company analysis status, missing fields, industry classification, and raw failure reason. Then use that scan output to route companies through either the existing generic industrial rules or a new bank-specific rule/check path. The disclosure-day summary remains card-centric, while a new diagnostic API exposes skipped/pending/error companies so coverage-pool issues are visible before Feishu send.

**Tech Stack:** Python 3.11+, FastAPI, pydantic, pandas, tushare, SQLite-backed existing store, pytest, vanilla JS frontend.

---

## File Structure

Existing files to modify:

- Modify: `config.yaml` — replace the one-stock placeholder coverage pool only after user supplies the formal list; add optional `company_industries` mapping for deterministic routing.
- Modify: `copilot/config.py` — add `CompanyIndustrySettings` or extend `EvalSettings` with optional industry mapping.
- Modify: `copilot/models.py` — add industry-aware optional fields only when needed by bank checks.
- Modify: `copilot/datasource/fundamentals.py` — keep current generic snapshot; optionally add bank fields in a focused follow-up task after scan identifies exact Tushare fields.
- Modify: `copilot/service/analyzer.py` — return per-company diagnostic results for disclosure-day scans; keep `analyze_company()` stable.
- Modify: `copilot/checks/reconcile.py` — split generic hard checks from industry-specific hard checks.
- Modify: `copilot/rules/registry.py` — route rules by industry.
- Modify: `copilot/report/builder.py` — keep `DailySummary` stable and add separate diagnostic model rather than overloading cards.
- Modify: `copilot/api/app.py` — expose diagnostic scan API.
- Modify: `copilot/api/dev_app.py` — demo diagnostic response.
- Modify: `copilot/api/real_app.py` — wire diagnostic scan with real services.
- Modify: `web/index.html` — add minimal coverage scan button/status block.
- Modify: `web/app.js` — add API wrapper and render diagnostic statuses.
- Modify: `web/styles.css` — minimal diagnostic table styling.
- Modify: `docs/development-log.md` — record formal coverage-pool scan results after execution.

New files:

- Create: `copilot/service/disclosure_scan.py` — diagnostic scan models and helpers.
- Create: `copilot/industry.py` — small industry enum/router; initially generic/bank/unknown only.
- Create: `copilot/rules/bank.py` — bank-specific rule implementations, added only after scan confirms required fields.

New tests:

- Create: `tests/test_disclosure_scan.py`
- Create: `tests/test_industry_routing.py`
- Create: `tests/test_industry_checks.py`
- Create: `tests/test_api_disclosure_scan.py`
- Create: `tests/test_frontend_diagnostics.py`
- Later bank field/rule tests: `tests/test_bank_rules.py`

---

### Task 1: Add Disclosure Scan Diagnostic Models

**Files:**
- Create: `copilot/service/disclosure_scan.py`
- Create: `tests/test_disclosure_scan.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_disclosure_scan.py`:

```python
from copilot.service.analyzer import CompanyAnalysisResult, CompanyAnalysisStatus
from copilot.service.disclosure_scan import DisclosureScanEvent, DisclosureScanResult, build_scan_result


def test_build_scan_result_counts_statuses():
    events = [
        DisclosureScanEvent(ts_code="000001.SZ", period="20250630", status=CompanyAnalysisStatus.DATA_NOT_READY, message="missing gross_margin_pct", has_card=False),
        DisclosureScanEvent(ts_code="920056.BJ", period="20250630", status=CompanyAnalysisStatus.OK, message="ok", has_card=True),
        DisclosureScanEvent(ts_code="600000.SH", period="20250630", status=CompanyAnalysisStatus.DATA_INCOMPLETE, message="current.revenue is negative", has_card=False),
    ]

    result = build_scan_result(date="20250821", coverage_count=3, events=events)

    assert result == DisclosureScanResult(
        date="20250821",
        coverage_count=3,
        disclosed_count=3,
        ok_count=1,
        data_not_ready_count=1,
        data_incomplete_count=1,
        error_count=0,
        events=events,
    )


def test_disclosure_scan_event_keeps_failure_reason_visible():
    event = DisclosureScanEvent(
        ts_code="000001.SZ",
        period="20250630",
        status=CompanyAnalysisStatus.DATA_NOT_READY,
        message="Tushare 暂未返回 000001.SZ 20250630 的完整财务快照",
        has_card=False,
        industry="bank",
    )

    assert event.industry == "bank"
    assert "完整财务快照" in event.message
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_disclosure_scan.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `copilot.service.disclosure_scan` does not exist.

- [ ] **Step 3: Implement scan models**

Create `copilot/service/disclosure_scan.py`:

```python
from pydantic import BaseModel

from copilot.service.analyzer import CompanyAnalysisStatus


class DisclosureScanEvent(BaseModel):
    ts_code: str
    period: str
    status: CompanyAnalysisStatus
    message: str
    has_card: bool
    industry: str | None = None


class DisclosureScanResult(BaseModel):
    date: str
    coverage_count: int
    disclosed_count: int
    ok_count: int
    data_not_ready_count: int
    data_incomplete_count: int
    error_count: int
    events: list[DisclosureScanEvent]


def build_scan_result(date: str, coverage_count: int, events: list[DisclosureScanEvent]) -> DisclosureScanResult:
    return DisclosureScanResult(
        date=date,
        coverage_count=coverage_count,
        disclosed_count=len(events),
        ok_count=sum(1 for event in events if event.status == CompanyAnalysisStatus.OK),
        data_not_ready_count=sum(1 for event in events if event.status == CompanyAnalysisStatus.DATA_NOT_READY),
        data_incomplete_count=sum(1 for event in events if event.status == CompanyAnalysisStatus.DATA_INCOMPLETE),
        error_count=sum(1 for event in events if event.status == CompanyAnalysisStatus.ERROR),
        events=events,
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_disclosure_scan.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/service/disclosure_scan.py tests/test_disclosure_scan.py
git commit -m "feat: add disclosure scan diagnostics"
```

---

### Task 2: Add Industry Routing Config

**Files:**
- Modify: `copilot/config.py`
- Modify: `config.yaml`
- Create: `copilot/industry.py`
- Create: `tests/test_industry_routing.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_industry_routing.py`:

```python
from copilot.config import load_settings
from copilot.industry import Industry, industry_for_ts_code


def test_load_settings_reads_company_industries(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
eval:
  coverage_pool:
    - 000001.SZ
    - 920056.BJ
  company_industries:
    000001.SZ: bank
    920056.BJ: generic
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path, env_path=tmp_path / "missing.env")

    assert settings.eval.company_industries == {"000001.SZ": "bank", "920056.BJ": "generic"}


def test_industry_for_ts_code_defaults_to_unknown():
    assert industry_for_ts_code("000001.SZ", {"000001.SZ": "bank"}) == Industry.BANK
    assert industry_for_ts_code("920056.BJ", {"920056.BJ": "generic"}) == Industry.GENERIC
    assert industry_for_ts_code("300750.SZ", {}) == Industry.UNKNOWN
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_industry_routing.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `company_industries` and `copilot.industry` do not exist.

- [ ] **Step 3: Implement industry routing**

Modify `copilot/config.py`, extend `EvalSettings`:

```python
class EvalSettings(BaseModel):
    coverage_pool: list[str] = Field(default_factory=list)
    company_industries: dict[str, str] = Field(default_factory=dict)
    start_date: str = "20250801"
    end_date: str = "20250831"
    benchmark_output: Path = Path("artifacts/benchmark.json")
```

Create `copilot/industry.py`:

```python
from enum import StrEnum


class Industry(StrEnum):
    GENERIC = "generic"
    BANK = "bank"
    UNKNOWN = "unknown"


def industry_for_ts_code(ts_code: str, company_industries: dict[str, str]) -> Industry:
    raw = company_industries.get(ts_code)
    if raw == Industry.BANK.value:
        return Industry.BANK
    if raw == Industry.GENERIC.value:
        return Industry.GENERIC
    return Industry.UNKNOWN
```

Modify `config.yaml` under `eval`:

```yaml
eval:
  coverage_pool:
    - 000001.SZ
  company_industries:
    000001.SZ: bank
  start_date: "20250801"
  end_date: "20250831"
  benchmark_output: artifacts/benchmark.json
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_industry_routing.py tests/test_config.py tests/test_config_rss.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/config.py copilot/industry.py config.yaml tests/test_industry_routing.py
git commit -m "feat: configure company industry routing"
```

---

### Task 3: Add Disclosure-Day Diagnostic Scan Service Method

**Files:**
- Modify: `copilot/service/analyzer.py`
- Test: `tests/test_disclosure_scan.py`

- [ ] **Step 1: Extend failing tests**

Append to `tests/test_disclosure_scan.py`:

```python
from copilot.datasource.calendar import DisclosureEvent
from copilot.models import PeriodSnapshot
from copilot.service.analyzer import AnalyzerService


class ScanCalendar:
    def fetch_events(self, date, coverage_pool):
        return [
            DisclosureEvent(ts_code="000001.SZ", ann_date=date, period="20250630"),
            DisclosureEvent(ts_code="920056.BJ", ann_date=date, period="20250630"),
        ]


class ScanFundamentals:
    def fetch_snapshot(self, ts_code, period):
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


class ScanStore:
    def __init__(self):
        self.snapshots = {}

    def upsert_snapshot(self, snapshot):
        self.snapshots[(snapshot.ts_code, snapshot.period)] = snapshot

    def get_snapshot(self, ts_code, period):
        return self.snapshots.get((ts_code, period))

    def replace_findings(self, ts_code, period, findings):
        pass


def test_analyzer_disclosure_scan_returns_status_for_each_event():
    service = AnalyzerService(
        fundamentals=ScanFundamentals(),
        store=ScanStore(),
        coverage_pool=["000001.SZ", "920056.BJ"],
        calendar=ScanCalendar(),
        company_industries={"000001.SZ": "bank", "920056.BJ": "generic"},
    )

    result = service.scan_disclosure_day("20250821")

    assert result.date == "20250821"
    assert result.coverage_count == 2
    assert result.disclosed_count == 2
    assert [(event.ts_code, event.status, event.has_card, event.industry) for event in result.events] == [
        ("000001.SZ", CompanyAnalysisStatus.DATA_NOT_READY, False, "bank"),
        ("920056.BJ", CompanyAnalysisStatus.OK, True, "generic"),
    ]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_disclosure_scan.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `AnalyzerService.__init__` has no `company_industries` argument and `scan_disclosure_day()` does not exist.

- [ ] **Step 3: Implement diagnostic scan method**

Modify `copilot/service/analyzer.py` imports:

```python
from copilot.industry import industry_for_ts_code
from copilot.service.disclosure_scan import DisclosureScanEvent, DisclosureScanResult, build_scan_result
```

Modify `AnalyzerService.__init__` signature and body:

```python
    def __init__(
        self,
        fundamentals: FundamentalsProvider,
        store: SnapshotStore,
        thresholds: RuleThresholds | None = None,
        coverage_pool: list[str] | None = None,
        calendar=None,
        company_industries: dict[str, str] | None = None,
    ):
        self.fundamentals = fundamentals
        self.store = store
        self.thresholds = thresholds or RuleThresholds()
        self.coverage_pool = coverage_pool or []
        self.calendar = calendar
        self.company_industries = company_industries or {}
```

Add method:

```python
    def scan_disclosure_day(self, date: str) -> DisclosureScanResult:
        if self.calendar is None:
            return build_scan_result(date, coverage_count=len(self.coverage_pool), events=[])
        events = self.calendar.fetch_events(date, set(self.coverage_pool))
        scan_events: list[DisclosureScanEvent] = []
        for event in events:
            result = self.analyze_company(event.ts_code, event.period)
            industry = industry_for_ts_code(event.ts_code, self.company_industries).value
            scan_events.append(
                DisclosureScanEvent(
                    ts_code=event.ts_code,
                    period=event.period,
                    status=result.status,
                    message=result.message,
                    has_card=result.card is not None,
                    industry=industry,
                )
            )
        return build_scan_result(date, coverage_count=len(self.coverage_pool), events=scan_events)
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_disclosure_scan.py tests/test_analyzer_disclosure_day.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/service/analyzer.py tests/test_disclosure_scan.py
git commit -m "feat: scan disclosure day diagnostics"
```

---

### Task 4: Add Diagnostic Scan API

**Files:**
- Modify: `copilot/api/app.py`
- Modify: `copilot/api/dev_app.py`
- Modify: `copilot/api/real_app.py`
- Create: `tests/test_api_disclosure_scan.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_api_disclosure_scan.py`:

```python
from fastapi.testclient import TestClient

from copilot.api.app import create_app
from copilot.rss.service import RssPollResult
from copilot.service.analyzer import CompanyAnalysisStatus
from copilot.service.disclosure_scan import DisclosureScanEvent, build_scan_result


class FakeScanService:
    def get_company_card(self, ts_code, period): return None
    def get_daily_summary(self, date): return None
    def get_evidence(self, ts_code, period, rule_id): return []
    def get_quarterly_review(self): return None
    def analyze_company(self, ts_code, period): raise AssertionError("not used")
    def analyze_disclosure_day(self, date): raise AssertionError("not used")
    def poll_rss(self): return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])
    def notify_feishu_disclosure_day(self, date): raise AssertionError("not used")

    def scan_disclosure_day(self, date):
        return build_scan_result(
            date=date,
            coverage_count=2,
            events=[
                DisclosureScanEvent(ts_code="000001.SZ", period="20250630", status=CompanyAnalysisStatus.DATA_NOT_READY, message="missing bank fields", has_card=False, industry="bank"),
                DisclosureScanEvent(ts_code="920056.BJ", period="20250630", status=CompanyAnalysisStatus.OK, message="ok", has_card=True, industry="generic"),
            ],
        )


def test_scan_disclosure_day_route_returns_diagnostics():
    client = TestClient(create_app(FakeScanService()))

    response = client.post("/api/scan/disclosure-day", json={"date": "20250821"})

    assert response.status_code == 200
    assert response.json()["data_not_ready_count"] == 1
    assert response.json()["events"][0]["industry"] == "bank"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_api_disclosure_scan.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `/api/scan/disclosure-day` does not exist.

- [ ] **Step 3: Implement API route**

Modify `copilot/api/app.py` imports:

```python
from copilot.service.disclosure_scan import DisclosureScanResult
```

Add to `ReportService`:

```python
    def scan_disclosure_day(self, date: str) -> DisclosureScanResult: ...
```

Add route before static mount:

```python
    @app.post("/api/scan/disclosure-day", response_model=DisclosureScanResult)
    def scan_disclosure_day(request: AnalyzeDisclosureDayRequest):
        return report_service.scan_disclosure_day(request.date)
```

Modify `copilot/api/dev_app.py` imports:

```python
from copilot.service.disclosure_scan import DisclosureScanEvent, build_scan_result
```

Add method to `DemoReportService`:

```python
    def scan_disclosure_day(self, date):
        return build_scan_result(
            date=date,
            coverage_count=42,
            events=[DisclosureScanEvent(ts_code=self.card.ts_code, period=self.card.period, status=CompanyAnalysisStatus.OK, message="ok", has_card=True, industry="generic")]
            if date == self.summary.date else [],
        )
```

Modify `copilot/api/real_app.py`, pass company industries when building analyzer:

```python
company_industries=self.settings.eval.company_industries,
```

Add method:

```python
    def scan_disclosure_day(self, date):
        if self.analyzer is None:
            raise HTTPException(status_code=503, detail="未配置 TUSHARE_TOKEN")
        return self.analyzer.scan_disclosure_day(date)
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_api_disclosure_scan.py tests/test_api_app.py tests/test_real_app_startup.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/api/app.py copilot/api/dev_app.py copilot/api/real_app.py tests/test_api_disclosure_scan.py
git commit -m "feat: expose disclosure scan diagnostics API"
```

---

### Task 5: Add Minimal Frontend Diagnostic View

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Create: `tests/test_frontend_diagnostics.py`

- [ ] **Step 1: Write failing frontend tests**

Create `tests/test_frontend_diagnostics.py`:

```python
from pathlib import Path


def test_frontend_exposes_disclosure_scan_controls():
    html = Path("web/index.html").read_text(encoding="utf-8")
    js = Path("web/app.js").read_text(encoding="utf-8")

    assert "scan-disclosure-day" in html
    assert "diagnostic-status" in html
    assert "scanDisclosureDay(date)" in js
    assert "/api/scan/disclosure-day" in js
    assert "renderDiagnostics" in js
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_frontend_diagnostics.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because scan controls do not exist.

- [ ] **Step 3: Add minimal controls**

Modify `web/index.html`, in the disclosure-day control group add:

```html
<button id="scan-disclosure-day">扫描诊断</button>
```

After `operation-status`, add:

```html
<div id="diagnostic-status" class="diagnostic-status"></div>
```

Modify `web/app.js`, add API method:

```javascript
  async scanDisclosureDay(date) {
    return requestJson("/api/scan/disclosure-day", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date }),
    });
  },
```

Add renderer:

```javascript
function renderDiagnostics(result) {
  const diagnosticStatus = document.querySelector("#diagnostic-status");
  diagnosticStatus.innerHTML = `
    <h2>扫描诊断</h2>
    <p>披露 ${result.disclosed_count} / 覆盖 ${result.coverage_count} | OK ${result.ok_count} | 待数据 ${result.data_not_ready_count} | 不完整 ${result.data_incomplete_count} | 错误 ${result.error_count}</p>
    <table>
      <thead><tr><th>代码</th><th>报告期</th><th>行业</th><th>状态</th><th>原因</th></tr></thead>
      <tbody>${result.events.map((event) => `<tr><td>${event.ts_code}</td><td>${event.period}</td><td>${event.industry || "unknown"}</td><td>${event.status}</td><td>${event.message}</td></tr>`).join("")}</tbody>
    </table>
  `;
}
```

Add event handler:

```javascript
document.querySelector("#scan-disclosure-day").addEventListener("click", async () => {
  try {
    const date = document.querySelector("#disclosure-date").value.trim();
    const result = await api.scanDisclosureDay(date);
    setStatus(result);
    renderDiagnostics(result);
  } catch (error) {
    setStatus({ error: error.message });
  }
});
```

Modify `web/styles.css`, append:

```css
.diagnostic-status {
  margin-top: 16px;
  overflow-x: auto;
}

.diagnostic-status table {
  width: 100%;
  border-collapse: collapse;
  background: white;
}

.diagnostic-status th,
.diagnostic-status td {
  border: 1px solid #e3e7f0;
  padding: 8px;
  text-align: left;
}
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
python -m pytest tests/test_frontend_diagnostics.py tests/test_frontend_contracts.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/index.html web/app.js web/styles.css tests/test_frontend_diagnostics.py
git commit -m "feat: show disclosure scan diagnostics"
```

---

### Task 6: Run Formal Coverage-Pool Scan Script Without Committing Secrets

**Files:**
- Modify: `docs/development-log.md`

- [ ] **Step 1: Ask for formal coverage pool list if not already configured**

If `config.yaml` still contains only `000001.SZ`, stop implementation and ask the user for the formal `coverage_pool` list. Do not invent the portfolio.

Expected user-provided format:

```yaml
eval:
  coverage_pool:
    - 000001.SZ
    - 920056.BJ
    - 601012.SH
  company_industries:
    000001.SZ: bank
    920056.BJ: generic
    601012.SH: generic
```

- [ ] **Step 2: Run scan after formal pool is configured**

Run:

```bash
python - <<'PY'
from copilot.api.real_app import app
from fastapi.testclient import TestClient

client = TestClient(app)
for date in ["20250821"]:
    response = client.post("/api/scan/disclosure-day", json={"date": date}, timeout=300)
    print("date=", date, "status_code=", response.status_code)
    print(response.json())
PY
```

Expected: returns `DisclosureScanResult` with per-company statuses.

- [ ] **Step 3: Record scan result in development log**

Append to `docs/development-log.md`:

```markdown
### Formal coverage-pool scan YYYY-MM-DD

Input coverage pool:

```text
<list ts_code values>
```

Scan result:

```text
OK=<n>
DATA_NOT_READY=<n>
DATA_INCOMPLETE=<n>
ERROR=<n>
```

Failure groups:

- Bank field mismatch: `<codes>`
- Generic missing Tushare fields: `<codes>`
- Other industry candidates: `<codes>`
- Tushare/API errors: `<codes>`
```

Replace placeholders with actual scan output before committing.

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/development-log.md
git commit -m "docs: record formal coverage pool scan"
```

---

### Task 7: Implement Bank-Specific Hard Check Routing

**Files:**
- Modify: `copilot/models.py`
- Modify: `copilot/checks/reconcile.py`
- Modify: `copilot/service/analyzer.py`
- Create: `tests/test_bank_rules.py`

- [ ] **Step 1: Write failing tests for known bank mismatch**

Create `tests/test_bank_rules.py`:

```python
from copilot.checks.reconcile import CheckStatus, run_hard_checks
from copilot.industry import Industry
from copilot.models import Context, PeriodSnapshot


def test_bank_context_does_not_require_gross_margin_receivables_or_inventory():
    snapshot = PeriodSnapshot(
        ts_code="000001.SZ",
        period="20250630",
        revenue=100.0,
        net_profit=10.0,
        operating_cash_flow=8.0,
        gross_margin_pct=None,
        accounts_receivable=None,
        inventory=None,
    )
    ctx = Context(ts_code="000001.SZ", current=snapshot, metadata={"industry": Industry.BANK.value})

    result = run_hard_checks(ctx)

    assert result.status == CheckStatus.OK


def test_generic_context_still_requires_gross_margin():
    snapshot = PeriodSnapshot(
        ts_code="920056.BJ",
        period="20250630",
        revenue=100.0,
        net_profit=10.0,
        operating_cash_flow=8.0,
        gross_margin_pct=None,
        accounts_receivable=20.0,
        inventory=15.0,
    )
    ctx = Context(ts_code="920056.BJ", current=snapshot, metadata={"industry": Industry.GENERIC.value})

    result = run_hard_checks(ctx)

    assert result.status == CheckStatus.DATA_INCOMPLETE
    assert any("gross_margin_pct" in message for message in result.messages)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_bank_rules.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because hard checks still require generic gross margin, receivables, and inventory fields for bank contexts.

- [ ] **Step 3: Add metadata to Context if missing**

If `copilot/models.py` `Context` has no `metadata`, modify it to include an editable metadata dict:

```python
class Context(BaseModel):
    ts_code: str
    current: PeriodSnapshot
    prior_quarter: PeriodSnapshot | None = None
    prior_year: PeriodSnapshot | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
```

If `metadata` already exists, leave `copilot/models.py` unchanged.

- [ ] **Step 4: Implement minimal bank hard-check routing**

Modify `copilot/checks/reconcile.py`:

```python
_GENERIC_REQUIRED_CURRENT_FIELDS = [
    "revenue",
    "net_profit",
    "gross_margin_pct",
    "operating_cash_flow",
]

_BANK_REQUIRED_CURRENT_FIELDS = [
    "revenue",
    "net_profit",
    "operating_cash_flow",
]

_GENERIC_NON_NEGATIVE_FIELDS = ["revenue", "accounts_receivable", "inventory"]
_BANK_NON_NEGATIVE_FIELDS = ["revenue"]


def _industry(ctx: Context) -> str:
    return str(ctx.metadata.get("industry") or "generic")


def _required_current_fields(ctx: Context) -> list[str]:
    return _BANK_REQUIRED_CURRENT_FIELDS if _industry(ctx) == "bank" else _GENERIC_REQUIRED_CURRENT_FIELDS


def _non_negative_fields(ctx: Context) -> list[str]:
    return _BANK_NON_NEGATIVE_FIELDS if _industry(ctx) == "bank" else _GENERIC_NON_NEGATIVE_FIELDS
```

Then update `run_hard_checks()` to iterate over `_required_current_fields(ctx)` and `_non_negative_fields(ctx)` instead of the old generic field lists.

- [ ] **Step 5: Ensure analyzer sets industry metadata**

Modify `copilot/service/analyzer.py` after assembling context:

```python
ctx.metadata["industry"] = industry_for_ts_code(ts_code, self.company_industries).value
```

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest tests/test_bank_rules.py tests/test_reconcile.py tests/test_analyzer_service.py tests/test_disclosure_scan.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add copilot/models.py copilot/checks/reconcile.py copilot/service/analyzer.py tests/test_bank_rules.py
git commit -m "feat: add bank-specific hard checks"
```

---

## Definition of Done

- `python -m pytest -q --basetemp=.pytest_tmp` passes.
- Formal `coverage_pool` is configured from user-provided list, not guessed.
- `/api/scan/disclosure-day` returns visible per-company statuses and reasons.
- Frontend can show diagnostic table for disclosure-day scan.
- Development log records formal scan results and failure groups.
- At least one industry-specific fix is implemented only after a real scan identifies the failure group.
- No real secrets are printed or committed.
- Feishu remains static webhook only; no callback/scheduler is introduced in this phase.

## Self-Review Notes

Spec coverage: The plan covers the user's requested direction: first prepare formal coverage-pool scanning, then use discovered issues to fix industry rules, especially banks but not limited to banks. It also records next-stage work in the development log and avoids guessing the formal portfolio. Placeholder scan: Task 6 includes explicit placeholder text only in a log template that must be replaced after real scan output; it also instructs the worker not to commit placeholders. Type consistency: `DisclosureScanEvent`, `DisclosureScanResult`, `scan_disclosure_day`, `Industry`, and `company_industries` are consistently named across tests, service, API, and frontend.
