# TradeEye Copilot Data Rules Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the D1–D4 core: project skeleton, Tushare financial snapshots, SQLite persistence, Context assembly, hard reconciliation checks, plugin rule engine, and rule tests.

**Architecture:** Keep all arithmetic outside the LLM path. `datasource/` fetches and normalizes external data, `store/` persists raw snapshots and findings, `checks/` blocks unreliable cards, and `rules/` emits auditable `Finding` objects with `Evidence`. Tests use local fixtures and monkeypatched data providers so rules stay pure and deterministic.

**Tech Stack:** Python 3.11+, FastAPI-ready package layout, pandas, pydantic, PyYAML, python-dotenv, pytest, SQLite (`sqlite3`).

---

## File Structure

Create the backend first under `copilot/` and keep each file narrow:

- Create: `pyproject.toml` — package metadata and dependencies.
- Create: `README.md` — temporary developer quickstart for the core package.
- Create: `.env.example` — documents required secrets without real values.
- Modify: `.gitignore` — ensure `.env`, caches, local DBs are ignored.
- Create: `config.yaml` — non-secret runtime config: DB path, Tushare retry settings, rule thresholds.
- Create: `copilot/__init__.py` — package marker.
- Create: `copilot/config.py` — load YAML + environment variables into typed settings.
- Create: `copilot/models.py` — shared domain models: `PeriodSnapshot`, `Context`, `Evidence`, `Finding`, enums.
- Create: `copilot/datasource/__init__.py` — datasource package marker.
- Create: `copilot/datasource/fundamentals.py` — Tushare financial table fetch + normalization.
- Create: `copilot/datasource/calendar.py` — disclosure event fetch interface.
- Create: `copilot/store/__init__.py` — store package marker.
- Create: `copilot/store/sqlite.py` — schema init and snapshot/finding persistence.
- Create: `copilot/context.py` — assemble current / prior quarter / prior year snapshots.
- Create: `copilot/checks/__init__.py` — checks package marker.
- Create: `copilot/checks/reconcile.py` — completeness and arithmetic sanity checks.
- Create: `copilot/rules/__init__.py` — rules package marker.
- Create: `copilot/rules/base.py` — `Rule` protocol and helper functions.
- Create: `copilot/rules/divergence.py` — first five arithmetic divergence rules.
- Create: `copilot/rules/caliber.py` — non-recurring profit contribution rule.
- Create: `copilot/rules/registry.py` — rule registration and execution order.
- Create: `tests/conftest.py` — reusable snapshot fixtures.
- Create: `tests/test_config.py` — config loading tests.
- Create: `tests/test_store_sqlite.py` — persistence tests.
- Create: `tests/test_context.py` — context assembly tests.
- Create: `tests/test_reconcile.py` — hard-check tests.
- Create: `tests/test_rules_divergence.py` — rule unit tests.
- Create: `tests/test_rules_caliber.py` — non-recurring profit rule tests.
- Create: `tests/test_registry.py` — registry execution tests.

---

### Task 1: Project Skeleton and Local Config

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `.env.example`
- Modify: `.gitignore`
- Create: `config.yaml`
- Create: `copilot/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create package metadata**

Write `pyproject.toml`:

```toml
[project]
name = "tradeeye-copilot"
version = "0.1.0"
description = "A-share earnings disclosure anomaly copilot"
requires-python = ">=3.11"
dependencies = [
    "pandas>=2.2.0",
    "pydantic>=2.7.0",
    "pyyaml>=6.0.1",
    "python-dotenv>=1.0.1",
    "tushare>=1.4.21",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Create local quickstart**

Write `README.md`:

```markdown
# TradeEye Copilot

A 股财报披露即时研判系统。当前阶段先实现结构化财务快照、硬校验、异常规则引擎与可复核 Evidence。

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest -q
```

## Runtime secrets

Secrets are read from environment variables only. Do not commit `.env`.

- `TUSHARE_TOKEN`
- `ASCEND_API_KEY`
- `FEISHU_WEBHOOK`
```

- [ ] **Step 3: Document secret names only**

Write `.env.example`:

```dotenv
TUSHARE_TOKEN=
ASCEND_API_KEY=
FEISHU_WEBHOOK=
```

- [ ] **Step 4: Ignore local artifacts**

Replace `.gitignore` with:

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
*.pyc
*.sqlite
*.sqlite3
*.db
.DS_Store
```

- [ ] **Step 5: Create non-secret config**

Write `config.yaml`:

```yaml
database:
  path: data/tradeeye_copilot.sqlite

tushare:
  timeout_seconds: 30
  max_retries: 3

rules:
  thresholds:
    receivable_revenue_gap_pct: 30.0
    inventory_revenue_gap_pct: 30.0
    ocf_to_net_profit_pct: 50.0
    gross_margin_change_pct: 5.0
    non_recurring_profit_share_pct: 30.0
```

- [ ] **Step 6: Create package markers and fixture file**

Create `copilot/__init__.py`:

```python
"""TradeEye Copilot core package."""
```

Create `tests/conftest.py`:

```python
from copilot.models import PeriodSnapshot


def make_snapshot(**overrides):
    data = {
        "ts_code": "000001.SZ",
        "period": "20250630",
        "ann_date": "20250821",
        "revenue": 100.0,
        "net_profit": 10.0,
        "deducted_net_profit": 9.0,
        "gross_margin_pct": 30.0,
        "operating_cash_flow": 8.0,
        "accounts_receivable": 20.0,
        "inventory": 15.0,
    }
    data.update(overrides)
    return PeriodSnapshot(**data)
```

- [ ] **Step 7: Run skeleton smoke command**

Run:

```bash
python -m pytest -q
```

Expected: pytest runs with no collected tests or import errors.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml README.md .env.example .gitignore config.yaml copilot/__init__.py tests/conftest.py
git commit -m "chore: initialize TradeEye Copilot core package"
```

---

### Task 2: Typed Config Loader

**Files:**
- Create: `copilot/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Create `tests/test_config.py`:

```python
from pathlib import Path

from copilot.config import load_settings


def test_load_settings_reads_yaml_and_environment(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
tushare:
  timeout_seconds: 12
  max_retries: 2
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
    monkeypatch.setenv("TUSHARE_TOKEN", "token-for-test")

    settings = load_settings(config_path)

    assert settings.database.path == Path("tmp/app.sqlite")
    assert settings.tushare.token == "token-for-test"
    assert settings.tushare.timeout_seconds == 12
    assert settings.tushare.max_retries == 2
    assert settings.rules.thresholds.receivable_revenue_gap_pct == 25.0
    assert settings.rules.thresholds.non_recurring_profit_share_pct == 20.0


def test_load_settings_keeps_secret_optional_for_tests(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  path: tmp/app.sqlite
tushare:
  timeout_seconds: 12
  max_retries: 2
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
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)

    settings = load_settings(config_path)

    assert settings.tushare.token is None
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_config.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'copilot.config'`.

- [ ] **Step 3: Implement config loader**

Create `copilot/config.py`:

```python
from pathlib import Path
import os

import yaml
from pydantic import BaseModel, Field


class DatabaseSettings(BaseModel):
    path: Path


class TushareSettings(BaseModel):
    timeout_seconds: int = 30
    max_retries: int = 3
    token: str | None = None


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
    rules: RuleSettings = Field(default_factory=RuleSettings)


def load_settings(path: str | Path = "config.yaml") -> Settings:
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    data.setdefault("tushare", {})["token"] = os.getenv("TUSHARE_TOKEN")
    return Settings.model_validate(data)
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/config.py tests/test_config.py
git commit -m "feat: add typed runtime config loader"
```

---

### Task 3: Domain Models

**Files:**
- Create: `copilot/models.py`
- Modify: `tests/conftest.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/test_models.py`:

```python
from copilot.models import Context, Evidence, Finding, PeriodSnapshot, Severity


def test_period_snapshot_calculates_yoy_growth(make_snapshot):
    current = make_snapshot(revenue=130.0)
    prior_year = make_snapshot(period="20240630", revenue=100.0)

    assert current.growth_pct("revenue", prior_year) == 30.0


def test_period_snapshot_returns_none_when_base_is_zero(make_snapshot):
    current = make_snapshot(revenue=130.0)
    prior_year = make_snapshot(period="20240630", revenue=0.0)

    assert current.growth_pct("revenue", prior_year) is None


def test_finding_serializes_evidence(make_snapshot):
    finding = Finding(
        rule_id="receivable_revenue_divergence",
        severity=Severity.RED,
        title="应收账款增速背离",
        detail="应收账款 +47.0% vs 营收 +12.0%，背离 35.0pct",
        evidence=[Evidence(source="tushare.balancesheet", field="accounts_receivable", period="20250630", value=20.0)],
        score=80.0,
    )

    assert finding.model_dump()["evidence"][0]["field"] == "accounts_receivable"


def test_context_exposes_periods(make_snapshot):
    ctx = Context(
        ts_code="000001.SZ",
        current=make_snapshot(period="20250630"),
        prior_quarter=make_snapshot(period="20250331"),
        prior_year=make_snapshot(period="20240630"),
    )

    assert ctx.periods == ["20250630", "20250331", "20240630"]
```

- [ ] **Step 2: Update fixture to import future models**

Replace `tests/conftest.py` with:

```python
import pytest

from copilot.models import PeriodSnapshot


@pytest.fixture
def make_snapshot():
    def _make_snapshot(**overrides):
        data = {
            "ts_code": "000001.SZ",
            "period": "20250630",
            "ann_date": "20250821",
            "revenue": 100.0,
            "net_profit": 10.0,
            "deducted_net_profit": 9.0,
            "gross_margin_pct": 30.0,
            "operating_cash_flow": 8.0,
            "accounts_receivable": 20.0,
            "inventory": 15.0,
        }
        data.update(overrides)
        return PeriodSnapshot(**data)

    return _make_snapshot
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
pytest tests/test_models.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'copilot.models'`.

- [ ] **Step 4: Implement shared domain models**

Create `copilot/models.py`:

```python
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class Severity(StrEnum):
    RED = "RED"
    YELLOW = "YELLOW"
    INFO = "INFO"


class Evidence(BaseModel):
    source: str
    field: str
    period: str
    value: float | str


class Finding(BaseModel):
    rule_id: str
    severity: Severity
    title: str
    detail: str
    evidence: list[Evidence]
    score: float


class PeriodSnapshot(BaseModel):
    ts_code: str
    period: str
    ann_date: str | None = None
    revenue: float | None = None
    net_profit: float | None = None
    deducted_net_profit: float | None = None
    gross_margin_pct: float | None = None
    operating_cash_flow: float | None = None
    accounts_receivable: float | None = None
    inventory: float | None = None

    def value(self, field: str) -> float | None:
        raw = getattr(self, field)
        if raw is None:
            return None
        return float(raw)

    def growth_pct(self, field: str, base: "PeriodSnapshot") -> float | None:
        current_value = self.value(field)
        base_value = base.value(field)
        if current_value is None or base_value in (None, 0):
            return None
        return (current_value / base_value - 1.0) * 100.0

    def change_pct_points(self, field: str, base: "PeriodSnapshot") -> float | None:
        current_value = self.value(field)
        base_value = base.value(field)
        if current_value is None or base_value is None:
            return None
        return current_value - base_value


class Context(BaseModel):
    ts_code: str
    current: PeriodSnapshot
    prior_quarter: PeriodSnapshot | None = None
    prior_year: PeriodSnapshot | None = None
    metadata: dict[str, Any] = {}

    @property
    def periods(self) -> list[str]:
        values = [self.current.period]
        if self.prior_quarter is not None:
            values.append(self.prior_quarter.period)
        if self.prior_year is not None:
            values.append(self.prior_year.period)
        return values
```

- [ ] **Step 5: Run tests and verify pass**

Run:

```bash
pytest tests/test_models.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add copilot/models.py tests/conftest.py tests/test_models.py
git commit -m "feat: define financial context domain models"
```

---

### Task 4: SQLite Store

**Files:**
- Create: `copilot/store/__init__.py`
- Create: `copilot/store/sqlite.py`
- Create: `tests/test_store_sqlite.py`

- [ ] **Step 1: Write failing store tests**

Create `tests/test_store_sqlite.py`:

```python
from copilot.models import Evidence, Finding, Severity
from copilot.store.sqlite import SQLiteStore


def test_store_round_trips_snapshot(make_snapshot, tmp_path):
    store = SQLiteStore(tmp_path / "app.sqlite")
    store.init_schema()
    snapshot = make_snapshot(period="20250630", revenue=123.0)

    store.upsert_snapshot(snapshot)
    loaded = store.get_snapshot("000001.SZ", "20250630")

    assert loaded == snapshot


def test_store_round_trips_findings(make_snapshot, tmp_path):
    store = SQLiteStore(tmp_path / "app.sqlite")
    store.init_schema()
    finding = Finding(
        rule_id="cashflow_quality",
        severity=Severity.YELLOW,
        title="现金流质量偏弱",
        detail="经营现金流/净利润 = 40.0%，低于 50.0%",
        evidence=[Evidence(source="tushare.cashflow", field="operating_cash_flow", period="20250630", value=4.0)],
        score=60.0,
    )

    store.replace_findings("000001.SZ", "20250630", [finding])
    loaded = store.list_findings("000001.SZ", "20250630")

    assert loaded == [finding]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_store_sqlite.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'copilot.store'`.

- [ ] **Step 3: Implement SQLite store**

Create `copilot/store/__init__.py`:

```python
"""Persistence adapters."""
```

Create `copilot/store/sqlite.py`:

```python
from pathlib import Path
import json
import sqlite3

from copilot.models import Finding, PeriodSnapshot


class SQLiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS financial_snapshots (
                    ts_code TEXT NOT NULL,
                    period TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (ts_code, period)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS findings (
                    ts_code TEXT NOT NULL,
                    period TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    score REAL NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (ts_code, period, rule_id)
                )
                """
            )

    def upsert_snapshot(self, snapshot: PeriodSnapshot) -> None:
        payload = snapshot.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO financial_snapshots (ts_code, period, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(ts_code, period) DO UPDATE SET payload = excluded.payload
                """,
                (snapshot.ts_code, snapshot.period, payload),
            )

    def get_snapshot(self, ts_code: str, period: str) -> PeriodSnapshot | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM financial_snapshots WHERE ts_code = ? AND period = ?",
                (ts_code, period),
            ).fetchone()
        if row is None:
            return None
        return PeriodSnapshot.model_validate_json(row["payload"])

    def replace_findings(self, ts_code: str, period: str, findings: list[Finding]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM findings WHERE ts_code = ? AND period = ?", (ts_code, period))
            conn.executemany(
                """
                INSERT INTO findings (ts_code, period, rule_id, severity, score, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        ts_code,
                        period,
                        finding.rule_id,
                        finding.severity.value,
                        finding.score,
                        finding.model_dump_json(),
                    )
                    for finding in findings
                ],
            )

    def list_findings(self, ts_code: str, period: str) -> list[Finding]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload FROM findings
                WHERE ts_code = ? AND period = ?
                ORDER BY score DESC, rule_id ASC
                """,
                (ts_code, period),
            ).fetchall()
        return [Finding.model_validate_json(row["payload"]) for row in rows]
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_store_sqlite.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/store/__init__.py copilot/store/sqlite.py tests/test_store_sqlite.py
git commit -m "feat: persist snapshots and findings in sqlite"
```

---

### Task 5: Tushare Financial Snapshot Adapter

**Files:**
- Create: `copilot/datasource/__init__.py`
- Create: `copilot/datasource/fundamentals.py`
- Create: `tests/test_fundamentals.py`

- [ ] **Step 1: Write failing normalization tests**

Create `tests/test_fundamentals.py`:

```python
import pandas as pd

from copilot.datasource.fundamentals import normalize_financial_snapshot


def test_normalize_financial_snapshot_combines_four_tables():
    income = pd.DataFrame([
        {"ts_code": "000001.SZ", "end_date": "20250630", "ann_date": "20250821", "revenue": 100.0, "n_income_attr_p": 10.0}
    ])
    balancesheet = pd.DataFrame([
        {"ts_code": "000001.SZ", "end_date": "20250630", "accounts_receiv": 20.0, "inventories": 15.0}
    ])
    cashflow = pd.DataFrame([
        {"ts_code": "000001.SZ", "end_date": "20250630", "n_cashflow_act": 8.0}
    ])
    indicator = pd.DataFrame([
        {"ts_code": "000001.SZ", "end_date": "20250630", "grossprofit_margin": 30.0, "profit_dedt": 9.0}
    ])

    snapshot = normalize_financial_snapshot("000001.SZ", "20250630", income, balancesheet, cashflow, indicator)

    assert snapshot.ts_code == "000001.SZ"
    assert snapshot.period == "20250630"
    assert snapshot.ann_date == "20250821"
    assert snapshot.revenue == 100.0
    assert snapshot.net_profit == 10.0
    assert snapshot.deducted_net_profit == 9.0
    assert snapshot.gross_margin_pct == 30.0
    assert snapshot.operating_cash_flow == 8.0
    assert snapshot.accounts_receivable == 20.0
    assert snapshot.inventory == 15.0


def test_normalize_financial_snapshot_keeps_missing_optional_fields_as_none():
    empty = pd.DataFrame()
    income = pd.DataFrame([
        {"ts_code": "000001.SZ", "end_date": "20250630", "ann_date": "20250821", "revenue": 100.0, "n_income_attr_p": 10.0}
    ])

    snapshot = normalize_financial_snapshot("000001.SZ", "20250630", income, empty, empty, empty)

    assert snapshot.accounts_receivable is None
    assert snapshot.inventory is None
    assert snapshot.operating_cash_flow is None
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_fundamentals.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'copilot.datasource'`.

- [ ] **Step 3: Implement normalization and fetch adapter**

Create `copilot/datasource/__init__.py`:

```python
"""External datasource adapters."""
```

Create `copilot/datasource/fundamentals.py`:

```python
from collections.abc import Callable
import time

import pandas as pd

from copilot.models import PeriodSnapshot


def _first_value(frame: pd.DataFrame, column: str):
    if frame.empty or column not in frame.columns:
        return None
    value = frame.iloc[0][column]
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def normalize_financial_snapshot(
    ts_code: str,
    period: str,
    income: pd.DataFrame,
    balancesheet: pd.DataFrame,
    cashflow: pd.DataFrame,
    indicator: pd.DataFrame,
) -> PeriodSnapshot:
    return PeriodSnapshot(
        ts_code=ts_code,
        period=period,
        ann_date=_first_value(income, "ann_date"),
        revenue=_first_value(income, "revenue"),
        net_profit=_first_value(income, "n_income_attr_p"),
        deducted_net_profit=_first_value(indicator, "profit_dedt"),
        gross_margin_pct=_first_value(indicator, "grossprofit_margin"),
        operating_cash_flow=_first_value(cashflow, "n_cashflow_act"),
        accounts_receivable=_first_value(balancesheet, "accounts_receiv"),
        inventory=_first_value(balancesheet, "inventories"),
    )


class TushareFundamentalsClient:
    def __init__(self, pro_api, max_retries: int = 3, sleep_seconds: float = 0.5):
        self.pro_api = pro_api
        self.max_retries = max_retries
        self.sleep_seconds = sleep_seconds

    def _call(self, fn: Callable, **kwargs) -> pd.DataFrame:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                result = fn(**kwargs)
                return result if result is not None else pd.DataFrame()
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    time.sleep(self.sleep_seconds * (2 ** attempt))
        raise RuntimeError(f"tushare call failed after {self.max_retries} attempts") from last_error

    def fetch_snapshot(self, ts_code: str, period: str) -> PeriodSnapshot:
        params = {"ts_code": ts_code, "period": period}
        income = self._call(self.pro_api.income, **params)
        balancesheet = self._call(self.pro_api.balancesheet, **params)
        cashflow = self._call(self.pro_api.cashflow, **params)
        indicator = self._call(self.pro_api.fina_indicator, **params)
        return normalize_financial_snapshot(ts_code, period, income, balancesheet, cashflow, indicator)
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_fundamentals.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/datasource/__init__.py copilot/datasource/fundamentals.py tests/test_fundamentals.py
git commit -m "feat: normalize tushare financial snapshots"
```

---

### Task 6: Disclosure Calendar Adapter

**Files:**
- Create: `copilot/datasource/calendar.py`
- Create: `tests/test_calendar.py`

- [ ] **Step 1: Write failing disclosure calendar tests**

Create `tests/test_calendar.py`:

```python
import pandas as pd

from copilot.datasource.calendar import DisclosureEvent, normalize_disclosure_events


def test_normalize_disclosure_events_filters_to_coverage_pool():
    frame = pd.DataFrame([
        {"ts_code": "000001.SZ", "ann_date": "20250821", "end_date": "20250630", "pre_date": "20250820"},
        {"ts_code": "600000.SH", "ann_date": "20250821", "end_date": "20250630", "pre_date": "20250820"},
    ])

    events = normalize_disclosure_events(frame, coverage_pool={"000001.SZ"})

    assert events == [DisclosureEvent(ts_code="000001.SZ", ann_date="20250821", period="20250630")]


def test_normalize_disclosure_events_uses_pre_date_when_ann_date_missing():
    frame = pd.DataFrame([
        {"ts_code": "000001.SZ", "ann_date": None, "end_date": "20250630", "pre_date": "20250820"},
    ])

    events = normalize_disclosure_events(frame, coverage_pool={"000001.SZ"})

    assert events[0].ann_date == "20250820"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_calendar.py -q
```

Expected: FAIL because `copilot.datasource.calendar` does not exist.

- [ ] **Step 3: Implement disclosure event normalization**

Create `copilot/datasource/calendar.py`:

```python
from pydantic import BaseModel
import pandas as pd


class DisclosureEvent(BaseModel):
    ts_code: str
    ann_date: str
    period: str


def _clean_date(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(value)


def normalize_disclosure_events(frame: pd.DataFrame, coverage_pool: set[str]) -> list[DisclosureEvent]:
    events: list[DisclosureEvent] = []
    for _, row in frame.iterrows():
        ts_code = str(row["ts_code"])
        if ts_code not in coverage_pool:
            continue
        ann_date = _clean_date(row.get("ann_date")) or _clean_date(row.get("pre_date"))
        period = _clean_date(row.get("end_date"))
        if ann_date is None or period is None:
            continue
        events.append(DisclosureEvent(ts_code=ts_code, ann_date=ann_date, period=period))
    return events


class TushareDisclosureCalendarClient:
    def __init__(self, pro_api):
        self.pro_api = pro_api

    def fetch_events(self, date: str, coverage_pool: set[str]) -> list[DisclosureEvent]:
        frame = self.pro_api.disclosure_date(ann_date=date)
        if frame is None:
            frame = pd.DataFrame()
        return normalize_disclosure_events(frame, coverage_pool)
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_calendar.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/datasource/calendar.py tests/test_calendar.py
git commit -m "feat: normalize disclosure calendar events"
```

---

### Task 7: Context Assembly

**Files:**
- Create: `copilot/context.py`
- Create: `tests/test_context.py`

- [ ] **Step 1: Write failing Context assembly tests**

Create `tests/test_context.py`:

```python
from copilot.context import assemble_context, prior_quarter_period, prior_year_period


class FakeSnapshotSource:
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def get_snapshot(self, ts_code, period):
        return self.snapshots.get((ts_code, period))


def test_prior_period_helpers():
    assert prior_quarter_period("20250630") == "20250331"
    assert prior_quarter_period("20250331") == "20241231"
    assert prior_year_period("20250630") == "20240630"


def test_assemble_context_loads_current_prior_quarter_and_prior_year(make_snapshot):
    source = FakeSnapshotSource({
        ("000001.SZ", "20250630"): make_snapshot(period="20250630"),
        ("000001.SZ", "20250331"): make_snapshot(period="20250331"),
        ("000001.SZ", "20240630"): make_snapshot(period="20240630"),
    })

    ctx = assemble_context(source, "000001.SZ", "20250630")

    assert ctx.current.period == "20250630"
    assert ctx.prior_quarter.period == "20250331"
    assert ctx.prior_year.period == "20240630"


def test_assemble_context_requires_current_snapshot(make_snapshot):
    source = FakeSnapshotSource({})

    try:
        assemble_context(source, "000001.SZ", "20250630")
    except ValueError as exc:
        assert "current snapshot missing" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_context.py -q
```

Expected: FAIL because `copilot.context` does not exist.

- [ ] **Step 3: Implement Context assembly**

Create `copilot/context.py`:

```python
from typing import Protocol

from copilot.models import Context, PeriodSnapshot


class SnapshotSource(Protocol):
    def get_snapshot(self, ts_code: str, period: str) -> PeriodSnapshot | None: ...


_QUARTER_ENDS = ["0331", "0630", "0930", "1231"]


def prior_quarter_period(period: str) -> str:
    year = int(period[:4])
    suffix = period[4:]
    index = _QUARTER_ENDS.index(suffix)
    if index == 0:
        return f"{year - 1}1231"
    return f"{year}{_QUARTER_ENDS[index - 1]}"


def prior_year_period(period: str) -> str:
    return f"{int(period[:4]) - 1}{period[4:]}"


def assemble_context(source: SnapshotSource, ts_code: str, period: str) -> Context:
    current = source.get_snapshot(ts_code, period)
    if current is None:
        raise ValueError(f"current snapshot missing: {ts_code} {period}")
    return Context(
        ts_code=ts_code,
        current=current,
        prior_quarter=source.get_snapshot(ts_code, prior_quarter_period(period)),
        prior_year=source.get_snapshot(ts_code, prior_year_period(period)),
    )
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_context.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/context.py tests/test_context.py
git commit -m "feat: assemble financial comparison context"
```

---

### Task 8: Hard Reconciliation Checks

**Files:**
- Create: `copilot/checks/__init__.py`
- Create: `copilot/checks/reconcile.py`
- Create: `tests/test_reconcile.py`

- [ ] **Step 1: Write failing reconciliation tests**

Create `tests/test_reconcile.py`:

```python
from copilot.checks.reconcile import CheckStatus, run_hard_checks
from copilot.models import Context


def test_hard_checks_pass_for_complete_context(make_snapshot):
    ctx = Context(
        ts_code="000001.SZ",
        current=make_snapshot(),
        prior_quarter=make_snapshot(period="20250331"),
        prior_year=make_snapshot(period="20240630"),
    )

    result = run_hard_checks(ctx)

    assert result.status == CheckStatus.OK
    assert result.messages == []


def test_hard_checks_block_when_required_current_fields_missing(make_snapshot):
    ctx = Context(ts_code="000001.SZ", current=make_snapshot(revenue=None))

    result = run_hard_checks(ctx)

    assert result.status == CheckStatus.DATA_INCOMPLETE
    assert result.messages == ["current.revenue missing"]


def test_hard_checks_flag_negative_revenue(make_snapshot):
    ctx = Context(ts_code="000001.SZ", current=make_snapshot(revenue=-1.0))

    result = run_hard_checks(ctx)

    assert result.status == CheckStatus.RECONCILE_FAILED
    assert result.messages == ["current.revenue is negative"]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_reconcile.py -q
```

Expected: FAIL because `copilot.checks.reconcile` does not exist.

- [ ] **Step 3: Implement hard checks**

Create `copilot/checks/__init__.py`:

```python
"""Hard data quality checks."""
```

Create `copilot/checks/reconcile.py`:

```python
from enum import StrEnum
from pydantic import BaseModel

from copilot.models import Context


class CheckStatus(StrEnum):
    OK = "OK"
    DATA_INCOMPLETE = "DATA_INCOMPLETE"
    RECONCILE_FAILED = "RECONCILE_FAILED"


class CheckResult(BaseModel):
    status: CheckStatus
    messages: list[str]


_REQUIRED_CURRENT_FIELDS = [
    "revenue",
    "net_profit",
    "gross_margin_pct",
    "operating_cash_flow",
]


_NON_NEGATIVE_FIELDS = [
    "revenue",
    "accounts_receivable",
    "inventory",
]


def run_hard_checks(ctx: Context) -> CheckResult:
    messages: list[str] = []

    for field in _REQUIRED_CURRENT_FIELDS:
        if ctx.current.value(field) is None:
            messages.append(f"current.{field} missing")

    if messages:
        return CheckResult(status=CheckStatus.DATA_INCOMPLETE, messages=messages)

    for field in _NON_NEGATIVE_FIELDS:
        value = ctx.current.value(field)
        if value is not None and value < 0:
            messages.append(f"current.{field} is negative")

    if messages:
        return CheckResult(status=CheckStatus.RECONCILE_FAILED, messages=messages)

    return CheckResult(status=CheckStatus.OK, messages=[])
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_reconcile.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/checks/__init__.py copilot/checks/reconcile.py tests/test_reconcile.py
git commit -m "feat: block unreliable financial contexts"
```

---

### Task 9: Rule Protocol and Shared Helpers

**Files:**
- Create: `copilot/rules/__init__.py`
- Create: `copilot/rules/base.py`
- Create: `tests/test_rules_base.py`

- [ ] **Step 1: Write failing helper tests**

Create `tests/test_rules_base.py`:

```python
from copilot.models import Evidence
from copilot.rules.base import pct_gap, source_evidence


def test_pct_gap_returns_difference_when_both_values_exist():
    assert pct_gap(47.0, 12.0) == 35.0


def test_pct_gap_returns_none_when_either_value_missing():
    assert pct_gap(None, 12.0) is None
    assert pct_gap(47.0, None) is None


def test_source_evidence_builds_standard_evidence():
    evidence = source_evidence("tushare.income", "revenue", "20250630", 100.0)

    assert evidence == Evidence(source="tushare.income", field="revenue", period="20250630", value=100.0)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_rules_base.py -q
```

Expected: FAIL because `copilot.rules` does not exist.

- [ ] **Step 3: Implement rule base**

Create `copilot/rules/__init__.py`:

```python
"""Anomaly rules."""
```

Create `copilot/rules/base.py`:

```python
from typing import Protocol

from copilot.models import Context, Evidence, Finding


class Rule(Protocol):
    id: str

    def applies(self, ctx: Context) -> bool: ...

    def evaluate(self, ctx: Context) -> Finding | None: ...


def pct_gap(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def source_evidence(source: str, field: str, period: str, value: float | str | None) -> Evidence:
    return Evidence(source=source, field=field, period=period, value="missing" if value is None else value)
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_rules_base.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/rules/__init__.py copilot/rules/base.py tests/test_rules_base.py
git commit -m "feat: define plugin rule interface"
```

---

### Task 10: Divergence Rules

**Files:**
- Create: `copilot/rules/divergence.py`
- Create: `tests/test_rules_divergence.py`

- [ ] **Step 1: Write failing divergence rule tests**

Create `tests/test_rules_divergence.py`:

```python
from copilot.models import Context, Severity
from copilot.rules.divergence import (
    CashflowQualityRule,
    GrossMarginChangeRule,
    InventoryRevenueDivergenceRule,
    NetProfitRevenueDirectionRule,
    ReceivableRevenueDivergenceRule,
)


def ctx(make_snapshot, current, prior_year=None):
    return Context(
        ts_code="000001.SZ",
        current=make_snapshot(**current),
        prior_year=make_snapshot(period="20240630", **(prior_year or {})),
    )


def test_receivable_revenue_divergence_triggers(make_snapshot):
    rule = ReceivableRevenueDivergenceRule(threshold_pct=30.0)
    finding = rule.evaluate(ctx(
        make_snapshot,
        current={"revenue": 112.0, "accounts_receivable": 147.0},
        prior_year={"revenue": 100.0, "accounts_receivable": 100.0},
    ))

    assert finding is not None
    assert finding.severity == Severity.RED
    assert finding.score == 35.0
    assert "背离 35.0pct" in finding.detail


def test_receivable_revenue_divergence_ignores_below_threshold(make_snapshot):
    rule = ReceivableRevenueDivergenceRule(threshold_pct=30.0)

    finding = rule.evaluate(ctx(
        make_snapshot,
        current={"revenue": 120.0, "accounts_receivable": 140.0},
        prior_year={"revenue": 100.0, "accounts_receivable": 100.0},
    ))

    assert finding is None


def test_inventory_revenue_divergence_triggers(make_snapshot):
    rule = InventoryRevenueDivergenceRule(threshold_pct=30.0)
    finding = rule.evaluate(ctx(
        make_snapshot,
        current={"revenue": 110.0, "inventory": 150.0},
        prior_year={"revenue": 100.0, "inventory": 100.0},
    ))

    assert finding is not None
    assert finding.rule_id == "inventory_revenue_divergence"


def test_cashflow_quality_triggers(make_snapshot):
    rule = CashflowQualityRule(threshold_pct=50.0)
    finding = rule.evaluate(ctx(make_snapshot, current={"net_profit": 10.0, "operating_cash_flow": 4.0}))

    assert finding is not None
    assert finding.severity == Severity.YELLOW
    assert "40.0%" in finding.detail


def test_gross_margin_change_triggers_on_large_abs_change(make_snapshot):
    rule = GrossMarginChangeRule(threshold_pct=5.0)
    finding = rule.evaluate(ctx(
        make_snapshot,
        current={"gross_margin_pct": 24.0},
        prior_year={"gross_margin_pct": 30.0},
    ))

    assert finding is not None
    assert finding.severity == Severity.YELLOW
    assert "-6.0pct" in finding.detail


def test_profit_revenue_direction_divergence_triggers(make_snapshot):
    rule = NetProfitRevenueDirectionRule()
    finding = rule.evaluate(ctx(
        make_snapshot,
        current={"revenue": 110.0, "net_profit": 8.0},
        prior_year={"revenue": 100.0, "net_profit": 10.0},
    ))

    assert finding is not None
    assert finding.severity == Severity.RED
    assert "方向背离" in finding.title
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_rules_divergence.py -q
```

Expected: FAIL because `copilot.rules.divergence` does not exist.

- [ ] **Step 3: Implement divergence rules**

Create `copilot/rules/divergence.py`:

```python
from dataclasses import dataclass

from copilot.models import Context, Finding, Severity
from copilot.rules.base import pct_gap, source_evidence


def _fmt_pct(value: float) -> str:
    return f"{value:+.1f}%"


def _fmt_pct_plain(value: float) -> str:
    return f"{value:.1f}%"


@dataclass(frozen=True)
class ReceivableRevenueDivergenceRule:
    threshold_pct: float
    id: str = "receivable_revenue_divergence"

    def applies(self, ctx: Context) -> bool:
        return ctx.prior_year is not None

    def evaluate(self, ctx: Context) -> Finding | None:
        if not self.applies(ctx):
            return None
        receivable_yoy = ctx.current.growth_pct("accounts_receivable", ctx.prior_year)
        revenue_yoy = ctx.current.growth_pct("revenue", ctx.prior_year)
        gap = pct_gap(receivable_yoy, revenue_yoy)
        if gap is None or gap <= self.threshold_pct:
            return None
        return Finding(
            rule_id=self.id,
            severity=Severity.RED,
            title="应收账款增速背离",
            detail=f"应收账款 {_fmt_pct(receivable_yoy)} vs 营收 {_fmt_pct(revenue_yoy)}，背离 {gap:.1f}pct",
            evidence=[
                source_evidence("tushare.balancesheet", "accounts_receivable", ctx.current.period, ctx.current.accounts_receivable),
                source_evidence("tushare.balancesheet", "accounts_receivable", ctx.prior_year.period, ctx.prior_year.accounts_receivable),
                source_evidence("tushare.income", "revenue", ctx.current.period, ctx.current.revenue),
                source_evidence("tushare.income", "revenue", ctx.prior_year.period, ctx.prior_year.revenue),
            ],
            score=round(gap, 1),
        )


@dataclass(frozen=True)
class InventoryRevenueDivergenceRule:
    threshold_pct: float
    id: str = "inventory_revenue_divergence"

    def applies(self, ctx: Context) -> bool:
        return ctx.prior_year is not None

    def evaluate(self, ctx: Context) -> Finding | None:
        if not self.applies(ctx):
            return None
        inventory_yoy = ctx.current.growth_pct("inventory", ctx.prior_year)
        revenue_yoy = ctx.current.growth_pct("revenue", ctx.prior_year)
        gap = pct_gap(inventory_yoy, revenue_yoy)
        if gap is None or gap <= self.threshold_pct:
            return None
        return Finding(
            rule_id=self.id,
            severity=Severity.RED,
            title="存货增速背离",
            detail=f"存货 {_fmt_pct(inventory_yoy)} vs 营收 {_fmt_pct(revenue_yoy)}，背离 {gap:.1f}pct",
            evidence=[
                source_evidence("tushare.balancesheet", "inventory", ctx.current.period, ctx.current.inventory),
                source_evidence("tushare.balancesheet", "inventory", ctx.prior_year.period, ctx.prior_year.inventory),
                source_evidence("tushare.income", "revenue", ctx.current.period, ctx.current.revenue),
                source_evidence("tushare.income", "revenue", ctx.prior_year.period, ctx.prior_year.revenue),
            ],
            score=round(gap, 1),
        )


@dataclass(frozen=True)
class CashflowQualityRule:
    threshold_pct: float
    id: str = "cashflow_quality"

    def applies(self, ctx: Context) -> bool:
        return ctx.current.net_profit not in (None, 0) and ctx.current.operating_cash_flow is not None

    def evaluate(self, ctx: Context) -> Finding | None:
        if not self.applies(ctx):
            return None
        ratio = ctx.current.operating_cash_flow / ctx.current.net_profit * 100.0
        if ratio >= self.threshold_pct:
            return None
        score = self.threshold_pct - ratio
        return Finding(
            rule_id=self.id,
            severity=Severity.YELLOW,
            title="现金流质量偏弱",
            detail=f"经营活动现金流净额/净利润 = {_fmt_pct_plain(ratio)}，低于 {_fmt_pct_plain(self.threshold_pct)}",
            evidence=[
                source_evidence("tushare.cashflow", "operating_cash_flow", ctx.current.period, ctx.current.operating_cash_flow),
                source_evidence("tushare.income", "net_profit", ctx.current.period, ctx.current.net_profit),
            ],
            score=round(score, 1),
        )


@dataclass(frozen=True)
class GrossMarginChangeRule:
    threshold_pct: float
    id: str = "gross_margin_change"

    def applies(self, ctx: Context) -> bool:
        return ctx.prior_year is not None

    def evaluate(self, ctx: Context) -> Finding | None:
        if not self.applies(ctx):
            return None
        change = ctx.current.change_pct_points("gross_margin_pct", ctx.prior_year)
        if change is None or abs(change) <= self.threshold_pct:
            return None
        return Finding(
            rule_id=self.id,
            severity=Severity.YELLOW,
            title="毛利率异动",
            detail=f"毛利率同比变动 {change:+.1f}pct，超过阈值 {self.threshold_pct:.1f}pct",
            evidence=[
                source_evidence("tushare.fina_indicator", "gross_margin_pct", ctx.current.period, ctx.current.gross_margin_pct),
                source_evidence("tushare.fina_indicator", "gross_margin_pct", ctx.prior_year.period, ctx.prior_year.gross_margin_pct),
            ],
            score=round(abs(change), 1),
        )


@dataclass(frozen=True)
class NetProfitRevenueDirectionRule:
    id: str = "net_profit_revenue_direction"

    def applies(self, ctx: Context) -> bool:
        return ctx.prior_year is not None

    def evaluate(self, ctx: Context) -> Finding | None:
        if not self.applies(ctx):
            return None
        revenue_yoy = ctx.current.growth_pct("revenue", ctx.prior_year)
        net_profit_yoy = ctx.current.growth_pct("net_profit", ctx.prior_year)
        if revenue_yoy is None or net_profit_yoy is None:
            return None
        if revenue_yoy == 0 or net_profit_yoy == 0 or revenue_yoy * net_profit_yoy > 0:
            return None
        score = abs(revenue_yoy - net_profit_yoy)
        return Finding(
            rule_id=self.id,
            severity=Severity.RED,
            title="利润与营收方向背离",
            detail=f"营收 {_fmt_pct(revenue_yoy)}，净利润 {_fmt_pct(net_profit_yoy)}，方向背离",
            evidence=[
                source_evidence("tushare.income", "revenue", ctx.current.period, ctx.current.revenue),
                source_evidence("tushare.income", "revenue", ctx.prior_year.period, ctx.prior_year.revenue),
                source_evidence("tushare.income", "net_profit", ctx.current.period, ctx.current.net_profit),
                source_evidence("tushare.income", "net_profit", ctx.prior_year.period, ctx.prior_year.net_profit),
            ],
            score=round(score, 1),
        )
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_rules_divergence.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/rules/divergence.py tests/test_rules_divergence.py
git commit -m "feat: add arithmetic divergence rules"
```

---

### Task 11: Non-Recurring Profit Rule

**Files:**
- Create: `copilot/rules/caliber.py`
- Create: `tests/test_rules_caliber.py`

- [ ] **Step 1: Write failing caliber rule tests**

Create `tests/test_rules_caliber.py`:

```python
from copilot.models import Context, Severity
from copilot.rules.caliber import NonRecurringProfitShareRule


def test_non_recurring_profit_share_triggers(make_snapshot):
    rule = NonRecurringProfitShareRule(threshold_pct=30.0)
    ctx = Context(ts_code="000001.SZ", current=make_snapshot(net_profit=10.0, deducted_net_profit=6.0))

    finding = rule.evaluate(ctx)

    assert finding is not None
    assert finding.severity == Severity.YELLOW
    assert finding.score == 40.0
    assert "非经常性损益贡献 40.0%" in finding.detail


def test_non_recurring_profit_share_ignores_below_threshold(make_snapshot):
    rule = NonRecurringProfitShareRule(threshold_pct=30.0)
    ctx = Context(ts_code="000001.SZ", current=make_snapshot(net_profit=10.0, deducted_net_profit=8.0))

    assert rule.evaluate(ctx) is None


def test_non_recurring_profit_share_skips_zero_profit(make_snapshot):
    rule = NonRecurringProfitShareRule(threshold_pct=30.0)
    ctx = Context(ts_code="000001.SZ", current=make_snapshot(net_profit=0.0, deducted_net_profit=0.0))

    assert rule.evaluate(ctx) is None
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_rules_caliber.py -q
```

Expected: FAIL because `copilot.rules.caliber` does not exist.

- [ ] **Step 3: Implement caliber rule**

Create `copilot/rules/caliber.py`:

```python
from dataclasses import dataclass

from copilot.models import Context, Finding, Severity
from copilot.rules.base import source_evidence


@dataclass(frozen=True)
class NonRecurringProfitShareRule:
    threshold_pct: float
    id: str = "non_recurring_profit_share"

    def applies(self, ctx: Context) -> bool:
        return ctx.current.net_profit not in (None, 0) and ctx.current.deducted_net_profit is not None

    def evaluate(self, ctx: Context) -> Finding | None:
        if not self.applies(ctx):
            return None
        share = (ctx.current.net_profit - ctx.current.deducted_net_profit) / ctx.current.net_profit * 100.0
        if share <= self.threshold_pct:
            return None
        return Finding(
            rule_id=self.id,
            severity=Severity.YELLOW,
            title="非经常性损益占比偏高",
            detail=f"非经常性损益贡献 {share:.1f}%，超过阈值 {self.threshold_pct:.1f}%",
            evidence=[
                source_evidence("tushare.income", "net_profit", ctx.current.period, ctx.current.net_profit),
                source_evidence("tushare.fina_indicator", "deducted_net_profit", ctx.current.period, ctx.current.deducted_net_profit),
            ],
            score=round(share, 1),
        )
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_rules_caliber.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add copilot/rules/caliber.py tests/test_rules_caliber.py
git commit -m "feat: add non recurring profit rule"
```

---

### Task 12: Rule Registry and Core Pipeline Smoke Test

**Files:**
- Create: `copilot/rules/registry.py`
- Create: `tests/test_registry.py`

- [ ] **Step 1: Write failing registry tests**

Create `tests/test_registry.py`:

```python
from copilot.config import RuleThresholds
from copilot.models import Context
from copilot.rules.registry import build_rules, run_rules


def test_build_rules_contains_six_arithmetic_rules():
    rules = build_rules(RuleThresholds())

    assert [rule.id for rule in rules] == [
        "receivable_revenue_divergence",
        "inventory_revenue_divergence",
        "cashflow_quality",
        "gross_margin_change",
        "net_profit_revenue_direction",
        "non_recurring_profit_share",
    ]


def test_run_rules_sorts_findings_by_score_desc(make_snapshot):
    ctx = Context(
        ts_code="000001.SZ",
        current=make_snapshot(
            revenue=112.0,
            accounts_receivable=147.0,
            inventory=150.0,
            net_profit=10.0,
            operating_cash_flow=4.0,
            deducted_net_profit=6.0,
        ),
        prior_year=make_snapshot(period="20240630", revenue=100.0, accounts_receivable=100.0, inventory=100.0),
    )

    findings = run_rules(ctx, build_rules(RuleThresholds()))

    assert [finding.rule_id for finding in findings][:2] == [
        "inventory_revenue_divergence",
        "non_recurring_profit_share",
    ]
    assert findings[0].score >= findings[1].score
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_registry.py -q
```

Expected: FAIL because `copilot.rules.registry` does not exist.

- [ ] **Step 3: Implement registry**

Create `copilot/rules/registry.py`:

```python
from copilot.config import RuleThresholds
from copilot.models import Context, Finding
from copilot.rules.base import Rule
from copilot.rules.caliber import NonRecurringProfitShareRule
from copilot.rules.divergence import (
    CashflowQualityRule,
    GrossMarginChangeRule,
    InventoryRevenueDivergenceRule,
    NetProfitRevenueDirectionRule,
    ReceivableRevenueDivergenceRule,
)


def build_rules(thresholds: RuleThresholds) -> list[Rule]:
    return [
        ReceivableRevenueDivergenceRule(threshold_pct=thresholds.receivable_revenue_gap_pct),
        InventoryRevenueDivergenceRule(threshold_pct=thresholds.inventory_revenue_gap_pct),
        CashflowQualityRule(threshold_pct=thresholds.ocf_to_net_profit_pct),
        GrossMarginChangeRule(threshold_pct=thresholds.gross_margin_change_pct),
        NetProfitRevenueDirectionRule(),
        NonRecurringProfitShareRule(threshold_pct=thresholds.non_recurring_profit_share_pct),
    ]


def run_rules(ctx: Context, rules: list[Rule]) -> list[Finding]:
    findings = [finding for rule in rules if (finding := rule.evaluate(ctx)) is not None]
    return sorted(findings, key=lambda finding: (-finding.score, finding.rule_id))
```

- [ ] **Step 4: Run registry tests and verify pass**

Run:

```bash
pytest tests/test_registry.py -q
```

Expected: PASS.

- [ ] **Step 5: Run full core test suite**

Run:

```bash
pytest -q
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add copilot/rules/registry.py tests/test_registry.py
git commit -m "feat: register arithmetic anomaly rules"
```

---

## Definition of Done

- `pytest -q` passes.
- `config.yaml` contains thresholds for all six arithmetic rules.
- `.env.example` documents secret names but contains no secret values.
- `copilot.rules.registry.build_rules()` returns exactly six arithmetic rules.
- Every emitted `Finding` includes at least two `Evidence` records unless it is a single-period ratio rule.
- Hard checks return `DATA_INCOMPLETE` or `RECONCILE_FAILED` before rules run when current facts are unreliable.
- No LLM, PDF, Web, or Feishu code is introduced in this plan.

## Self-Review Notes

Spec coverage for D1–D4 is complete: skeleton, Tushare snapshot normalization, SQLite schema, Context, hard checks, rule protocol, five divergence rules, one caliber rule, unit tests, and config thresholds are all covered. The LLM tone rule is deliberately excluded and handled in Plan B. No placeholders remain in implementation steps.
