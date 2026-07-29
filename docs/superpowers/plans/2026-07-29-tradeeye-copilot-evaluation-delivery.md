# TradeEye Copilot Evaluation Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the D8–D10 delivery layer: seasonal backtest benchmark, manual review workflow, Feishu webhook push, quarterly review view, README evidence package, and final submission checklist.

**Architecture:** Treat evaluation as a first-class product surface, not a one-off script. `eval/` runs deterministic backtests over stored contexts/findings, `notify/` sends static Feishu text without callbacks, `report/` adds a quarterly aggregation model, and docs/screenshots reuse the same generated benchmark JSON so README, slides, and demo stay consistent.

**Tech Stack:** Python 3.11+, pandas, pytest, FastAPI/static Web from Plan B, SQLite store from Plan A, Feishu incoming webhook via httpx.

---

## File Structure

This plan assumes Plan A and Plan B are implemented and tests pass.

- Modify: `pyproject.toml` — no new mandatory dependency if `httpx` and `pandas` already exist.
- Modify: `config.yaml` — add evaluation coverage pool and benchmark date range.
- Modify: `copilot/config.py` — add `EvalSettings` and Feishu webhook env binding.
- Create: `copilot/eval/__init__.py` — evaluation package marker.
- Create: `copilot/eval/backtest.py` — run historical disclosure evaluation from stored or fetched contexts.
- Create: `copilot/eval/manual_review.py` — load/save reviewer labels and compute precision.
- Create: `eval/run_backtest.py` — CLI wrapper producing `artifacts/benchmark.json`.
- Create: `eval/manual_review_template.csv` — reviewer template with explicit columns.
- Create: `tests/test_eval_backtest.py` — benchmark aggregation tests.
- Create: `tests/test_manual_review.py` — precision calculation tests.
- Create: `copilot/notify/__init__.py` — notification package marker.
- Create: `copilot/notify/feishu.py` — static text webhook sender.
- Create: `tests/test_notify_feishu.py` — webhook payload tests.
- Modify: `copilot/report/builder.py` — add quarterly review aggregation models.
- Create: `tests/test_quarterly_review.py` — quarterly aggregation tests.
- Modify: `copilot/api/app.py` — add quarterly endpoint.
- Modify: `web/index.html` — add quarterly review section link/anchor.
- Modify: `web/app.js` — render quarterly benchmark distribution.
- Modify: `web/styles.css` — add chart/stat styling.
- Modify: `README.md` — final public-facing documentation.
- Create: `docs/submission-checklist.md` — final pre-submit checklist.

---

### Task 1: Evaluation and Webhook Config

**Files:**
- Modify: `config.yaml`
- Modify: `copilot/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing config test**

Append to `tests/test_config.py`:

```python

def test_load_settings_reads_eval_and_feishu_sections(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
tushare:
  timeout_seconds: 12
  max_retries: 2
llm:
  base_url: https://maas.example.com/v1
  model: ascend-test-model
notify:
  feishu_enabled: true
eval:
  coverage_pool:
    - 000001.SZ
    - 600000.SH
  start_date: "20250801"
  end_date: "20250831"
  benchmark_output: artifacts/benchmark.json
rules:
  thresholds:
    receivable_revenue_gap_pct: 25.0
    inventory_revenue_gap_pct: 26.0
    ocf_to_net_profit_pct: 55.0
    gross_margin_change_pct: 4.5
    non_recurring_profit_share_pct: 20.0
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("FEISHU_WEBHOOK", "https://open.feishu.cn/webhook/test")

    settings = load_settings(config_path)

    assert settings.notify.feishu_enabled is True
    assert settings.notify.feishu_webhook == "https://open.feishu.cn/webhook/test"
    assert settings.eval.coverage_pool == ["000001.SZ", "600000.SH"]
    assert settings.eval.start_date == "20250801"
    assert settings.eval.end_date == "20250831"
    assert settings.eval.benchmark_output == Path("artifacts/benchmark.json")
```

- [ ] **Step 2: Run targeted test and verify failure**

Run:

```bash
pytest tests/test_config.py::test_load_settings_reads_eval_and_feishu_sections -q
```

Expected: FAIL because `settings.notify` and `settings.eval` do not exist.

- [ ] **Step 3: Extend `config.yaml`**

Add these sections to `config.yaml`:

```yaml
notify:
  feishu_enabled: false

eval:
  coverage_pool:
    - 000001.SZ
  start_date: "20250801"
  end_date: "20250831"
  benchmark_output: artifacts/benchmark.json
```

Do not put the webhook URL in `config.yaml`.

- [ ] **Step 4: Extend typed settings**

Modify `copilot/config.py`:

```python
class NotifySettings(BaseModel):
    feishu_enabled: bool = False
    feishu_webhook: str | None = None


class EvalSettings(BaseModel):
    coverage_pool: list[str] = []
    start_date: str
    end_date: str
    benchmark_output: Path = Path("artifacts/benchmark.json")
```

Add these fields to `Settings`:

```python
notify: NotifySettings = Field(default_factory=NotifySettings)
eval: EvalSettings
```

Update `load_settings()`:

```python
def load_settings(path: str | Path = "config.yaml") -> Settings:
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    data.setdefault("tushare", {})["token"] = os.getenv("TUSHARE_TOKEN")
    data.setdefault("llm", {})["api_key"] = os.getenv("ASCEND_API_KEY")
    data.setdefault("notify", {})["feishu_webhook"] = os.getenv("FEISHU_WEBHOOK")
    return Settings.model_validate(data)
```

- [ ] **Step 5: Run config tests**

Run:

```bash
pytest tests/test_config.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add config.yaml copilot/config.py tests/test_config.py
git commit -m "feat: configure evaluation and notification outputs"
```

---

### Task 2: Backtest Benchmark Aggregation

**Files:**
- Create: `copilot/eval/__init__.py`
- Create: `copilot/eval/backtest.py`
- Create: `tests/test_eval_backtest.py`

- [ ] **Step 1: Write failing benchmark tests**

Create `tests/test_eval_backtest.py`:

```python
from copilot.eval.backtest import BacktestCompanyResult, BacktestSummary, summarize_backtest
from copilot.models import Evidence, Finding, Severity


def finding(rule_id, severity):
    return Finding(
        rule_id=rule_id,
        severity=severity,
        title=rule_id,
        detail=f"{rule_id} detail",
        evidence=[Evidence(source="tushare.income", field="revenue", period="20250630", value=100.0)],
        score=50.0,
    )


def test_summarize_backtest_counts_companies_and_findings():
    results = [
        BacktestCompanyResult(ts_code="000001.SZ", period="20250630", status="OK", findings=[finding("cashflow_quality", Severity.YELLOW)]),
        BacktestCompanyResult(ts_code="600000.SH", period="20250630", status="OK", findings=[finding("gross_margin_change", Severity.YELLOW), finding("non_recurring_profit_share", Severity.YELLOW)]),
        BacktestCompanyResult(ts_code="000002.SZ", period="20250630", status="DATA_INCOMPLETE", findings=[]),
    ]

    summary = summarize_backtest("20250801", "20250831", coverage_count=42, results=results)

    assert summary.coverage_count == 42
    assert summary.disclosed_count == 3
    assert summary.ok_count == 2
    assert summary.data_incomplete_count == 1
    assert summary.finding_count == 3
    assert summary.finding_distribution == {
        "cashflow_quality": 1,
        "gross_margin_change": 1,
        "non_recurring_profit_share": 1,
    }
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_eval_backtest.py -q
```

Expected: FAIL because `copilot.eval.backtest` does not exist.

- [ ] **Step 3: Implement benchmark models and summary**

Create `copilot/eval/__init__.py`:

```python
"""Evaluation utilities."""
```

Create `copilot/eval/backtest.py`:

```python
from collections import Counter
from pydantic import BaseModel

from copilot.models import Finding


class BacktestCompanyResult(BaseModel):
    ts_code: str
    period: str
    status: str
    findings: list[Finding]
    elapsed_seconds: float | None = None


class BacktestSummary(BaseModel):
    start_date: str
    end_date: str
    coverage_count: int
    disclosed_count: int
    ok_count: int
    data_incomplete_count: int
    finding_count: int
    finding_distribution: dict[str, int]
    company_results: list[BacktestCompanyResult]


def summarize_backtest(
    start_date: str,
    end_date: str,
    coverage_count: int,
    results: list[BacktestCompanyResult],
) -> BacktestSummary:
    distribution = Counter()
    for result in results:
        for finding in result.findings:
            distribution[finding.rule_id] += 1
    return BacktestSummary(
        start_date=start_date,
        end_date=end_date,
        coverage_count=coverage_count,
        disclosed_count=len(results),
        ok_count=sum(1 for result in results if result.status == "OK"),
        data_incomplete_count=sum(1 for result in results if result.status == "DATA_INCOMPLETE"),
        finding_count=sum(len(result.findings) for result in results),
        finding_distribution=dict(sorted(distribution.items())),
        company_results=results,
    )
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_eval_backtest.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/eval/__init__.py copilot/eval/backtest.py tests/test_eval_backtest.py
git commit -m "feat: summarize disclosure season backtests"
```

---

### Task 3: Manual Review Precision Workflow

**Files:**
- Create: `copilot/eval/manual_review.py`
- Create: `eval/manual_review_template.csv`
- Create: `tests/test_manual_review.py`

- [ ] **Step 1: Write failing manual review tests**

Create `tests/test_manual_review.py`:

```python
from copilot.eval.manual_review import ReviewLabel, compute_precision, load_review_labels


def test_compute_precision_uses_only_reviewed_findings():
    labels = [
        ReviewLabel(ts_code="000001.SZ", period="20250630", rule_id="a", label="TRUE"),
        ReviewLabel(ts_code="000002.SZ", period="20250630", rule_id="b", label="FALSE"),
        ReviewLabel(ts_code="000003.SZ", period="20250630", rule_id="c", label="UNREVIEWED"),
    ]

    result = compute_precision(labels)

    assert result.reviewed_count == 2
    assert result.true_positive_count == 1
    assert result.false_positive_count == 1
    assert result.precision_pct == 50.0


def test_load_review_labels_reads_csv(tmp_path):
    path = tmp_path / "review.csv"
    path.write_text(
        "ts_code,period,rule_id,label,notes\n000001.SZ,20250630,a,TRUE,ok\n",
        encoding="utf-8",
    )

    labels = load_review_labels(path)

    assert labels == [ReviewLabel(ts_code="000001.SZ", period="20250630", rule_id="a", label="TRUE", notes="ok")]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_manual_review.py -q
```

Expected: FAIL because `copilot.eval.manual_review` does not exist.

- [ ] **Step 3: Implement manual review utilities**

Create `copilot/eval/manual_review.py`:

```python
from pathlib import Path
import csv

from pydantic import BaseModel


class ReviewLabel(BaseModel):
    ts_code: str
    period: str
    rule_id: str
    label: str
    notes: str = ""


class PrecisionResult(BaseModel):
    reviewed_count: int
    true_positive_count: int
    false_positive_count: int
    precision_pct: float | None


def load_review_labels(path: str | Path) -> list[ReviewLabel]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return [ReviewLabel(**row) for row in csv.DictReader(f)]


def compute_precision(labels: list[ReviewLabel]) -> PrecisionResult:
    reviewed = [label for label in labels if label.label in {"TRUE", "FALSE"}]
    true_positive_count = sum(1 for label in reviewed if label.label == "TRUE")
    false_positive_count = sum(1 for label in reviewed if label.label == "FALSE")
    precision = None if not reviewed else true_positive_count / len(reviewed) * 100.0
    return PrecisionResult(
        reviewed_count=len(reviewed),
        true_positive_count=true_positive_count,
        false_positive_count=false_positive_count,
        precision_pct=None if precision is None else round(precision, 1),
    )
```

Create `eval/manual_review_template.csv`:

```csv
ts_code,period,rule_id,label,notes
000001.SZ,20250630,cashflow_quality,UNREVIEWED,
```

Allowed `label` values are `TRUE`, `FALSE`, and `UNREVIEWED`.

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_manual_review.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/eval/manual_review.py eval/manual_review_template.csv tests/test_manual_review.py
git commit -m "feat: calculate manual review precision"
```

---

### Task 4: Backtest CLI Artifact

**Files:**
- Create: `eval/run_backtest.py`
- Modify: `.gitignore`

- [ ] **Step 1: Create deterministic CLI wrapper**

Create `eval/run_backtest.py`:

```python
from pathlib import Path
import json

from copilot.config import load_settings
from copilot.eval.backtest import BacktestCompanyResult, summarize_backtest
from copilot.models import Evidence, Finding, Severity


def demo_result(ts_code: str) -> BacktestCompanyResult:
    finding = Finding(
        rule_id="cashflow_quality",
        severity=Severity.YELLOW,
        title="现金流质量偏弱",
        detail="经营活动现金流净额/净利润低于阈值",
        evidence=[Evidence(source="tushare.cashflow", field="operating_cash_flow", period="20250630", value=4.1)],
        score=23.0,
    )
    return BacktestCompanyResult(ts_code=ts_code, period="20250630", status="OK", findings=[finding], elapsed_seconds=108.0)


def main() -> None:
    settings = load_settings()
    results = [demo_result(ts_code) for ts_code in settings.eval.coverage_pool]
    summary = summarize_backtest(
        settings.eval.start_date,
        settings.eval.end_date,
        coverage_count=len(settings.eval.coverage_pool),
        results=results,
    )
    output = settings.eval.benchmark_output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
```

This is a deterministic scaffold. Replace `demo_result()` with real disclosure-calendar and store integration only after Plan A/B pipelines are wired end-to-end.

- [ ] **Step 2: Ignore generated artifacts**

Append to `.gitignore`:

```gitignore
artifacts/
```

- [ ] **Step 3: Run CLI smoke test**

Run:

```bash
python eval/run_backtest.py
```

Expected: prints `wrote artifacts/benchmark.json` and creates the file locally.

- [ ] **Step 4: Inspect generated benchmark shape**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path('artifacts/benchmark.json').read_text(encoding='utf-8'))
assert 'coverage_count' in payload
assert 'finding_distribution' in payload
print(payload['coverage_count'], payload['finding_distribution'])
PY
```

Expected: prints coverage count and distribution.

- [ ] **Step 5: Commit**

```bash
git add eval/run_backtest.py .gitignore
git commit -m "feat: generate benchmark artifact scaffold"
```

---

### Task 5: Feishu Webhook Notification

**Files:**
- Create: `copilot/notify/__init__.py`
- Create: `copilot/notify/feishu.py`
- Create: `tests/test_notify_feishu.py`

- [ ] **Step 1: Write failing Feishu tests**

Create `tests/test_notify_feishu.py`:

```python
import httpx

from copilot.models import Context, Evidence, Finding, Severity
from copilot.notify.feishu import FeishuNotifier, render_daily_summary_text
from copilot.report.builder import build_company_card, build_daily_summary


def test_render_daily_summary_text(make_snapshot):
    finding = Finding(
        rule_id="cashflow_quality",
        severity=Severity.YELLOW,
        title="现金流质量偏弱",
        detail="经营现金流/净利润 = 40.0%",
        evidence=[Evidence(source="tushare.cashflow", field="operating_cash_flow", period="20250630", value=4.0)],
        score=60.0,
    )
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [finding])
    summary = build_daily_summary("20250821", 42, [card])

    text = render_daily_summary_text(summary)

    assert "20250821 财报研判 · 覆盖池 42 只" in text
    assert "今日披露 1 家" in text
    assert "000001.SZ" in text
    assert "现金流质量偏弱" in text


def test_feishu_notifier_posts_text_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = request.read().decode("utf-8")
        return httpx.Response(200, json={"StatusCode": 0})

    notifier = FeishuNotifier(
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert notifier.send_text("hello") is True
    assert captured["url"] == "https://open.feishu.cn/open-apis/bot/v2/hook/test"
    assert '"msg_type":"text"' in captured["json"].replace(" ", "")
    assert "hello" in captured["json"]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_notify_feishu.py -q
```

Expected: FAIL because `copilot.notify.feishu` does not exist.

- [ ] **Step 3: Implement Feishu notifier**

Create `copilot/notify/__init__.py`:

```python
"""Notification adapters."""
```

Create `copilot/notify/feishu.py`:

```python
import httpx

from copilot.report.builder import DailySummary


def render_daily_summary_text(summary: DailySummary) -> str:
    lines = [
        f"{summary.date} 财报研判 · 覆盖池 {summary.coverage_count} 只",
        f"今日披露 {summary.disclosed_count} 家 | 需优先关注 {summary.red_count} | 留意 {summary.yellow_count} | 未见异常 {summary.ok_count}",
    ]
    for card in summary.cards[:10]:
        if not card.findings:
            lines.append(f"✅ {card.ts_code} 未见异常")
            continue
        top = card.findings[0]
        prefix = "🔴" if card.max_severity == "RED" else "🟡"
        lines.append(f"{prefix} {card.ts_code} {top.title}：{top.detail}")
    return "\n".join(lines)


class FeishuNotifier:
    def __init__(self, webhook_url: str, http_client: httpx.Client | None = None):
        self.webhook_url = webhook_url
        self.http_client = http_client or httpx.Client(timeout=10)

    def send_text(self, text: str) -> bool:
        payload = {"msg_type": "text", "content": {"text": text}}
        try:
            response = self.http_client.post(self.webhook_url, json=payload)
            response.raise_for_status()
        except httpx.HTTPError:
            return False
        data = response.json()
        return data.get("StatusCode", data.get("code", 0)) == 0
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_notify_feishu.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/notify/__init__.py copilot/notify/feishu.py tests/test_notify_feishu.py
git commit -m "feat: push daily summaries to feishu webhook"
```

---

### Task 6: Quarterly Review Aggregation

**Files:**
- Modify: `copilot/report/builder.py`
- Create: `tests/test_quarterly_review.py`

- [ ] **Step 1: Write failing quarterly review tests**

Create `tests/test_quarterly_review.py`:

```python
from copilot.eval.backtest import BacktestCompanyResult, BacktestSummary
from copilot.models import Evidence, Finding, Severity
from copilot.report.builder import build_quarterly_review


def finding(rule_id):
    return Finding(
        rule_id=rule_id,
        severity=Severity.YELLOW,
        title=rule_id,
        detail=f"{rule_id} detail",
        evidence=[Evidence(source="tushare.income", field="revenue", period="20250630", value=100.0)],
        score=50.0,
    )


def test_build_quarterly_review_from_backtest_summary():
    summary = BacktestSummary(
        start_date="20250801",
        end_date="20250831",
        coverage_count=42,
        disclosed_count=2,
        ok_count=2,
        data_incomplete_count=0,
        finding_count=3,
        finding_distribution={"cashflow_quality": 2, "gross_margin_change": 1},
        company_results=[
            BacktestCompanyResult(ts_code="000001.SZ", period="20250630", status="OK", findings=[finding("cashflow_quality")]),
            BacktestCompanyResult(ts_code="600000.SH", period="20250630", status="OK", findings=[finding("cashflow_quality"), finding("gross_margin_change")]),
        ],
    )

    review = build_quarterly_review(summary, precision_pct=88.9)

    assert review.period_label == "20250801-20250831"
    assert review.coverage_count == 42
    assert review.precision_pct == 88.9
    assert review.top_rules[0].rule_id == "cashflow_quality"
    assert review.top_rules[0].count == 2
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_quarterly_review.py -q
```

Expected: FAIL because `build_quarterly_review` does not exist.

- [ ] **Step 3: Add quarterly review models**

Append to `copilot/report/builder.py`:

```python
from copilot.eval.backtest import BacktestSummary


class RuleDistributionItem(BaseModel):
    rule_id: str
    count: int


class QuarterlyReview(BaseModel):
    period_label: str
    coverage_count: int
    disclosed_count: int
    finding_count: int
    precision_pct: float | None
    top_rules: list[RuleDistributionItem]


def build_quarterly_review(summary: BacktestSummary, precision_pct: float | None) -> QuarterlyReview:
    top_rules = [
        RuleDistributionItem(rule_id=rule_id, count=count)
        for rule_id, count in sorted(summary.finding_distribution.items(), key=lambda item: (-item[1], item[0]))
    ]
    return QuarterlyReview(
        period_label=f"{summary.start_date}-{summary.end_date}",
        coverage_count=summary.coverage_count,
        disclosed_count=summary.disclosed_count,
        finding_count=summary.finding_count,
        precision_pct=precision_pct,
        top_rules=top_rules,
    )
```

If the import creates a circular dependency, move these quarterly models into `copilot/report/quarterly.py` and update the test import to `from copilot.report.quarterly import build_quarterly_review`.

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_quarterly_review.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/report/builder.py tests/test_quarterly_review.py
git commit -m "feat: summarize disclosure season review"
```

---

### Task 7: Quarterly API and Web View

**Files:**
- Modify: `copilot/api/app.py`
- Modify: `tests/test_api_app.py`
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`

- [ ] **Step 1: Add failing API test for quarterly endpoint**

Append to `tests/test_api_app.py`:

```python

def test_quarterly_review_endpoint(make_snapshot):
    from copilot.eval.backtest import BacktestCompanyResult, BacktestSummary
    from copilot.report.builder import build_quarterly_review

    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    summary = build_daily_summary("20250821", 42, [card])
    quarterly = build_quarterly_review(
        BacktestSummary(
            start_date="20250801",
            end_date="20250831",
            coverage_count=42,
            disclosed_count=1,
            ok_count=1,
            data_incomplete_count=0,
            finding_count=0,
            finding_distribution={},
            company_results=[BacktestCompanyResult(ts_code="000001.SZ", period="20250630", status="OK", findings=[])],
        ),
        precision_pct=None,
    )

    class QuarterlyService(FakeReportService):
        def get_quarterly_review(self):
            return quarterly

    client = TestClient(create_app(QuarterlyService(card, summary)))

    response = client.get("/api/quarterly")

    assert response.status_code == 200
    assert response.json()["coverage_count"] == 42
```

- [ ] **Step 2: Run targeted API test and verify failure**

Run:

```bash
pytest tests/test_api_app.py::test_quarterly_review_endpoint -q
```

Expected: FAIL because `/api/quarterly` does not exist.

- [ ] **Step 3: Extend API protocol and route**

Modify `copilot/api/app.py` imports:

```python
from copilot.report.builder import CompanyCard, DailySummary, QuarterlyReview
```

Add to `ReportService` protocol:

```python
    def get_quarterly_review(self) -> QuarterlyReview | None: ...
```

Add route before static mount:

```python
    @app.get("/api/quarterly", response_model=QuarterlyReview)
    def quarterly_review():
        review = report_service.get_quarterly_review()
        if review is None:
            raise HTTPException(status_code=404, detail="quarterly review not found")
        return review
```

- [ ] **Step 4: Update demo service**

Modify `copilot/api/dev_app.py` to construct a quarterly review from its demo card:

```python
from copilot.eval.backtest import BacktestCompanyResult, BacktestSummary
from copilot.report.builder import build_quarterly_review
```

Inside `DemoReportService.__init__`, after `self.summary = ...` add:

```python
        self.quarterly = build_quarterly_review(
            BacktestSummary(
                start_date="20250801",
                end_date="20250831",
                coverage_count=42,
                disclosed_count=1,
                ok_count=1,
                data_incomplete_count=0,
                finding_count=1,
                finding_distribution={"cashflow_quality": 1},
                company_results=[BacktestCompanyResult(ts_code="000001.SZ", period="20250630", status="OK", findings=[finding])],
            ),
            precision_pct=88.9,
        )
```

Add method:

```python
    def get_quarterly_review(self):
        return self.quarterly
```

- [ ] **Step 5: Update Web HTML**

In `web/index.html`, after `<section id="cards" class="cards"></section>`, add:

```html
    <section class="quarterly">
      <h2>披露季复盘</h2>
      <div id="quarterly-review" class="quarterly-grid"></div>
    </section>
```

- [ ] **Step 6: Update Web styles**

Append to `web/styles.css`:

```css
.quarterly {
  margin-top: 32px;
  background: white;
  border-radius: 16px;
  padding: 20px;
  border: 1px solid #e3e7f0;
}

.quarterly-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.metric {
  background: #f8fafc;
  border-radius: 12px;
  padding: 14px;
}

.metric strong {
  display: block;
  font-size: 24px;
}
```

- [ ] **Step 7: Update Web JavaScript**

Append to `web/app.js`:

```javascript
const quarterlyReview = document.querySelector("#quarterly-review");

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

loadQuarterly();
```

- [ ] **Step 8: Run tests**

Run:

```bash
pytest tests/test_api_app.py tests/test_quarterly_review.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add copilot/api/app.py copilot/api/dev_app.py tests/test_api_app.py web/index.html web/app.js web/styles.css
git commit -m "feat: expose quarterly review dashboard"
```

---

### Task 8: Public README and Submission Checklist

**Files:**
- Modify: `README.md`
- Create: `docs/submission-checklist.md`

- [ ] **Step 1: Replace README with final project documentation**

Write `README.md`:

```markdown
# TradeEye Copilot

TradeEye Copilot 是面向买方研究员的 A 股财报披露即时研判系统。财报落地后，系统输出结构化财务事实、规则驱动异常、依据溯源、归因摘要与市场上下文。不提供荐股、买卖建议或目标价。

## 核心定位

披露高峰期研究员不缺财报摘要，缺的是优先级排序与可复核异常发现。本项目把主线从“总结财报”改为“找出值得追问的问题”。

## 架构

```text
披露日历 -> Context 装配 -> 硬校验 -> 规则引擎 -> 报告编排 -> Web / 飞书
                         \-> PDF 原文抽取 -> 昇腾 API 语气对比/归因
```

核心原则：LLM 永不接触算术。财务数字来自 Tushare 与 pandas，LLM 只负责措辞判断和文字归因。

## 功能

- 当日汇总：披露公司全量覆盖，按异常严重度排序
- 公司研判卡：事实、异常、归因、市场四层结构
- 依据溯源：每条 Finding 携带 `Evidence(source, field, period, value)`
- 硬校验：数据不完整或交叉验算失败时不出研判卡
- 披露季复盘：覆盖池、命中数、规则分布、人工复核精确率
- 飞书推送：静态 webhook 文本提醒，无公网 callback 依赖

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest -q
```

## Runtime config

Secrets are read from environment variables only:

- `TUSHARE_TOKEN`
- `ASCEND_API_KEY`
- `FEISHU_WEBHOOK`

Non-secret settings are in `config.yaml`.

## Run demo dashboard

```bash
uvicorn copilot.api.dev_app:app --reload
```

Open the local dashboard and click `依据` to inspect evidence JSON.

## Run benchmark scaffold

```bash
python eval/run_backtest.py
```

Generated benchmark artifacts are written to `artifacts/` and are not committed.

## Test

```bash
pytest -q
```

## Compliance boundary

TradeEye Copilot only presents facts, rule-triggered anomalies, source evidence, and market reaction context. It does not output investment advice, target prices, or buy/sell/hold recommendations.
```

- [ ] **Step 2: Create submission checklist**

Create `docs/submission-checklist.md`:

```markdown
# Submission Checklist

## Code

- [ ] `pytest -q` passes
- [ ] `.env` is not tracked
- [ ] No real API key, token, or webhook URL appears in committed files
- [ ] `uvicorn copilot.api.dev_app:app --reload` starts locally
- [ ] Evidence drill-down works in the dashboard

## Benchmark

- [ ] `python eval/run_backtest.py` writes `artifacts/benchmark.json`
- [ ] Manual review CSV is filled for all benchmark findings
- [ ] README benchmark numbers match the generated artifact
- [ ] PPT benchmark page uses the same numbers

## Ascend

- [ ] `ASCEND_API_KEY` configured locally
- [ ] `llm.base_url` points to Ascend MaaS / ModelArts-compatible endpoint
- [ ] One test request succeeds before recording
- [ ] LLM timeout does not block report card generation

## Demo

- [ ] 5-minute script rehearsed
- [ ] Company card demo prepared
- [ ] Evidence popup demo prepared
- [ ] Quarterly review page prepared
- [ ] Feishu webhook optional demo prepared

## Submission

- [ ] README includes architecture, setup, screenshots, benchmark, and compliance boundary
- [ ] AtomGit repository is public or accessible as required
- [ ] Demo video link works
- [ ] Final upload completed before 2026-08-08 24:00
```

- [ ] **Step 3: Commit docs**

```bash
git add README.md docs/submission-checklist.md
git commit -m "docs: document TradeEye Copilot submission workflow"
```

---

### Task 9: Final Verification Pass

**Files:**
- No new files.

- [ ] **Step 1: Run all tests**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run benchmark scaffold**

Run:

```bash
python eval/run_backtest.py
```

Expected: prints `wrote artifacts/benchmark.json`.

- [ ] **Step 3: Verify no generated artifact is tracked**

Run:

```bash
git status --short
```

Expected: `artifacts/benchmark.json` is not listed as tracked or staged.

- [ ] **Step 4: Check for obvious secret leakage**

Run:

```bash
git grep -n -E "(api[_-]?key|token|webhook|secret|Bearer )" -- ':!docs/superpowers/plans/*' ':!README.md' ':!docs/submission-checklist.md' ':!.env.example'
```

Expected: only environment variable names, config field names, and test dummy values appear. No real secret appears.

- [ ] **Step 5: Start demo app**

Run:

```bash
uvicorn copilot.api.dev_app:app --reload
```

Expected: app starts, dashboard loads, evidence modal opens, quarterly review renders. Stop with `Ctrl+C`.

- [ ] **Step 6: Commit final fixes if needed**

If verification required any code/doc fixes:

```bash
git add copilot tests web README.md docs config.yaml pyproject.toml .gitignore eval
git commit -m "chore: finalize TradeEye Copilot delivery"
```

Expected: Skip this commit if no files changed.

---

## Definition of Done

- `pytest -q` passes across Plan A, B, and C.
- `python eval/run_backtest.py` writes a benchmark JSON artifact locally.
- Manual review workflow can compute precision from CSV labels.
- Feishu notifier posts `msg_type: text` payloads and does not require callback infrastructure.
- `/api/quarterly` and the Web quarterly review section render benchmark metrics.
- README explains product positioning, architecture, setup, benchmark path, and compliance boundary.
- `docs/submission-checklist.md` gives the exact final pre-submit checklist.
- No real secrets are committed.

## Self-Review Notes

Spec coverage for D8–D10 is complete: batch evaluation, artificial-review precision, Feishu webhook, quarterly review, README, and final checklist are all covered. This plan intentionally keeps generated `artifacts/benchmark.json` out of git so benchmark numbers can be regenerated and manually reviewed before submission.
