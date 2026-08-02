from pydantic import ValidationError
import pytest

from copilot.models import (
    AgentFactContext,
    ClassificationResult,
    CompanyIdentity,
    Context,
    Evidence,
    Fact,
    FactEvidence,
    FactStatus,
    Finding,
    MappingStatus,
    RuleResult,
    RuleResultStatus,
    Severity,
)


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


def test_verified_fact_requires_matching_evidence():
    evidence = FactEvidence(
        evidence_id="ev-revenue",
        source="tushare.income",
        field="revenue",
        period="20250630",
        value=128.4,
    )
    fact = Fact(
        fact_id="revenue",
        label="营业收入",
        value=128.4,
        unit="亿元",
        period="20250630",
        status=FactStatus.VERIFIED,
        evidence=evidence,
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
            evidence=evidence.model_copy(update={"period": "20240630"}),
        )

    with pytest.raises(ValidationError):
        Fact(
            fact_id="revenue",
            label="营业收入",
            value=128.4,
            unit="亿元",
            period="20250630",
            status=FactStatus.VERIFIED,
            evidence=evidence.model_copy(update={"value": 127.0}),
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




def test_invalid_fact_requires_reason():
    with pytest.raises(ValidationError):
        Fact(
            fact_id="revenue",
            label="营业收入",
            period="20250630",
            status=FactStatus.INVALID,
        )


def test_not_applicable_fact_requires_special_profile():
    with pytest.raises(ValidationError):
        Fact(
            fact_id="gross_margin_pct",
            label="毛利率",
            period="20250630",
            status=FactStatus.NOT_APPLICABLE,
        )
    with pytest.raises(ValidationError):
        Fact(
            fact_id="gross_margin_pct",
            label="毛利率",
            period="20250630",
            status=FactStatus.NOT_APPLICABLE,
            applicability_profile_id="generic",
        )

    fact = Fact(
        fact_id="gross_margin_pct",
        label="毛利率",
        period="20250630",
        status=FactStatus.NOT_APPLICABLE,
        applicability_profile_id="bank_v1",
        reason_code="INDUSTRY_NOT_APPLICABLE",
        reason="bank_v1 未使用毛利率口径",
    )
    assert fact.applicability_profile_id == "bank_v1"


def test_identity_classification_and_agent_context_serialize():
    identity = CompanyIdentity(
        ts_code="600000.SH",
        name="示例银行",
        provider="tushare.stock_basic",
        name_field="name",
    )
    classification = ClassificationResult(
        provider="tushare.stock_basic",
        provider_industry="银行",
        mapping_status=MappingStatus.MAPPED,
        rule_profile_id="bank_v1",
        industry_field="industry",
        source_value="银行",
    )
    context = AgentFactContext(
        ts_code="600000.SH",
        period="20250630",
        fact_id="revenue",
        evidence_id="ev-revenue",
    )

    assert identity.model_dump()["provider"] == "tushare.stock_basic"
    assert classification.model_dump()["rule_profile_id"] == "bank_v1"
    assert context.model_dump()["fact_id"] == "revenue"
