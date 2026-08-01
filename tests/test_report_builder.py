from copilot.models import (
    CardStatus,
    ClassificationResult,
    Context,
    Evidence,
    FactStatus,
    Finding,
    MappingStatus,
    RuleResult,
    RuleResultStatus,
    Severity,
)
from copilot.report.builder import CompanyCard, build_company_card, build_daily_summary


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


def test_legacy_company_card_data_keeps_new_fields_compatible():
    card = CompanyCard(
        ts_code="000001.SZ",
        period="20250630",
        fact_line="营收 128.4",
        findings=[],
    )

    assert card.facts == []
    assert card.rule_results == []
    assert card.card_status == CardStatus.OK


def test_company_card_serializes_structured_contract():
    classification = ClassificationResult(
        provider="tushare.stock_basic",
        provider_industry="银行",
        mapping_status=MappingStatus.MAPPED,
        rule_profile_id="bank_v1",
    )
    rule_result = RuleResult(
        rule_id="gross_margin_change",
        status=RuleResultStatus.MISS,
        required_fact_ids=["gross_margin_pct"],
    )
    card = CompanyCard(
        ts_code="000001.SZ",
        period="20250630",
        fact_line="营收 128.4",
        findings=[],
        classification=classification,
        facts=[],
        rule_results=[rule_result],
    )

    payload = card.model_dump()
    assert payload["classification"]["rule_profile_id"] == "bank_v1"
    assert payload["rule_results"][0]["status"] == "MISS"


def test_build_company_card_preserves_legacy_call_and_defaults_structured_fields(make_snapshot):
    ctx = Context(ts_code="000001.SZ", current=make_snapshot())

    card = build_company_card(ctx, [])

    assert card.facts == []
    assert card.rule_results == []
    assert card.card_status == CardStatus.OK


from pydantic import ValidationError
import pytest

from copilot.models import Fact, FactStatus
from copilot.report.builder import CompanyCard


def test_company_card_rejects_ok_with_invalid_fact():
    fact = Fact(
        fact_id="revenue",
        label="营业收入",
        period="20250630",
        status=FactStatus.INVALID,
        reason_code="HARD_CHECK_FAILED",
        reason="校验失败",
    )
    with pytest.raises(ValidationError):
        CompanyCard(
            ts_code="000001.SZ",
            period="20250630",
            fact_line="营收 NA",
            findings=[],
            facts=[fact],
        )


def test_company_card_accepts_partial_with_invalid_fact():
    fact = Fact(
        fact_id="revenue",
        label="营业收入",
        period="20250630",
        status=FactStatus.INVALID,
        reason_code="HARD_CHECK_FAILED",
        reason="校验失败",
    )
    card = CompanyCard(
        ts_code="000001.SZ",
        period="20250630",
        fact_line="营收 NA",
        findings=[],
        facts=[fact],
        card_status="PARTIAL",
    )
    assert card.card_status == "PARTIAL"


def test_company_card_allows_blocked_without_facts():
    card = CompanyCard(
        ts_code="000001.SZ",
        period="20250630",
        fact_line="",
        findings=[],
        card_status="BLOCKED",
    )
    assert card.facts == []
