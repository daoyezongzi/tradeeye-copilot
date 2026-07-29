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
