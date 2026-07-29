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
        "receivable_revenue_divergence",
    ]
    assert findings[0].severity == findings[1].severity
    assert findings[0].score >= findings[1].score
