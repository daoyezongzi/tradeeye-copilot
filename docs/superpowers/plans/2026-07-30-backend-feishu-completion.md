# Backend Feishu Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the backend-only final disclosure notification shape: formal Feishu text that includes all abnormal findings, visible data issues, company names, and a self-review report, without adding frontend work.

**Architecture:** Keep the existing analysis and scan APIs. Add a focused Feishu summary renderer that combines `DailySummary` cards with `DisclosureScanResult` diagnostics, groups all abnormal cards by severity, lists data-problem events, and summarizes normal companies. Real app notification should analyze and scan the date before sending so skipped/error companies are not invisible.

**Tech Stack:** Python 3.11+, FastAPI, pydantic, pytest, existing Tushare-backed services, Feishu webhook text sender.

---

## File Structure

Existing files to modify:

- Modify: `copilot/config.py` — add `eval.company_names` for optional display names.
- Modify: `config.yaml` — add `company_names` for the current 100-stock smoke pool only when names are fetched from Tushare.
- Modify: `copilot/notify/feishu.py` — add formal disclosure renderer and keep old renderer compatible.
- Modify: `copilot/api/real_app.py` — send formal summary from `DailySummary + DisclosureScanResult + company_names`.
- Modify: `copilot/api/dev_app.py` — support formal notify path in demo service.
- Modify: `docs/development-log.md` — record what remains after this phase.

New tests:

- Create: `tests/test_feishu_formal_summary.py`
- Create or modify: `tests/test_real_app_notify.py`

No frontend files should be changed in this plan.

---

### Task 1: Add Company Name Settings

**Files:**
- Modify: `copilot/config.py`
- Modify: `config.yaml`
- Test: `tests/test_industry_routing.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_industry_routing.py`:

```python

def test_load_settings_reads_company_names(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
eval:
  coverage_pool:
    - 603026.SH
  company_names:
    603026.SH: 石大胜华
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path, env_path=tmp_path / "missing.env")

    assert settings.eval.company_names == {"603026.SH": "石大胜华"}
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_industry_routing.py::test_load_settings_reads_company_names -q --basetemp=.pytest_tmp
```

Expected: FAIL because `EvalSettings` has no `company_names` field.

- [ ] **Step 3: Implement settings field**

Modify `copilot/config.py`:

```python
class EvalSettings(BaseModel):
    coverage_pool: list[str] = Field(default_factory=list)
    company_industries: dict[str, str] = Field(default_factory=dict)
    company_names: dict[str, str] = Field(default_factory=dict)
    start_date: str = "20250801"
    end_date: str = "20250831"
    benchmark_output: Path = Path("artifacts/benchmark.json")
```

- [ ] **Step 4: Populate config names for smoke pool**

Use Tushare `stock_basic(exchange="", list_status="L", fields="ts_code,name")` to fill `eval.company_names` for every code in `eval.coverage_pool`. Do not print token or webhook. Keep existing `coverage_pool` and `company_industries` unchanged.

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest tests/test_industry_routing.py tests/test_config.py tests/test_config_rss.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add copilot/config.py config.yaml tests/test_industry_routing.py
git commit -m "feat: configure coverage company names"
```

---

### Task 2: Formal Feishu Summary Renderer

**Files:**
- Modify: `copilot/notify/feishu.py`
- Create: `tests/test_feishu_formal_summary.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_feishu_formal_summary.py`:

```python
from copilot.models import Evidence, Finding, Severity
from copilot.notify.feishu import render_formal_disclosure_text
from copilot.report.builder import CompanyCard, DailySummary
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureScanEvent, build_scan_result


def finding(rule_id, severity, title, detail, score):
    return Finding(
        rule_id=rule_id,
        severity=severity,
        title=title,
        detail=detail,
        evidence=[Evidence(source="tushare", field="revenue", period="20250630", value=100.0)],
        score=score,
    )


def card(ts_code, severity, score):
    top = finding("cashflow_quality", severity, "现金流质量偏弱", "OCF/NP = 27.0%，低于 50.0%", score)
    return CompanyCard(
        ts_code=ts_code,
        period="20250630",
        fact_line="营收 100.0 | 净利 10.0 | 毛利率 30.0% | 经营现金流 2.7",
        findings=[top],
        max_severity=severity,
        max_score=score,
    )


def test_formal_summary_includes_all_abnormal_cards_and_skips_normal_details():
    red = card("603026.SH", Severity.RED, 90.0)
    yellow = card("600151.SH", Severity.YELLOW, 40.0)
    normal = CompanyCard(ts_code="600032.SH", period="20250630", fact_line="ok", findings=[], max_severity=None, max_score=0.0)
    summary = DailySummary(
        date="20250825",
        coverage_count=3,
        disclosed_count=3,
        red_count=1,
        yellow_count=1,
        ok_count=1,
        cards=[red, yellow, normal],
    )
    scan = build_scan_result(
        date="20250825",
        coverage_count=3,
        events=[
            DisclosureScanEvent(ts_code="603026.SH", period="20250630", status=CompanyAnalysisStatus.OK, message="ok", has_card=True, industry="generic"),
            DisclosureScanEvent(ts_code="600151.SH", period="20250630", status=CompanyAnalysisStatus.OK, message="ok", has_card=True, industry="generic"),
            DisclosureScanEvent(ts_code="600032.SH", period="20250630", status=CompanyAnalysisStatus.OK, message="ok", has_card=True, industry="generic"),
        ],
    )

    text = render_formal_disclosure_text(summary, scan, {"603026.SH": "石大胜华", "600151.SH": "航天机电"})

    assert "20250825 财报披露研判 · 覆盖池 3 家" in text
    assert "🔴 红色异常：1 家" in text
    assert "🟡 黄色异常：1 家" in text
    assert "【红色异常 · 1/1】" in text
    assert "603026.SH 石大胜华" in text
    assert "600151.SH 航天机电" in text
    assert "600032.SH" not in text
    assert "未见异常：1 家，不逐条展开" in text


def test_formal_summary_lists_data_problem_events():
    summary = DailySummary(date="20250825", coverage_count=2, disclosed_count=2, red_count=0, yellow_count=0, ok_count=1, cards=[])
    scan = build_scan_result(
        date="20250825",
        coverage_count=2,
        events=[
            DisclosureScanEvent(ts_code="000001.SZ", period="20250630", status=CompanyAnalysisStatus.DATA_NOT_READY, message="missing bank fields", has_card=False, industry="bank"),
            DisclosureScanEvent(ts_code="600000.SH", period="20250630", status=CompanyAnalysisStatus.ERROR, message="tushare timeout", has_card=False, industry="bank"),
        ],
    )

    text = render_formal_disclosure_text(summary, scan, {"000001.SZ": "平安银行", "600000.SH": "浦发银行"})

    assert "【数据问题 · 2】" in text
    assert "000001.SZ 平安银行 DATA_NOT_READY：missing bank fields" in text
    assert "600000.SH 浦发银行 ERROR：tushare timeout" in text
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_feishu_formal_summary.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `render_formal_disclosure_text` does not exist.

- [ ] **Step 3: Implement formal renderer**

Modify `copilot/notify/feishu.py`:

```python
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureScanResult


def _display_name(ts_code: str, company_names: dict[str, str]) -> str:
    name = company_names.get(ts_code)
    return f"{ts_code} {name}" if name else ts_code


def _abnormal_cards(summary: DailySummary, severity: Severity) -> list:
    return [card for card in summary.cards if card.max_severity == severity and card.findings]


def _card_line(card, company_names: dict[str, str], prefix: str) -> str:
    top = card.findings[0]
    return f"{prefix} {_display_name(card.ts_code, company_names)}\n- {top.title}：{top.detail}"


def _data_problem_events(scan: DisclosureScanResult):
    problem_statuses = {
        CompanyAnalysisStatus.DATA_NOT_READY,
        CompanyAnalysisStatus.DATA_INCOMPLETE,
        CompanyAnalysisStatus.ERROR,
    }
    return [event for event in scan.events if event.status in problem_statuses]


def render_formal_disclosure_text(summary: DailySummary, scan: DisclosureScanResult, company_names: dict[str, str] | None = None) -> str:
    names = company_names or {}
    red_cards = _abnormal_cards(summary, Severity.RED)
    yellow_cards = _abnormal_cards(summary, Severity.YELLOW)
    data_problems = _data_problem_events(scan)
    lines = [
        f"{summary.date} 财报披露研判 · 覆盖池 {summary.coverage_count} 家",
        "",
        f"今日披露：{summary.disclosed_count} 家",
        f"🔴 红色异常：{len(red_cards)} 家",
        f"🟡 黄色异常：{len(yellow_cards)} 家",
        f"⚪ 未见异常：{summary.ok_count} 家",
        f"⚠️ 数据问题：{len(data_problems)} 家",
    ]
    lines.extend(["", f"【红色异常 · {len(red_cards)}/{len(red_cards)}】"])
    lines.extend([_card_line(card, names, "🔴") for card in red_cards] or ["无"])
    lines.extend(["", f"【黄色异常 · {len(yellow_cards)}/{len(yellow_cards)}】"])
    lines.extend([_card_line(card, names, "🟡") for card in yellow_cards] or ["无"])
    lines.extend(["", f"【数据问题 · {len(data_problems)}】"])
    if data_problems:
        lines.extend(
            f"⚠️ {_display_name(event.ts_code, names)} {event.status.value}：{event.message}"
            for event in data_problems
        )
    else:
        lines.append("无")
    lines.extend(["", f"【未见异常】", f"未见异常：{summary.ok_count} 家，不逐条展开。"])
    return "\n".join(lines)
```

Keep `render_daily_summary_text()` unchanged for backward compatibility.

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_feishu_formal_summary.py tests/test_notify.py -q --basetemp=.pytest_tmp
```

Expected: PASS. If `tests/test_notify.py` does not exist, run only `tests/test_feishu_formal_summary.py`.

- [ ] **Step 5: Commit**

```bash
git add copilot/notify/feishu.py tests/test_feishu_formal_summary.py
git commit -m "feat: render formal Feishu disclosure summary"
```

---

### Task 3: Wire Real Feishu Notify to Scan Diagnostics

**Files:**
- Modify: `copilot/api/real_app.py`
- Modify: `copilot/api/dev_app.py`
- Create: `tests/test_real_app_notify.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_real_app_notify.py`:

```python
from copilot.api.app import NotifyResult
from copilot.models import Finding, Severity
from copilot.notify.feishu import render_formal_disclosure_text
from copilot.report.builder import CompanyCard, DailySummary
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureScanEvent, build_scan_result


def test_formal_notify_text_combines_summary_and_scan():
    card = CompanyCard(
        ts_code="603026.SH",
        period="20250630",
        fact_line="fact",
        findings=[Finding(rule_id="x", severity=Severity.RED, title="异常", detail="证据", evidence=[], score=99.0)],
        max_severity=Severity.RED,
        max_score=99.0,
    )
    summary = DailySummary(date="20250825", coverage_count=2, disclosed_count=2, red_count=1, yellow_count=0, ok_count=0, cards=[card])
    scan = build_scan_result(
        date="20250825",
        coverage_count=2,
        events=[
            DisclosureScanEvent(ts_code="603026.SH", period="20250630", status=CompanyAnalysisStatus.OK, message="ok", has_card=True, industry="generic"),
            DisclosureScanEvent(ts_code="000001.SZ", period="20250630", status=CompanyAnalysisStatus.DATA_NOT_READY, message="missing", has_card=False, industry="bank"),
        ],
    )

    text = render_formal_disclosure_text(summary, scan, {"603026.SH": "石大胜华", "000001.SZ": "平安银行"})

    assert "603026.SH 石大胜华" in text
    assert "000001.SZ 平安银行 DATA_NOT_READY：missing" in text
```

- [ ] **Step 2: Run test to verify failure or baseline**

Run:

```bash
python -m pytest tests/test_real_app_notify.py -q --basetemp=.pytest_tmp
```

Expected: PASS if Task 2 already exposes the renderer. This task's production change is wiring, not renderer behavior.

- [ ] **Step 3: Wire real app notification**

Modify `copilot/api/real_app.py` import:

```python
from copilot.notify.feishu import FeishuNotifier, render_formal_disclosure_text
```

Modify `notify_feishu_disclosure_day()`:

```python
    def notify_feishu_disclosure_day(self, date):
        summary = self.analyze_disclosure_day(date)
        scan = self.scan_disclosure_day(date)
        if summary.disclosed_count == 0 and scan.disclosed_count == 0:
            return NotifyResult(sent=False, reason="no_disclosures")
        webhook = self.settings.notify.feishu_webhook
        if not webhook:
            return NotifyResult(sent=False, reason="webhook_not_configured")
        text = render_formal_disclosure_text(summary, scan, self.settings.eval.company_names)
        sent = FeishuNotifier(webhook).send_text(text)
        return NotifyResult(sent=sent, reason="ok" if sent else "send_failed")
```

Modify `copilot/api/dev_app.py` import and `notify_feishu_disclosure_day()` if needed so demo service can still return `NotifyResult(sent=False, reason="webhook_not_configured")` without breaking tests.

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_real_app_notify.py tests/test_api_disclosure_scan.py tests/test_real_app_startup.py -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/api/real_app.py copilot/api/dev_app.py tests/test_real_app_notify.py
git commit -m "feat: send formal Feishu disclosure summary"
```

---

### Task 4: Backend Smoke Commands and Remaining Work Self-Review

**Files:**
- Modify: `docs/development-log.md`

- [ ] **Step 1: Run full tests**

Run:

```bash
python -m pytest -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 2: Run formal summary preview without sending**

Run:

```bash
PYTHONIOENCODING=utf-8 python - <<'PY'
from copilot.api.real_app import RealReportService
from copilot.notify.feishu import render_formal_disclosure_text

service = RealReportService()
summary = service.analyze_disclosure_day("20250825")
scan = service.scan_disclosure_day("20250825")
text = render_formal_disclosure_text(summary, scan, service.settings.eval.company_names)
print("TEXT_CHARS=", len(text))
print("TEXT_LINES=", len(text.splitlines()))
print("RED=", summary.red_count)
print("YELLOW=", summary.yellow_count)
print("DATA_PROBLEMS=", scan.data_not_ready_count + scan.data_incomplete_count + scan.error_count)
print(text[:2000])
PY
```

Expected: prints a formal summary preview with all red/yellow abnormal companies, all data problems, and normal-company count only.

- [ ] **Step 3: Record self-review in development log**

Append to `docs/development-log.md`:

```markdown
### Backend Feishu completion self-review

Completed in this phase:

- Formal Feishu disclosure renderer: total summary, all red/yellow abnormalities, data-problem events, normal-company count.
- Real notify path now combines `DailySummary` with `DisclosureScanResult`.
- Company display names are available through `eval.company_names`.
- Frontend intentionally unchanged in this phase.

Still not done:

- Feishu interactive card/buttons/callback.
- Stable hosted detail URL for every disclosure day.
- True industry-specific bank metrics such as NIM/NPL/provision coverage/capital adequacy.
- Other industry rule packs for securities, insurance, real estate, utilities.
- Scheduler/retry daemon/RSS retry queue.
- PDF/LLM management discussion attribution in real cards.
- Formal replacement of the smoke 100-stock pool with the user's true watchlist.
```

- [ ] **Step 4: Run full tests again**

Run:

```bash
python -m pytest -q --basetemp=.pytest_tmp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/development-log.md
git commit -m "docs: record backend Feishu completion review"
```

---

## Definition of Done

- No frontend files changed after this plan begins.
- `python -m pytest -q --basetemp=.pytest_tmp` passes.
- `config.yaml` has 100-stock smoke pool plus `company_names` and `company_industries` mappings.
- Formal Feishu renderer includes all red/yellow abnormal cards and all scan data problems.
- Real Feishu notify path uses formal renderer with scan diagnostics.
- Development log lists what remains after this backend-only phase.
- No real secrets are printed or committed.

## Self-Review Notes

Spec coverage: This plan covers the user's request to skip frontend work and finish remaining backend/Feishu work in batches, with a final self-review of remaining items. Placeholder scan: no placeholder tasks remain; concrete tests and code snippets are provided for each batch. Type consistency: `render_formal_disclosure_text(summary, scan, company_names)`, `company_names`, `DisclosureScanResult`, and `CompanyAnalysisStatus` are used consistently across tests and implementation.
