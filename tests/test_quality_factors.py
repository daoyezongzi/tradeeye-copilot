from copilot.models import Context, Evidence, Finding, RuleResult, RuleResultStatus, Severity
from copilot.quality.factors import FactorStatus, build_quality_factors, build_quality_overview
from copilot.report.builder import build_company_card


def _finding(rule_id: str, severity: Severity) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        title=rule_id,
        detail="detail",
        evidence=[Evidence(source="tushare.income", field="revenue", period="20250630", value=100.0)],
        score=1.0,
    )


def _rule_result(rule_id: str, status: RuleResultStatus) -> RuleResult:
    return RuleResult(rule_id=rule_id, status=status, required_fact_ids=[])


def test_quality_factors_map_rule_statuses(make_snapshot):
    ctx = Context(ts_code="000001.SZ", current=make_snapshot())

    factors = build_quality_factors(
        ctx,
        rule_results=[
            _rule_result("receivable_revenue_divergence", RuleResultStatus.MISS),
            _rule_result("cashflow_quality", RuleResultStatus.HIT),
            _rule_result("net_profit_revenue_direction", RuleResultStatus.HIT),
            _rule_result("gross_margin_change", RuleResultStatus.NOT_EVALUATED),
        ],
        findings=[
            _finding("cashflow_quality", Severity.YELLOW),
            _finding("net_profit_revenue_direction", Severity.RED),
        ],
    )

    by_id = {factor.factor_id: factor for factor in factors}
    assert by_id["revenue_realization_quality"].status == FactorStatus.NORMAL
    assert by_id["cashflow_quality"].status == FactorStatus.WATCH
    assert by_id["performance_direction_consistency"].status == FactorStatus.ANOMALY
    assert by_id["profitability_stability"].status == FactorStatus.NOT_EVALUATED
    assert by_id["cashflow_quality"].rule_ids == ["cashflow_quality"]
    assert by_id["cashflow_quality"].observations[0].label == "经营现金流/净利润"


def test_quality_factor_observations_use_readable_chinese_labels(make_snapshot):
    ctx = Context(
        ts_code="000001.SZ",
        current=make_snapshot(revenue=59.0, net_profit=65.5),
        prior_year=make_snapshot(period="20240630", revenue=100.0, net_profit=10.0),
    )

    factors = build_quality_factors(
        ctx,
        rule_results=[_rule_result("net_profit_revenue_direction", RuleResultStatus.HIT)],
        findings=[_finding("net_profit_revenue_direction", Severity.RED)],
    )

    factor = {item.factor_id: item for item in factors}["performance_direction_consistency"]
    assert factor.observations[0].label == "营收/净利润同比"
    assert factor.observations[0].value == "营收 -41.0% / 净利 +555.0%"
    assert "YoY" not in factor.observations[0].label


def test_quality_overview_counts_and_status(make_snapshot):
    ctx = Context(ts_code="000001.SZ", current=make_snapshot())
    factors = build_quality_factors(
        ctx,
        rule_results=[
            _rule_result("receivable_revenue_divergence", RuleResultStatus.MISS),
            _rule_result("cashflow_quality", RuleResultStatus.HIT),
            _rule_result("net_profit_revenue_direction", RuleResultStatus.HIT),
        ],
        findings=[
            _finding("cashflow_quality", Severity.YELLOW),
            _finding("net_profit_revenue_direction", Severity.RED),
        ],
    )

    overview = build_quality_overview(factors)

    assert overview.status == FactorStatus.ANOMALY
    assert overview.anomaly_count == 1
    assert overview.watch_count == 1
    assert overview.normal_count == 1
    assert overview.not_evaluated_count == 3
    assert "异常 1 项" in overview.summary
    assert "关注 1 项" in overview.summary


def test_build_company_card_includes_quality_factors(make_snapshot):
    ctx = Context(ts_code="000001.SZ", current=make_snapshot())
    rule_results = [
        _rule_result("receivable_revenue_divergence", RuleResultStatus.MISS),
        _rule_result("cashflow_quality", RuleResultStatus.HIT),
    ]

    card = build_company_card(ctx, [_finding("cashflow_quality", Severity.YELLOW)], rule_results=rule_results)

    assert len(card.quality_factors) == 6
    assert card.quality_overview.status == FactorStatus.WATCH
    assert card.quality_overview.watch_count == 1
    assert card.model_dump()["quality_factors"][0]["status"]
