from copilot.checks.reconcile import CheckStatus, run_hard_checks
from copilot.industry import Industry
from copilot.models import Context, PeriodSnapshot


def test_bank_context_does_not_require_gross_margin_receivables_or_inventory():
    snapshot = PeriodSnapshot(
        ts_code="000001.SZ",
        period="20250630",
        revenue=100.0,
        net_profit=10.0,
        operating_cash_flow=8.0,
        gross_margin_pct=None,
        accounts_receivable=None,
        inventory=None,
    )
    ctx = Context(ts_code="000001.SZ", current=snapshot, metadata={"industry": Industry.BANK.value})

    result = run_hard_checks(ctx)

    assert result.status == CheckStatus.OK


def test_generic_context_still_requires_gross_margin():
    snapshot = PeriodSnapshot(
        ts_code="920056.BJ",
        period="20250630",
        revenue=100.0,
        net_profit=10.0,
        operating_cash_flow=8.0,
        gross_margin_pct=None,
        accounts_receivable=20.0,
        inventory=15.0,
    )
    ctx = Context(ts_code="920056.BJ", current=snapshot, metadata={"industry": Industry.GENERIC.value})

    result = run_hard_checks(ctx)

    assert result.status == CheckStatus.DATA_INCOMPLETE
    assert any("gross_margin_pct" in message for message in result.messages)
