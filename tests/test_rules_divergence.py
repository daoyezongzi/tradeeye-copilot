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
