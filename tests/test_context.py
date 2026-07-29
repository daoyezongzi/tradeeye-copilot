from copilot.context import assemble_context, prior_quarter_period, prior_year_period


class FakeSnapshotSource:
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def get_snapshot(self, ts_code, period):
        return self.snapshots.get((ts_code, period))


def test_prior_period_helpers():
    assert prior_quarter_period("20250630") == "20250331"
    assert prior_quarter_period("20250331") == "20241231"
    assert prior_year_period("20250630") == "20240630"


def test_assemble_context_loads_current_prior_quarter_and_prior_year(make_snapshot):
    source = FakeSnapshotSource({
        ("000001.SZ", "20250630"): make_snapshot(period="20250630"),
        ("000001.SZ", "20250331"): make_snapshot(period="20250331"),
        ("000001.SZ", "20240630"): make_snapshot(period="20240630"),
    })

    ctx = assemble_context(source, "000001.SZ", "20250630")

    assert ctx.current.period == "20250630"
    assert ctx.prior_quarter.period == "20250331"
    assert ctx.prior_year.period == "20240630"


def test_assemble_context_requires_current_snapshot(make_snapshot):
    source = FakeSnapshotSource({})

    try:
        assemble_context(source, "000001.SZ", "20250630")
    except ValueError as exc:
        assert "current snapshot missing" in str(exc)
    else:
        raise AssertionError("expected ValueError")
