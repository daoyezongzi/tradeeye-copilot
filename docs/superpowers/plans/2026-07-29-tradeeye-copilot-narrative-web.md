# TradeEye Copilot Narrative Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the D5–D7 layer: Ascend-compatible LLM client, PDF management-discussion extraction, tone comparison rule, report card builder, FastAPI endpoints, and a static Web dashboard with evidence drill-down.

**Architecture:** Keep Plan A's arithmetic core as the source of truth. The LLM is a single outbound adapter used only by `narrative/` and `report/`; API responses are built from stored snapshots/findings plus optional narrative outputs. The static Web app reads JSON endpoints and never performs calculations in the browser.

**Tech Stack:** Python 3.11+, FastAPI, httpx, PyMuPDF, pydantic, pytest, vanilla HTML/CSS/JS.

---

## File Structure

This plan assumes Plan A has been implemented and tests pass.

- Modify: `pyproject.toml` — add FastAPI, uvicorn, httpx, PyMuPDF.
- Modify: `config.yaml` — add non-secret LLM and PDF settings.
- Modify: `copilot/config.py` — add `LLMSettings` and `NarrativeSettings`.
- Create: `copilot/llm/__init__.py` — LLM package marker.
- Create: `copilot/llm/client.py` — single OpenAI-compatible chat completions client for Ascend MaaS.
- Create: `copilot/narrative/__init__.py` — narrative package marker.
- Create: `copilot/narrative/extract.py` — extract management discussion / outlook text from cached PDFs.
- Create: `copilot/narrative/tone.py` — compare two periods' management wording and return a tone finding.
- Create: `copilot/report/__init__.py` — report package marker.
- Create: `copilot/report/builder.py` — build company cards and daily summaries from core data.
- Create: `copilot/api/__init__.py` — API package marker.
- Create: `copilot/api/app.py` — FastAPI app with company card, daily summary, and evidence endpoints.
- Create: `web/index.html` — dashboard shell.
- Create: `web/styles.css` — presentation styling.
- Create: `web/app.js` — fetch and render summaries/cards/evidence.
- Create: `tests/test_llm_client.py` — LLM adapter tests with mocked transport.
- Create: `tests/test_narrative_extract.py` — PDF/text extraction tests.
- Create: `tests/test_narrative_tone.py` — tone prompt/parse tests.
- Create: `tests/test_report_builder.py` — card builder tests.
- Create: `tests/test_api_app.py` — endpoint tests.

---

### Task 1: Runtime Dependencies and Config Extension

**Files:**
- Modify: `pyproject.toml`
- Modify: `config.yaml`
- Modify: `copilot/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing config test for LLM and narrative settings**

Append to `tests/test_config.py`:

```python

def test_load_settings_reads_llm_and_narrative_sections(monkeypatch, tmp_path):
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
  timeout_seconds: 45
narrative:
  pdf_cache_dir: data/pdf_cache
  max_section_chars: 12000
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
    monkeypatch.setenv("ASCEND_API_KEY", "ascend-key-for-test")

    settings = load_settings(config_path)

    assert settings.llm.base_url == "https://maas.example.com/v1"
    assert settings.llm.model == "ascend-test-model"
    assert settings.llm.api_key == "ascend-key-for-test"
    assert settings.llm.timeout_seconds == 45
    assert settings.narrative.pdf_cache_dir == Path("data/pdf_cache")
    assert settings.narrative.max_section_chars == 12000
```

- [ ] **Step 2: Run the targeted config test and verify failure**

Run:

```bash
pytest tests/test_config.py::test_load_settings_reads_llm_and_narrative_sections -q
```

Expected: FAIL with `AttributeError` because `settings.llm` does not exist.

- [ ] **Step 3: Add dependencies**

Modify `pyproject.toml` dependencies to:

```toml
dependencies = [
    "fastapi>=0.111.0",
    "httpx>=0.27.0",
    "pandas>=2.2.0",
    "pydantic>=2.7.0",
    "pymupdf>=1.24.0",
    "pyyaml>=6.0.1",
    "python-dotenv>=1.0.1",
    "tushare>=1.4.21",
    "uvicorn>=0.30.0",
]
```

- [ ] **Step 4: Extend config file**

Modify `config.yaml` so it contains these additional sections:

```yaml
llm:
  base_url: https://maas.example.com/v1
  model: ascend-compatible-model
  timeout_seconds: 60

narrative:
  pdf_cache_dir: data/pdf_cache
  max_section_chars: 12000
```

Keep existing `database`, `tushare`, and `rules` sections unchanged.

- [ ] **Step 5: Extend typed settings**

Modify `copilot/config.py` to include these classes and fields:

```python
class LLMSettings(BaseModel):
    base_url: str
    model: str
    timeout_seconds: int = 60
    api_key: str | None = None


class NarrativeSettings(BaseModel):
    pdf_cache_dir: Path = Path("data/pdf_cache")
    max_section_chars: int = 12000


class Settings(BaseModel):
    database: DatabaseSettings
    tushare: TushareSettings = Field(default_factory=TushareSettings)
    llm: LLMSettings
    narrative: NarrativeSettings = Field(default_factory=NarrativeSettings)
    rules: RuleSettings = Field(default_factory=RuleSettings)
```

Update `load_settings()` to read the Ascend secret without printing it:

```python
def load_settings(path: str | Path = "config.yaml") -> Settings:
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    data.setdefault("tushare", {})["token"] = os.getenv("TUSHARE_TOKEN")
    data.setdefault("llm", {})["api_key"] = os.getenv("ASCEND_API_KEY")
    return Settings.model_validate(data)
```

- [ ] **Step 6: Run config tests and verify pass**

Run:

```bash
pytest tests/test_config.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml config.yaml copilot/config.py tests/test_config.py
git commit -m "feat: configure ascend narrative runtime"
```

---

### Task 2: Ascend-Compatible LLM Client

**Files:**
- Create: `copilot/llm/__init__.py`
- Create: `copilot/llm/client.py`
- Create: `tests/test_llm_client.py`

- [ ] **Step 1: Write failing LLM client tests**

Create `tests/test_llm_client.py`:

```python
import httpx

from copilot.llm.client import ChatMessage, LLMClient


def test_llm_client_posts_openai_compatible_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["json"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "归因文本"}}]},
        )

    client = LLMClient(
        base_url="https://maas.example.com/v1",
        model="ascend-model",
        api_key="secret-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.chat([ChatMessage(role="user", content="解释变化")])

    assert captured["url"] == "https://maas.example.com/v1/chat/completions"
    assert captured["authorization"] == "Bearer secret-key"
    assert '"model":"ascend-model"' in captured["json"].replace(" ", "")
    assert result == "归因文本"


def test_llm_client_returns_none_on_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    client = LLMClient(
        base_url="https://maas.example.com/v1",
        model="ascend-model",
        api_key="secret-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert client.chat([ChatMessage(role="user", content="解释变化")]) is None
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_llm_client.py -q
```

Expected: FAIL because `copilot.llm.client` does not exist.

- [ ] **Step 3: Implement the LLM adapter**

Create `copilot/llm/__init__.py`:

```python
"""LLM adapters."""
```

Create `copilot/llm/client.py`:

```python
from pydantic import BaseModel
import httpx


class ChatMessage(BaseModel):
    role: str
    content: str


class LLMClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None,
        timeout_seconds: int = 60,
        http_client: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client or httpx.Client(timeout=timeout_seconds)

    def chat(self, messages: list[ChatMessage], temperature: float = 0.2) -> str | None:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [message.model_dump() for message in messages],
            "temperature": temperature,
        }
        try:
            response = self.http_client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        data = response.json()
        return data["choices"][0]["message"]["content"]
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_llm_client.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/llm/__init__.py copilot/llm/client.py tests/test_llm_client.py
git commit -m "feat: add ascend compatible llm client"
```

---

### Task 3: PDF Management Section Extraction

**Files:**
- Create: `copilot/narrative/__init__.py`
- Create: `copilot/narrative/extract.py`
- Create: `tests/test_narrative_extract.py`

- [ ] **Step 1: Write failing extraction tests**

Create `tests/test_narrative_extract.py`:

```python
from copilot.narrative.extract import extract_management_section_from_text, pdf_cache_path


def test_pdf_cache_path_uses_ts_code_and_period(tmp_path):
    path = pdf_cache_path(tmp_path, "000001.SZ", "20250630")

    assert path == tmp_path / "000001.SZ_20250630.pdf"


def test_extract_management_section_from_text_prefers_management_discussion():
    text = "一、公司简介\n二、管理层讨论与分析\n经营承压但订单改善。\n三、公司治理\n治理内容"

    section = extract_management_section_from_text(text, max_chars=100)

    assert section == "二、管理层讨论与分析\n经营承压但订单改善。"


def test_extract_management_section_from_text_falls_back_to_future_outlook():
    text = "第一节 释义\n未来展望\n公司将提升现金回款。\n第十节 财务报告\n报表"

    section = extract_management_section_from_text(text, max_chars=100)

    assert section == "未来展望\n公司将提升现金回款。"


def test_extract_management_section_from_text_limits_chars():
    text = "管理层讨论与分析\n" + "经营" * 100

    section = extract_management_section_from_text(text, max_chars=12)

    assert section == "管理层讨论与分析\n经营"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_narrative_extract.py -q
```

Expected: FAIL because `copilot.narrative.extract` does not exist.

- [ ] **Step 3: Implement extraction helpers**

Create `copilot/narrative/__init__.py`:

```python
"""Narrative extraction and LLM analysis."""
```

Create `copilot/narrative/extract.py`:

```python
from pathlib import Path
import re

import fitz


_START_PATTERNS = [
    r"管理层讨论与分析",
    r"经营情况讨论与分析",
    r"未来展望",
    r"公司未来发展的展望",
]

_END_PATTERNS = [
    r"公司治理",
    r"重要事项",
    r"财务报告",
    r"第十节",
]


def pdf_cache_path(cache_dir: str | Path, ts_code: str, period: str) -> Path:
    return Path(cache_dir) / f"{ts_code}_{period}.pdf"


def extract_text_from_pdf(path: str | Path) -> str:
    document = fitz.open(path)
    try:
        return "\n".join(page.get_text("text") for page in document)
    finally:
        document.close()


def extract_management_section_from_text(text: str, max_chars: int) -> str | None:
    start_match = None
    for pattern in _START_PATTERNS:
        match = re.search(pattern, text)
        if match and (start_match is None or match.start() < start_match.start()):
            start_match = match
    if start_match is None:
        return None

    tail = text[start_match.start():]
    end_index = len(tail)
    for pattern in _END_PATTERNS:
        match = re.search(pattern, tail[start_match.end() - start_match.start():])
        if match:
            candidate = start_match.end() - start_match.start() + match.start()
            end_index = min(end_index, candidate)
    section = tail[:end_index].strip()
    return section[:max_chars]


def extract_management_section_from_pdf(path: str | Path, max_chars: int) -> str | None:
    if not Path(path).exists():
        return None
    return extract_management_section_from_text(extract_text_from_pdf(path), max_chars=max_chars)
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_narrative_extract.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/narrative/__init__.py copilot/narrative/extract.py tests/test_narrative_extract.py
git commit -m "feat: extract management discussion from pdf text"
```

---

### Task 4: Management Tone Comparison

**Files:**
- Create: `copilot/narrative/tone.py`
- Create: `tests/test_narrative_tone.py`

- [ ] **Step 1: Write failing tone tests**

Create `tests/test_narrative_tone.py`:

```python
from copilot.models import Severity
from copilot.narrative.tone import ToneComparisonResult, compare_management_tone


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.messages = None

    def chat(self, messages, temperature=0.2):
        self.messages = messages
        return self.response


def test_compare_management_tone_returns_finding_when_weakened():
    llm = FakeLLM('{"weakened": true, "reason": "从订单充足变为需求承压", "evidence": "需求承压"}')

    finding = compare_management_tone(
        llm,
        ts_code="000001.SZ",
        current_period="20250630",
        prior_period="20240630",
        current_text="需求承压，回款放缓。",
        prior_text="订单充足，增长稳健。",
    )

    assert finding is not None
    assert finding.rule_id == "management_tone_weakened"
    assert finding.severity == Severity.YELLOW
    assert "从订单充足变为需求承压" in finding.detail
    assert finding.evidence[0].source == "pdf.management_discussion"


def test_compare_management_tone_returns_none_when_not_weakened():
    llm = FakeLLM('{"weakened": false, "reason": "语气稳定", "evidence": "稳健"}')

    finding = compare_management_tone(
        llm,
        ts_code="000001.SZ",
        current_period="20250630",
        prior_period="20240630",
        current_text="经营稳健。",
        prior_text="经营稳健。",
    )

    assert finding is None


def test_compare_management_tone_returns_none_on_bad_llm_response():
    llm = FakeLLM("not-json")

    finding = compare_management_tone(
        llm,
        ts_code="000001.SZ",
        current_period="20250630",
        prior_period="20240630",
        current_text="需求承压。",
        prior_text="订单充足。",
    )

    assert finding is None
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_narrative_tone.py -q
```

Expected: FAIL because `copilot.narrative.tone` does not exist.

- [ ] **Step 3: Implement tone comparison**

Create `copilot/narrative/tone.py`:

```python
import json
from typing import Protocol

from pydantic import BaseModel, ValidationError

from copilot.llm.client import ChatMessage
from copilot.models import Evidence, Finding, Severity


class ToneComparisonResult(BaseModel):
    weakened: bool
    reason: str
    evidence: str


class ChatClient(Protocol):
    def chat(self, messages: list[ChatMessage], temperature: float = 0.2) -> str | None: ...


def _build_prompt(current_period: str, prior_period: str, current_text: str, prior_text: str) -> str:
    return (
        "你是买方研究员的财报措辞对比助手。只判断管理层语气是否转弱，不给投资建议。\n"
        "请输出严格 JSON：{\"weakened\": true/false, \"reason\": \"一句原因\", \"evidence\": \"原文中的短语\"}\n"
        f"上期报告期：{prior_period}\n{prior_text}\n\n"
        f"本期报告期：{current_period}\n{current_text}"
    )


def compare_management_tone(
    llm: ChatClient,
    ts_code: str,
    current_period: str,
    prior_period: str,
    current_text: str,
    prior_text: str,
) -> Finding | None:
    prompt = _build_prompt(current_period, prior_period, current_text, prior_text)
    content = llm.chat([ChatMessage(role="user", content=prompt)], temperature=0.0)
    if content is None:
        return None
    try:
        result = ToneComparisonResult.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValidationError):
        return None
    if not result.weakened:
        return None
    return Finding(
        rule_id="management_tone_weakened",
        severity=Severity.YELLOW,
        title="管理层展望语气退坡",
        detail=f"管理层措辞较上期转弱：{result.reason}",
        evidence=[
            Evidence(source="pdf.management_discussion", field="current_text", period=current_period, value=result.evidence),
            Evidence(source="pdf.management_discussion", field="prior_text", period=prior_period, value=prior_text[:120]),
        ],
        score=25.0,
    )
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_narrative_tone.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/narrative/tone.py tests/test_narrative_tone.py
git commit -m "feat: compare management tone with llm"
```

---

### Task 5: Report Card Builder

**Files:**
- Create: `copilot/report/__init__.py`
- Create: `copilot/report/builder.py`
- Create: `tests/test_report_builder.py`

- [ ] **Step 1: Write failing report builder tests**

Create `tests/test_report_builder.py`:

```python
from copilot.models import Context, Evidence, Finding, Severity
from copilot.report.builder import build_company_card, build_daily_summary


def finding(rule_id, severity, score):
    return Finding(
        rule_id=rule_id,
        severity=severity,
        title=rule_id,
        detail=f"{rule_id} detail",
        evidence=[Evidence(source="tushare.income", field="revenue", period="20250630", value=100.0)],
        score=score,
    )


def test_build_company_card_formats_four_layers(make_snapshot):
    ctx = Context(ts_code="000001.SZ", current=make_snapshot(revenue=128.4, net_profit=15.2, deducted_net_profit=11.8))

    card = build_company_card(ctx, [finding("cashflow_quality", Severity.YELLOW, 60.0)], attribution="增长来自收入改善。")

    assert card.ts_code == "000001.SZ"
    assert "营收 128.4" in card.fact_line
    assert card.findings[0].rule_id == "cashflow_quality"
    assert card.attribution == "增长来自收入改善。"
    assert card.market_line == "市场数据待接入"


def test_build_daily_summary_counts_severity(make_snapshot):
    ctx = Context(ts_code="000001.SZ", current=make_snapshot())
    cards = [
        build_company_card(ctx, [finding("red", Severity.RED, 80.0)]),
        build_company_card(Context(ts_code="000002.SZ", current=make_snapshot(ts_code="000002.SZ")), [finding("yellow", Severity.YELLOW, 30.0)]),
        build_company_card(Context(ts_code="000003.SZ", current=make_snapshot(ts_code="000003.SZ")), []),
    ]

    summary = build_daily_summary("20250821", coverage_count=42, cards=cards)

    assert summary.date == "20250821"
    assert summary.disclosed_count == 3
    assert summary.red_count == 1
    assert summary.yellow_count == 1
    assert summary.ok_count == 1
    assert summary.cards[0].max_score == 80.0
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_report_builder.py -q
```

Expected: FAIL because `copilot.report.builder` does not exist.

- [ ] **Step 3: Implement report builder**

Create `copilot/report/__init__.py`:

```python
"""Report assembly."""
```

Create `copilot/report/builder.py`:

```python
from pydantic import BaseModel

from copilot.models import Context, Finding, Severity


class CompanyCard(BaseModel):
    ts_code: str
    period: str
    fact_line: str
    findings: list[Finding]
    attribution: str | None = None
    market_line: str = "市场数据待接入"
    max_severity: Severity | None = None
    max_score: float = 0.0


class DailySummary(BaseModel):
    date: str
    coverage_count: int
    disclosed_count: int
    red_count: int
    yellow_count: int
    ok_count: int
    cards: list[CompanyCard]


def _num(value: float | None) -> str:
    return "NA" if value is None else f"{value:.1f}"


def _max_severity(findings: list[Finding]) -> Severity | None:
    severities = {finding.severity for finding in findings}
    if Severity.RED in severities:
        return Severity.RED
    if Severity.YELLOW in severities:
        return Severity.YELLOW
    if Severity.INFO in severities:
        return Severity.INFO
    return None


def build_company_card(ctx: Context, findings: list[Finding], attribution: str | None = None) -> CompanyCard:
    current = ctx.current
    ordered = sorted(findings, key=lambda finding: (-finding.score, finding.rule_id))
    fact_line = (
        f"营收 {_num(current.revenue)} | 净利 {_num(current.net_profit)} | "
        f"扣非净利 {_num(current.deducted_net_profit)} | 毛利率 {_num(current.gross_margin_pct)}% | "
        f"经营现金流 {_num(current.operating_cash_flow)}"
    )
    return CompanyCard(
        ts_code=ctx.ts_code,
        period=current.period,
        fact_line=fact_line,
        findings=ordered,
        attribution=attribution,
        max_severity=_max_severity(ordered),
        max_score=max((finding.score for finding in ordered), default=0.0),
    )


def build_daily_summary(date: str, coverage_count: int, cards: list[CompanyCard]) -> DailySummary:
    ordered_cards = sorted(cards, key=lambda card: (-card.max_score, card.ts_code))
    red_count = sum(1 for card in cards if card.max_severity == Severity.RED)
    yellow_count = sum(1 for card in cards if card.max_severity == Severity.YELLOW)
    ok_count = sum(1 for card in cards if card.max_severity is None)
    return DailySummary(
        date=date,
        coverage_count=coverage_count,
        disclosed_count=len(cards),
        red_count=red_count,
        yellow_count=yellow_count,
        ok_count=ok_count,
        cards=ordered_cards,
    )
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_report_builder.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/report/__init__.py copilot/report/builder.py tests/test_report_builder.py
git commit -m "feat: build auditable earnings report cards"
```

---

### Task 6: FastAPI Endpoints

**Files:**
- Create: `copilot/api/__init__.py`
- Create: `copilot/api/app.py`
- Create: `tests/test_api_app.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_api_app.py`:

```python
from fastapi.testclient import TestClient

from copilot.api.app import create_app
from copilot.models import Context, Evidence, Finding, Severity
from copilot.report.builder import build_company_card, build_daily_summary


class FakeReportService:
    def __init__(self, card, summary):
        self.card = card
        self.summary = summary

    def get_company_card(self, ts_code, period):
        return self.card

    def get_daily_summary(self, date):
        return self.summary

    def get_evidence(self, ts_code, period, rule_id):
        return self.card.findings[0].evidence


def test_company_card_endpoint(make_snapshot):
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
    client = TestClient(create_app(FakeReportService(card, summary)))

    response = client.get("/api/company/000001.SZ/20250630")

    assert response.status_code == 200
    assert response.json()["ts_code"] == "000001.SZ"
    assert response.json()["findings"][0]["rule_id"] == "cashflow_quality"


def test_daily_summary_endpoint(make_snapshot):
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    summary = build_daily_summary("20250821", 42, [card])
    client = TestClient(create_app(FakeReportService(card, summary)))

    response = client.get("/api/daily/20250821")

    assert response.status_code == 200
    assert response.json()["coverage_count"] == 42


def test_evidence_endpoint(make_snapshot):
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
    client = TestClient(create_app(FakeReportService(card, summary)))

    response = client.get("/api/evidence/000001.SZ/20250630/cashflow_quality")

    assert response.status_code == 200
    assert response.json()[0]["field"] == "operating_cash_flow"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_api_app.py -q
```

Expected: FAIL because `copilot.api.app` does not exist.

- [ ] **Step 3: Implement FastAPI app factory**

Create `copilot/api/__init__.py`:

```python
"""HTTP API."""
```

Create `copilot/api/app.py`:

```python
from typing import Protocol

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from copilot.models import Evidence
from copilot.report.builder import CompanyCard, DailySummary


class ReportService(Protocol):
    def get_company_card(self, ts_code: str, period: str) -> CompanyCard | None: ...

    def get_daily_summary(self, date: str) -> DailySummary | None: ...

    def get_evidence(self, ts_code: str, period: str, rule_id: str) -> list[Evidence]: ...


def create_app(report_service: ReportService) -> FastAPI:
    app = FastAPI(title="TradeEye Copilot")

    @app.get("/api/company/{ts_code}/{period}", response_model=CompanyCard)
    def company_card(ts_code: str, period: str):
        card = report_service.get_company_card(ts_code, period)
        if card is None:
            raise HTTPException(status_code=404, detail="company card not found")
        return card

    @app.get("/api/daily/{date}", response_model=DailySummary)
    def daily_summary(date: str):
        summary = report_service.get_daily_summary(date)
        if summary is None:
            raise HTTPException(status_code=404, detail="daily summary not found")
        return summary

    @app.get("/api/evidence/{ts_code}/{period}/{rule_id}", response_model=list[Evidence])
    def evidence(ts_code: str, period: str, rule_id: str):
        return report_service.get_evidence(ts_code, period, rule_id)

    app.mount("/", StaticFiles(directory="web", html=True), name="web")
    return app
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_api_app.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/api/__init__.py copilot/api/app.py tests/test_api_app.py
git commit -m "feat: expose report cards over fastapi"
```

---

### Task 7: Static Web Dashboard

**Files:**
- Create: `web/index.html`
- Create: `web/styles.css`
- Create: `web/app.js`

- [ ] **Step 1: Create dashboard HTML**

Create `web/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TradeEye Copilot</title>
  <link rel="stylesheet" href="/styles.css" />
</head>
<body>
  <main class="page">
    <section class="hero">
      <div>
        <p class="eyebrow">财报披露即时研判</p>
        <h1 id="summary-title">加载中...</h1>
        <p id="summary-line" class="summary-line"></p>
      </div>
      <input id="date-input" type="text" value="20250821" aria-label="披露日期" />
    </section>
    <section id="cards" class="cards"></section>
  </main>
  <dialog id="evidence-dialog">
    <h2>依据溯源</h2>
    <pre id="evidence-content"></pre>
    <button id="close-dialog">关闭</button>
  </dialog>
  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create dashboard styles**

Create `web/styles.css`:

```css
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f5f7fb;
  color: #172033;
}

.page {
  max-width: 1120px;
  margin: 0 auto;
  padding: 32px;
}

.hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #172033;
  color: white;
  border-radius: 18px;
  padding: 28px;
}

.eyebrow {
  color: #9fb5ff;
  margin: 0 0 8px;
}

.summary-line {
  color: #d8def0;
}

#date-input {
  border: 1px solid #44506a;
  border-radius: 10px;
  padding: 10px 12px;
  background: #101827;
  color: white;
}

.cards {
  display: grid;
  gap: 16px;
  margin-top: 24px;
}

.card {
  background: white;
  border-radius: 16px;
  padding: 20px;
  border: 1px solid #e3e7f0;
  box-shadow: 0 10px 30px rgba(23, 32, 51, 0.06);
}

.card.red {
  border-left: 6px solid #c62828;
}

.card.yellow {
  border-left: 6px solid #f9a825;
}

.card.ok {
  border-left: 6px solid #2e7d32;
}

.finding {
  margin: 10px 0;
  padding: 10px;
  background: #f8fafc;
  border-radius: 10px;
}

button {
  cursor: pointer;
  border: 0;
  border-radius: 8px;
  padding: 8px 10px;
  background: #244cff;
  color: white;
}

pre {
  white-space: pre-wrap;
}
```

- [ ] **Step 3: Create dashboard JavaScript**

Create `web/app.js`:

```javascript
const dateInput = document.querySelector("#date-input");
const title = document.querySelector("#summary-title");
const summaryLine = document.querySelector("#summary-line");
const cards = document.querySelector("#cards");
const dialog = document.querySelector("#evidence-dialog");
const evidenceContent = document.querySelector("#evidence-content");
const closeDialog = document.querySelector("#close-dialog");

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

async function loadDaily(date) {
  const response = await fetch(`/api/daily/${date}`);
  const summary = await response.json();
  title.textContent = `${summary.date} 财报研判 · 覆盖池 ${summary.coverage_count} 只`;
  summaryLine.textContent = `今日披露 ${summary.disclosed_count} 家 | 需优先关注 ${summary.red_count} | 留意 ${summary.yellow_count} | 未见异常 ${summary.ok_count}`;
  cards.innerHTML = "";
  for (const card of summary.cards) {
    cards.appendChild(renderCard(card));
  }
}

closeDialog.addEventListener("click", () => dialog.close());
dateInput.addEventListener("change", () => loadDaily(dateInput.value));
loadDaily(dateInput.value);
```

- [ ] **Step 4: Serve locally and smoke test**

Run:

```bash
uvicorn copilot.api.app:create_app --factory --reload
```

Expected: This command fails because `create_app` requires a `report_service`; do not commit this command as the final run command.

- [ ] **Step 5: Add explicit development app entrypoint**

Create `copilot/api/dev_app.py`:

```python
from copilot.api.app import create_app
from copilot.models import Context, Evidence, Finding, PeriodSnapshot, Severity
from copilot.report.builder import build_company_card, build_daily_summary


class DemoReportService:
    def __init__(self):
        snapshot = PeriodSnapshot(
            ts_code="000001.SZ",
            period="20250630",
            ann_date="20250821",
            revenue=128.4,
            net_profit=15.2,
            deducted_net_profit=11.8,
            gross_margin_pct=31.2,
            operating_cash_flow=4.1,
            accounts_receivable=47.0,
            inventory=20.0,
        )
        finding = Finding(
            rule_id="cashflow_quality",
            severity=Severity.YELLOW,
            title="现金流质量偏弱",
            detail="经营活动现金流净额/净利润 = 27.0%，低于 50.0%",
            evidence=[Evidence(source="tushare.cashflow", field="operating_cash_flow", period="20250630", value=4.1)],
            score=23.0,
        )
        self.card = build_company_card(Context(ts_code="000001.SZ", current=snapshot), [finding], attribution="增长主要来自收入改善，但现金回款未同步。")
        self.summary = build_daily_summary("20250821", 42, [self.card])

    def get_company_card(self, ts_code, period):
        if ts_code == self.card.ts_code and period == self.card.period:
            return self.card
        return None

    def get_daily_summary(self, date):
        if date == self.summary.date:
            return self.summary
        return None

    def get_evidence(self, ts_code, period, rule_id):
        for finding in self.card.findings:
            if finding.rule_id == rule_id:
                return finding.evidence
        return []


app = create_app(DemoReportService())
```

- [ ] **Step 6: Run dashboard smoke test**

Run:

```bash
uvicorn copilot.api.dev_app:app --reload
```

Expected: Server starts. Open `http://127.0.0.1:8000/` and see one demo company card; clicking `依据` opens JSON evidence. Stop with `Ctrl+C`.

- [ ] **Step 7: Commit**

```bash
git add web/index.html web/styles.css web/app.js copilot/api/dev_app.py
git commit -m "feat: add static earnings dashboard"
```

---

### Task 8: Full D5-D7 Verification

**Files:**
- No new files.

- [ ] **Step 1: Run narrative and API tests**

Run:

```bash
pytest tests/test_llm_client.py tests/test_narrative_extract.py tests/test_narrative_tone.py tests/test_report_builder.py tests/test_api_app.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full suite**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 3: Verify no secrets are committed**

Run:

```bash
git diff --cached -- . ':!*.md'
```

Expected: no real API keys, tokens, webhook URLs, or `.env` content appear.

- [ ] **Step 4: Commit any final fixes**

If Step 1 or Step 2 required fixes, stage only changed source and test files:

```bash
git add copilot tests web pyproject.toml config.yaml
git commit -m "test: verify narrative web pipeline"
```

Expected: If no files changed after prior commits, skip this commit.

---

## Definition of Done

- `pytest -q` passes after Plan A and this plan.
- `LLMClient` sends OpenAI-compatible `/chat/completions` requests to a configurable `base_url`.
- `ASCEND_API_KEY` is read only from environment variables and is never written to logs, config, tests, or docs.
- PDF extraction returns `None` when no cached PDF exists, so missing original text does not block report cards.
- Tone comparison emits a `Finding` only when the LLM returns valid JSON with `weakened: true`.
- API exposes `/api/daily/{date}`, `/api/company/{ts_code}/{period}`, and `/api/evidence/{ts_code}/{period}/{rule_id}`.
- Web dashboard renders summary counts, company cards, finding details, and evidence JSON.
- Arithmetic remains in Plan A core; browser and LLM code do not recalculate financial ratios.

## Self-Review Notes

Spec coverage for D5–D7 is complete: Ascend API path, PDF management-section extraction, LLM tone comparison, attribution-ready card assembly, FastAPI endpoints, Web dashboard, and evidence drill-down are represented. Feishu push, backtest benchmark, quarterly review, README finalization, and video are intentionally deferred to Plan C.
