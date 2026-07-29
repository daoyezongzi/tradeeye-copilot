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
