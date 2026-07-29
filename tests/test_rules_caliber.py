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
