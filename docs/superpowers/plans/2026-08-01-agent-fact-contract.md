# Agent 事实输出接口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不修改现有前端的前提下，为 `CompanyCard` 增加带证据的结构化事实、行业分类和规则执行状态，供未来研判卡高亮与右侧 Agent 上下文使用。

**Architecture:** 保留现有 `CompanyCard` 的全部字段和展示逻辑，新增模型字段采用兼容默认值。由后端从 Tushare 公司基础资料读取外部行业标签，通过少量配置映射特殊 profile，未映射行业继续使用现有 generic 规则；事实对象由快照字段和确定性来源构建，规则结果同时保留 Finding 和完整执行状态。仅扩展后端 Python 模块和测试，不修改 `web/`。

**Tech Stack:** Python 3.11+, Pydantic v2, FastAPI, pandas, PyYAML, pytest, Tushare。

---

## 文件结构与职责

- Modify: `copilot/models.py` — 增加事实、证据、行业分类、规则状态和 Agent 上下文模型；保留现有领域模型。
- Modify: `copilot/report/builder.py` — 扩展 `CompanyCard`，从 `Context` 生成结构化事实和兼容 `fact_line`。
- Modify: `copilot/datasource/fundamentals.py` — 增加公司基础资料查询协议和 Tushare `stock_basic` 归一化结果。
- Modify: `copilot/industry.py` — 增加外部行业标签到内部 profile 的确定性映射；未映射返回 generic。
- Modify: `copilot/config.py` — 增加少量 `industry_profiles` 配置模型与默认值。
- Modify: `config.yaml` — 仅增加特殊行业标签映射示例/当前已确认映射，不改覆盖池语义。
- Modify: `copilot/service/analyzer.py` — 读取公司资料、解析 profile、构建结构化事实和规则结果；保持现有分析状态和前端兼容。
- Modify: `copilot/api/app.py` — 暴露新模型字段于现有 CompanyCard 响应；预留 Agent fact context 请求/响应模型，不实现对话业务。
- Modify: `tests/test_models.py` — 模型约束和序列化测试。
- Modify: `tests/test_report_builder.py` — 结构化事实和卡片状态测试。
- Modify: `tests/test_fundamentals.py` — 公司基础资料归一化与调用测试。
- Modify: `tests/test_industry_routing.py` — 映射、未映射和不可用状态测试。
- Modify: `tests/test_analyzer_service.py` — Analyzer 注入公司资料、generic fallback、部分事实和规则状态测试。
- Modify: `tests/test_api_analysis_routes.py` — CompanyCard 新字段 API 契约测试。
- Modify: `docs/development-log.md` — 完成后追加阶段归档、验证命令和结果。
- Do not modify: `web/` — 本阶段前端由前端同事处理。

---

### Task 1: 建立结构化模型契约

**Files:**
- Modify: `copilot/models.py`
- Modify: `copilot/report/builder.py`
- Test: `tests/test_models.py`
- Test: `tests/test_report_builder.py`

- [ ] **Step 1: 写失败测试，锁定新增枚举和证据约束**

在 `tests/test_models.py` 增加：

```python
import pytest
from pydantic import ValidationError

from copilot.models import (
    Fact,
    FactEvidence,
    FactStatus,
    RuleResult,
    RuleResultStatus,
)


def test_verified_fact_requires_matching_evidence():
    fact = Fact(
        fact_id="revenue",
        label="营业收入",
        value=128.4,
        unit="亿元",
        period="20250630",
        status=FactStatus.VERIFIED,
        evidence=FactEvidence(
            evidence_id="ev-revenue",
            source="tushare.income",
            field="revenue",
            period="20250630",
            value=128.4,
        ),
    )
    assert fact.status == FactStatus.VERIFIED

    with pytest.raises(ValidationError):
        Fact(
            fact_id="revenue",
            label="营业收入",
            value=128.4,
            unit="亿元",
            period="20250630",
            status=FactStatus.VERIFIED,
        )

    with pytest.raises(ValidationError):
        Fact(
            fact_id="revenue",
            label="营业收入",
            value=128.4,
            unit="亿元",
            period="20250630",
            status=FactStatus.VERIFIED,
            evidence=FactEvidence(
                evidence_id="ev-revenue",
                source="tushare.income",
                field="revenue",
                period="20240630",
                value=128.4,
            ),
        )


def test_unavailable_fact_requires_reason():
    with pytest.raises(ValidationError):
        Fact(
            fact_id="gross_margin_pct",
            label="毛利率",
            period="20250630",
            status=FactStatus.UNAVAILABLE,
        )

    fact = Fact(
        fact_id="gross_margin_pct",
        label="毛利率",
        period="20250630",
        status=FactStatus.UNAVAILABLE,
        reason_code="EMPTY_SOURCE_RESULT",
        reason="工具未返回该报告期字段",
    )
    assert fact.evidence is None


def test_rule_result_distinguishes_not_evaluated_from_miss():
    result = RuleResult(
        rule_id="gross_margin_change",
        status=RuleResultStatus.NOT_EVALUATED,
        required_fact_ids=["gross_margin_pct"],
        reason_code="REQUIRED_FACT_UNAVAILABLE",
        reason="required fact unavailable",
    )
    assert result.status != RuleResultStatus.MISS
```

- [ ] **Step 2: 运行模型测试确认失败**

Run:

```bash
python -m pytest tests/test_models.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `Fact`, `FactEvidence`, `FactStatus`, `RuleResult`, and `RuleResultStatus` are not defined.

- [ ] **Step 3: 实现模型和 Pydantic 校验**

在 `copilot/models.py` 保留现有类，并追加以下定义；使用 `model_validator` 校验事实状态：

```python
from enum import StrEnum
from pydantic import BaseModel, Field, model_validator


class MappingStatus(StrEnum):
    MAPPED = "MAPPED"
    UNMAPPED = "UNMAPPED"
    UNAVAILABLE = "UNAVAILABLE"
    CONFLICT = "CONFLICT"


class FactStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CompanyIdentity(BaseModel):
    ts_code: str
    name: str | None = None
    provider: str
    name_field: str | None = None
    retrieved_at: str | None = None


class ClassificationResult(BaseModel):
    provider: str
    provider_industry: str | None = None
    mapping_status: MappingStatus
    rule_profile_id: str = "generic"
    industry_field: str | None = None
    source_value: str | None = None
    retrieved_at: str | None = None


class FactEvidence(BaseModel):
    evidence_id: str
    source: str
    field: str
    period: str
    value: float | str


class Fact(BaseModel):
    fact_id: str
    label: str
    value: float | str | None = None
    unit: str | None = None
    period: str
    status: FactStatus
    evidence: FactEvidence | None = None
    reason_code: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_status(self):
        if self.status == FactStatus.VERIFIED:
            if self.value is None or self.evidence is None:
                raise ValueError("verified fact requires value and evidence")
            if self.evidence.period != self.period:
                raise ValueError("fact and evidence periods must match")
            if self.evidence.value != self.value:
                raise ValueError("fact and evidence values must match")
        elif self.status in {FactStatus.UNAVAILABLE, FactStatus.INVALID}:
            if not self.reason_code or not self.reason:
                raise ValueError("unavailable or invalid fact requires reason")
        return self


class RuleResultStatus(StrEnum):
    HIT = "HIT"
    MISS = "MISS"
    NOT_EVALUATED = "NOT_EVALUATED"
    BLOCKED = "BLOCKED"


class RuleResult(BaseModel):
    rule_id: str
    status: RuleResultStatus
    required_fact_ids: list[str] = Field(default_factory=list)
    related_fact_ids: list[str] = Field(default_factory=list)
    reason_code: str | None = None
    reason: str | None = None


class CardStatus(StrEnum):
    OK = "OK"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


class AgentFactContext(BaseModel):
    ts_code: str
    period: str
    fact_id: str | None = None
    rule_id: str | None = None
    evidence_id: str | None = None
```

- [ ] **Step 4: 扩展 CompanyCard，保持旧字段兼容**

在 `copilot/report/builder.py` 导入新模型和 `Field`，把 `CompanyCard` 追加为：

```python
class CompanyCard(BaseModel):
    ts_code: str
    period: str
    fact_line: str
    findings: list[Finding]
    attribution: str | None = None
    market_line: str = "市场数据待接入"
    max_severity: Severity | None = None
    max_score: float = 0.0
    company: CompanyIdentity | None = None
    classification: ClassificationResult | None = None
    card_status: CardStatus = CardStatus.OK
    facts: list[Fact] = Field(default_factory=list)
    rule_results: list[RuleResult] = Field(default_factory=list)
```

暂时保留 `build_company_card()` 的旧调用参数，并让默认构建返回空 `facts` / `rule_results`，后续 Analyzer 再传入结构化结果，避免一次改变所有调用者。

- [ ] **Step 5: 运行模型和报告构建测试**

Run:

```bash
python -m pytest tests/test_models.py tests/test_report_builder.py -q --basetemp=.pytest_tmp
```

Expected: PASS；现有 `fact_line` 断言继续通过，新增模型约束通过。

- [ ] **Step 6: Commit**

```bash
git add copilot/models.py copilot/report/builder.py tests/test_models.py tests/test_report_builder.py
git commit -m "feat: add structured Agent fact models"
```

---

### Task 2: 增加 Tushare 公司资料和行业 profile 映射

**Files:**
- Modify: `copilot/datasource/fundamentals.py`
- Modify: `copilot/industry.py`
- Modify: `copilot/config.py`
- Modify: `config.yaml`
- Test: `tests/test_fundamentals.py`
- Test: `tests/test_industry_routing.py`

- [ ] **Step 1: 写失败测试，锁定 Tushare 公司资料和映射行为**

在 `tests/test_fundamentals.py` 增加：

```python
import pandas as pd

from copilot.datasource.fundamentals import normalize_company_profile


def test_normalize_company_profile_reads_identity_and_industry():
    profile = normalize_company_profile(
        "600000.SH",
        pd.DataFrame([{"ts_code": "600000.SH", "name": "示例银行", "industry": "银行"}]),
    )

    assert profile.ts_code == "600000.SH"
    assert profile.name == "示例银行"
    assert profile.provider_industry == "银行"
    assert profile.source == "tushare.stock_basic"
```

在 `tests/test_industry_routing.py` 增加：

```python
from copilot.industry import resolve_classification
from copilot.models import MappingStatus


def test_known_provider_industry_maps_to_special_profile():
    result = resolve_classification(
        provider_industry="银行",
        industry_profiles={"银行": "bank_v1"},
    )
    assert result.mapping_status == MappingStatus.MAPPED
    assert result.rule_profile_id == "bank_v1"


def test_unknown_provider_industry_uses_generic_without_claiming_generic_industry():
    result = resolve_classification(
        provider_industry="新行业",
        industry_profiles={"银行": "bank_v1"},
    )
    assert result.mapping_status == MappingStatus.UNMAPPED
    assert result.rule_profile_id == "generic"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
python -m pytest tests/test_fundamentals.py tests/test_industry_routing.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because profile normalization and classification resolution are not defined.

- [ ] **Step 3: 实现公司 profile 归一化和 Tushare 查询**

在 `copilot/datasource/fundamentals.py` 增加：

```python
from copilot.models import CompanyIdentity
from pydantic import BaseModel


class CompanyProfile(BaseModel):
    identity: CompanyIdentity
    provider_industry: str | None = None
    source: str = "tushare.stock_basic"
    field: str = "industry"


def normalize_company_profile(ts_code: str, frame: pd.DataFrame) -> CompanyProfile:
    row = frame.iloc[0] if not frame.empty else None
    name = None if row is None else _first_value(frame, "name")
    industry = None if row is None else _first_value(frame, "industry")
    return CompanyProfile(
        identity=CompanyIdentity(
            ts_code=ts_code,
            name=name,
            provider="tushare.stock_basic",
            name_field="name" if name is not None else None,
        ),
        provider_industry=industry,
    )
```

在 `TushareFundamentalsClient` 增加：

```python
def fetch_company_profile(self, ts_code: str) -> CompanyProfile:
    frame = self._call(self.pro_api.stock_basic, ts_code=ts_code, fields="ts_code,name,industry")
    return normalize_company_profile(ts_code, frame)
```

如果调用返回空 DataFrame，返回 `provider_industry=None`，由 Analyzer 形成 `UNAVAILABLE` 分类；不要默认生成具体行业。

- [ ] **Step 4: 实现外部行业标签到 profile 的映射**

在 `copilot/industry.py` 增加：

```python
from copilot.models import ClassificationResult, MappingStatus


def resolve_classification(
    provider_industry: str | None,
    industry_profiles: dict[str, str],
) -> ClassificationResult:
    if provider_industry is None:
        return ClassificationResult(
            provider="tushare.stock_basic",
            mapping_status=MappingStatus.UNAVAILABLE,
            rule_profile_id="generic",
            industry_field="industry",
        )
    profile = industry_profiles.get(provider_industry)
    return ClassificationResult(
        provider="tushare.stock_basic",
        provider_industry=provider_industry,
        mapping_status=MappingStatus.MAPPED if profile else MappingStatus.UNMAPPED,
        rule_profile_id=profile or "generic",
        industry_field="industry",
        source_value=provider_industry,
    )
```

保留现有 `Industry` 和 `industry_for_ts_code()`，直到 Analyzer 完成迁移；不修改现有配置兼容路径。

- [ ] **Step 5: 增加配置字段和银行映射**

在 `copilot/config.py` 增加：

```python
class EvalSettings(BaseModel):
    # 现有字段保留
    industry_profiles: dict[str, str] = Field(default_factory=dict)
```

在 `config.yaml` 的 `eval` 下增加：

```yaml
  industry_profiles:
    银行: bank_v1
```

- [ ] **Step 6: 运行资料、映射和现有配置测试**

Run:

```bash
python -m pytest tests/test_fundamentals.py tests/test_industry_routing.py tests/test_config.py -q --basetemp=.pytest_tmp
```

Expected: PASS。

- [ ] **Step 7: Commit**

```bash
git add copilot/datasource/fundamentals.py copilot/industry.py copilot/config.py config.yaml tests/test_fundamentals.py tests/test_industry_routing.py
git commit -m "feat: resolve industry profiles from Tushare"
```

---

### Task 3: 构建卡片事实和规则执行状态

**Files:**
- Modify: `copilot/report/builder.py`
- Modify: `copilot/rules/registry.py`
- Modify: `copilot/rules/base.py`
- Test: `tests/test_report_builder.py`
- Test: `tests/test_rules_registry.py`

- [ ] **Step 1: 写失败测试，验证事实 evidence 和规则状态**

在 `tests/test_report_builder.py` 增加：

```python
from copilot.models import FactStatus, RuleResultStatus


def test_build_company_card_includes_verified_facts_with_evidence(make_snapshot):
    ctx = Context(ts_code="000001.SZ", current=make_snapshot(revenue=128.4))
    card = build_company_card(ctx, [], classification=None)

    revenue = next(item for item in card.facts if item.fact_id == "revenue")
    assert revenue.status == FactStatus.VERIFIED
    assert revenue.period == "20250630"
    assert revenue.evidence.source == "tushare.income"
    assert revenue.evidence.field == "revenue"
    assert revenue.evidence.value == 128.4


def test_missing_fact_is_unavailable_and_card_is_partial(make_snapshot):
    ctx = Context(ts_code="000001.SZ", current=make_snapshot(gross_margin_pct=None))
    card = build_company_card(ctx, [], classification=None)

    margin = next(item for item in card.facts if item.fact_id == "gross_margin_pct")
    assert margin.status == FactStatus.UNAVAILABLE
    assert card.card_status.value == "PARTIAL"
```

在 `tests/test_rules_registry.py` 新增：

```python
from copilot.models import RuleResultStatus


def test_missing_rule_inputs_are_not_evaluated(make_snapshot):
    ctx = Context(ts_code="000001.SZ", current=make_snapshot(gross_margin_pct=None))
    results = evaluate_rule_results(ctx, build_rules(RuleThresholds()))
    margin = next(item for item in results if item.rule_id == "gross_margin_change")
    assert margin.status == RuleResultStatus.NOT_EVALUATED
    assert margin.status != RuleResultStatus.MISS
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
python -m pytest tests/test_report_builder.py tests/test_rules_registry.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because `facts`, `classification`, `evaluate_rule_results`, and `rule_results` do not exist.

- [ ] **Step 3: 实现 Context 字段到 Fact 的确定性构建**

在 `copilot/report/builder.py` 增加固定字段规格：

```python
_FACT_SPECS = [
    ("revenue", "营业收入", "亿元", "tushare.income", "revenue"),
    ("net_profit", "净利润", "亿元", "tushare.income", "net_profit"),
    ("deducted_net_profit", "扣非净利润", "亿元", "tushare.fina_indicator", "deducted_net_profit"),
    ("gross_margin_pct", "毛利率", "%", "tushare.fina_indicator", "gross_margin_pct"),
    ("operating_cash_flow", "经营活动现金流", "亿元", "tushare.cashflow", "operating_cash_flow"),
]
```

实现 `build_facts(ctx)`：

```python
def build_facts(ctx: Context) -> list[Fact]:
    facts = []
    for fact_id, label, unit, source, field in _FACT_SPECS:
        value = getattr(ctx.current, field)
        if value is None:
            facts.append(
                Fact(
                    fact_id=fact_id,
                    label=label,
                    period=ctx.current.period,
                    status=FactStatus.UNAVAILABLE,
                    reason_code="EMPTY_SOURCE_RESULT",
                    reason=f"工具未返回 {ctx.current.period} 的 {label}",
                )
            )
            continue
        evidence_id = f"{ctx.ts_code}:{ctx.current.period}:{fact_id}"
        facts.append(
            Fact(
                fact_id=fact_id,
                label=label,
                value=float(value),
                unit=unit,
                period=ctx.current.period,
                status=FactStatus.VERIFIED,
                evidence=FactEvidence(
                    evidence_id=evidence_id,
                    source=source,
                    field=field,
                    period=ctx.current.period,
                    value=float(value),
                ),
            )
        )
    return facts
```

- [ ] **Step 4: 让规则声明输入依赖并生成 RuleResult**

在 `copilot/rules/base.py` 的 `Rule` protocol 增加：

```python
required_fact_ids: tuple[str, ...]
```

给现有规则类增加与计算实际一致的 `required_fact_ids`，例如毛利率规则使用 `("gross_margin_pct",)`，现金流规则使用 `("operating_cash_flow", "net_profit")`。在 `copilot/rules/registry.py` 增加：

```python
from copilot.models import FactStatus, RuleResult, RuleResultStatus


def evaluate_rule_results(ctx: Context, rules: list[Rule], facts: list[Fact] | None = None) -> list[RuleResult]:
    fact_map = {fact.fact_id: fact for fact in (facts or build_facts(ctx))}
    results = []
    for rule in rules:
        missing = [
            fact_id for fact_id in rule.required_fact_ids
            if fact_map.get(fact_id) is None or fact_map[fact_id].status != FactStatus.VERIFIED
        ]
        if missing:
            results.append(
                RuleResult(
                    rule_id=rule.id,
                    status=RuleResultStatus.NOT_EVALUATED,
                    required_fact_ids=list(rule.required_fact_ids),
                    related_fact_ids=missing,
                    reason_code="REQUIRED_FACT_UNAVAILABLE",
                    reason="；".join(missing),
                )
            )
            continue
        finding = rule.evaluate(ctx)
        results.append(
            RuleResult(
                rule_id=rule.id,
                status=RuleResultStatus.HIT if finding is not None else RuleResultStatus.MISS,
                required_fact_ids=list(rule.required_fact_ids),
            )
        )
    return results
```

`run_rules()` 继续返回已有 Finding 列表，以保持现有前端和调用者兼容；Analyzer 同时调用 `evaluate_rule_results()`。

- [ ] **Step 5: 扩展 build_company_card 参数并计算卡片状态**

将函数签名扩展为：

```python
def build_company_card(
    ctx: Context,
    findings: list[Finding],
    attribution: str | None = None,
    classification: ClassificationResult | None = None,
    rule_results: list[RuleResult] | None = None,
    company: CompanyIdentity | None = None,
) -> CompanyCard:
```

默认构建 `facts = build_facts(ctx)`。如果存在 `UNAVAILABLE` 或 `INVALID` 事实，状态为 `PARTIAL`；调用者在核心上下文缺失时传入 `BLOCKED`。不要删除旧 `fact_line`。

- [ ] **Step 6: 运行规则和报告测试**

Run:

```bash
python -m pytest tests/test_report_builder.py tests/test_rules_registry.py tests/test_rules_divergence.py tests/test_rules_caliber.py -q --basetemp=.pytest_tmp
```

Expected: PASS；已有 Finding 排序和异常规则测试继续通过，新规则状态测试通过。

- [ ] **Step 7: Commit**

```bash
git add copilot/report/builder.py copilot/rules/base.py copilot/rules/registry.py copilot/rules/divergence.py copilot/rules/caliber.py tests/test_report_builder.py tests/test_rules_registry.py
git commit -m "feat: expose fact and rule evaluation status"
```

---

### Task 4: 接入 Analyzer 与现有 API，保持前端不变

**Files:**
- Modify: `copilot/service/analyzer.py`
- Modify: `copilot/api/app.py`
- Modify: `tests/test_analyzer_service.py`
- Modify: `tests/test_api_analysis_routes.py`

- [ ] **Step 1: 写失败测试，验证 Analyzer 产出新字段和 generic fallback**

在 `tests/test_analyzer_service.py` 给 FakeFundamentals 增加可选 `fetch_company_profile()`，并新增：

```python
from copilot.datasource.fundamentals import CompanyProfile
from copilot.models import CompanyIdentity


def test_analyze_company_attaches_classification_and_facts():
    current = snapshot(period="20250630")
    fundamentals = FakeFundamentals({
        ("000001.SZ", "20250630"): current,
        ("000001.SZ", "20250331"): snapshot(period="20250331"),
        ("000001.SZ", "20240630"): snapshot(period="20240630"),
    })
    fundamentals.company_profile = CompanyProfile(
        identity=CompanyIdentity(ts_code="000001.SZ", name="示例公司", provider="tushare.stock_basic"),
        provider_industry="新行业",
    )
    service = AnalyzerService(
        fundamentals=fundamentals,
        store=FakeStore(),
        industry_profiles={"银行": "bank_v1"},
    )

    result = service.analyze_company("000001.SZ", "20250630")

    assert result.card.classification.mapping_status.value == "UNMAPPED"
    assert result.card.classification.rule_profile_id == "generic"
    assert result.card.facts
    assert result.card.rule_results
```

在 `tests/test_api_analysis_routes.py` 新增响应断言：

```python
payload = response.json()
assert "facts" in payload
assert "classification" in payload
assert "rule_results" in payload
assert "fact_line" in payload
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
python -m pytest tests/test_analyzer_service.py tests/test_api_analysis_routes.py -q --basetemp=.pytest_tmp
```

Expected: FAIL because Analyzer does not fetch/attach classification and the constructor has no `industry_profiles` parameter.

- [ ] **Step 3: 扩展 FundamentalsProvider 协议和 Analyzer 构造参数**

在 `copilot/service/analyzer.py` 增加：

```python
from copilot.datasource.fundamentals import CompanyProfile
from copilot.industry import resolve_classification


class FundamentalsProvider(Protocol):
    def fetch_snapshot(self, ts_code: str, period: str) -> PeriodSnapshot: ...
    def fetch_company_profile(self, ts_code: str) -> CompanyProfile: ...
```

为 `AnalyzerService.__init__()` 增加：

```python
industry_profiles: dict[str, str] | None = None,
```

并设置：

```python
self.industry_profiles = industry_profiles or {}
```

为测试 FakeFundamentals 提供默认 `fetch_company_profile()` 返回空 `CompanyProfile`，保持原有测试场景可运行。

- [ ] **Step 4: 在分析流程中接入公司资料和分类**

在 `analyze_company()` 开始获取公司资料：

```python
profile = self.fundamentals.fetch_company_profile(ts_code)
classification = resolve_classification(profile.provider_industry, self.industry_profiles)
```

完成快照和 hard-check 后：

```python
facts = build_facts(ctx)
rule_results = evaluate_rule_results(ctx, build_rules(self.thresholds), facts=facts)
findings = run_rules(ctx, build_rules(self.thresholds))
card = build_company_card(
    ctx,
    findings,
    classification=classification,
    company=profile.identity,
    rule_results=rule_results,
)
```

如果 `fetch_company_profile()` 工具失败，不让错误身份替代财务分析；构造 `ClassificationResult(mapping_status=UNAVAILABLE, rule_profile_id="generic")`，继续通用规则。只有财务核心快照或 hard-check 失败时保留原有 `DATA_NOT_READY` / `DATA_INCOMPLETE` 结果。

对于本阶段的现有 bank 配置路径，可以先保留 `company_industries` 作为兼容 fallback，但新 Tushare profile 优先；不要移除旧参数导致现有调用失败。

- [ ] **Step 5: 注入真实 Tushare 客户端配置**

在 `copilot/api/real_app.py` 创建 `TushareFundamentalsClient` 后，将 `settings.eval.industry_profiles` 传给 `AnalyzerService`。不要修改 `web/`。

- [ ] **Step 6: 预留 API 上下文模型，不实现聊天接口**

在 `copilot/api/app.py` 从 `copilot.models` 导入 `AgentFactContext`，增加只用于契约复用的响应模型或注释性类型导出；不新增 `/api/chat`，不实现 Agent 自由文本生成。

现有 `GET /api/company/{ts_code}/{period}` 和扫描 bundle 因 `CompanyCard` 类型扩展自动返回新字段。保持所有旧路径不变。

- [ ] **Step 7: 运行 Analyzer 和 API 测试**

Run:

```bash
python -m pytest tests/test_analyzer_service.py tests/test_api_analysis_routes.py tests/test_api_disclosure_scan.py tests/test_disclosure_analysis_bundle.py -q --basetemp=.pytest_tmp
```

Expected: PASS；旧状态、Finding、Bundle 和 API 测试继续通过，新字段断言通过。

- [ ] **Step 8: Commit**

```bash
git add copilot/service/analyzer.py copilot/api/app.py copilot/api/real_app.py tests/test_analyzer_service.py tests/test_api_analysis_routes.py
 git commit -m "feat: attach structured facts to company analysis"
```

---

### Task 5: 兼容性、文档日志和最终验证

**Files:**
- Modify: `docs/development-log.md`
- Test: all existing tests
- Verify: `web/` unchanged

- [ ] **Step 1: 检查前端未被修改**

Run:

```bash
git diff --name-only HEAD~4..HEAD -- web
```

Expected: no output.

- [ ] **Step 2: 运行格式和全量测试**

Run:

```bash
git diff --check HEAD~4..HEAD
python -m pytest -q --basetemp=.pytest_tmp
```

Expected: `diff --check` 无输出；全量测试通过，测试总数以实际结果为准。

- [ ] **Step 3: 追加开发日志归档**

在 `docs/development-log.md` 顶部追加本阶段记录，包含：

```markdown
### 阶段归档：Agent 事实输出接口与行业分类预留

本阶段只扩展后端接口，不修改 `web/`。保留 `CompanyCard` 旧字段，新增结构化 `facts`、`classification`、`rule_results`、`card_status`，为研判卡事实高亮和右侧 Agent 上下文预留稳定标识。

- Tushare 公司基础资料提供外部行业标签；已配置标签映射到特殊 profile，未映射行业使用现有 generic 通用规则。
- 每个 `VERIFIED` 事实绑定报告期、工具来源、字段和原始值；缺失/无效事实不能生成 `MISS`，依赖规则为 `NOT_EVALUATED`。
- Agent 不参与数字计算、来源选择或规则判定；Agent 回答不进入研判卡高亮。
- 现有前端未修改，旧 `fact_line` 保留为兼容展示，结构化 `facts` 才是事实主数据。

验证：

```bash
python -m pytest -q --basetemp=.pytest_tmp
```

结果：

```text
<填入实际通过数量>
```
```

实际测试数量必须直接从命令输出记录，不能手填猜测；日志中应记录实际的 `N passed` 结果。

Run:

```bash
python -m pytest -q --basetemp=.pytest_tmp
 git diff --check
```

Expected: all tests pass and no whitespace errors.

- [ ] **Step 5: Commit**

```bash
git add docs/development-log.md
git commit -m "docs: archive Agent fact contract work"
```

- [ ] **Step 6: 生成交付报告**

报告必须列出：

- 设计文档提交号和路径；
- 实现计划路径；
- 实现提交号列表；
- 新增/修改的后端接口模型；
- Tushare 行业映射与 generic fallback 语义；
- `VERIFIED` / `UNAVAILABLE` / `INVALID` / `NOT_APPLICABLE` 和规则状态语义；
- 明确 `web/` 未修改；
- 最终测试命令与实际通过数量；
- 工作区剩余的用户原有 `D start_demo.bat` 状态。

---

## 计划自审

### Spec coverage

- CompanyCard 兼容扩展：Task 1、Task 4。
- 结构化事实与证据一致性：Task 1、Task 3。
- Tushare 公司身份/行业来源：Task 2、Task 4。
- 少量特殊映射与 generic fallback：Task 2、Task 4。
- `HIT` / `MISS` / `NOT_EVALUATED` / `BLOCKED`：Task 1、Task 3。
- 局部事实缺失和卡片状态：Task 3、Task 4。
- Agent 上下文预留、不实现对话：Task 1、Task 4。
- 前端不修改：Task 4、Task 5。
- 测试和日志归档：Task 1-5。

### Placeholder scan

已检查计划正文，没有 `TBD`、`TODO`、`FIXME` 或未定义的“适当处理”步骤。最终日志中的测试数量明确要求以实际命令输出填入，不构成实现占位符。

### Type consistency

- `Fact`, `FactEvidence`, `FactStatus`, `RuleResult`, `RuleResultStatus`, `CompanyIdentity`, `ClassificationResult`, `CardStatus` 先在 Task 1 定义，后续均按同名类型使用。
- `CompanyProfile` 在 Task 2 定义，Task 4 的 `FundamentalsProvider` 复用。
- `resolve_classification()` 在 Task 2 定义，Task 4 复用。
- `build_facts()` 在 Task 3 定义，Task 4 复用。
- `evaluate_rule_results()` 在 Task 3 定义，Task 4 复用。
- `CompanyCard` 新字段均使用兼容默认值，旧调用保持有效。

### Scope check

本计划只覆盖一个后端接口契约子项目，未包含前端改造、Agent 对话业务或 AI 审核器实现，范围适合单次执行。
