from copilot.models import Context, Evidence, Finding, Severity


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
