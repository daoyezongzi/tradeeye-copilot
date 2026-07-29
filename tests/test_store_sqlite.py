from copilot.models import Evidence, Finding, Severity
from copilot.store.sqlite import SQLiteStore


def test_store_round_trips_snapshot(make_snapshot, tmp_path):
    store = SQLiteStore(tmp_path / "app.sqlite")
    store.init_schema()
    snapshot = make_snapshot(period="20250630", revenue=123.0)

    store.upsert_snapshot(snapshot)
    loaded = store.get_snapshot("000001.SZ", "20250630")

    assert loaded == snapshot


def test_store_round_trips_findings(make_snapshot, tmp_path):
    store = SQLiteStore(tmp_path / "app.sqlite")
    store.init_schema()
    finding = Finding(
        rule_id="cashflow_quality",
        severity=Severity.YELLOW,
        title="现金流质量偏弱",
        detail="经营现金流/净利润 = 40.0%，低于 50.0%",
        evidence=[Evidence(source="tushare.cashflow", field="operating_cash_flow", period="20250630", value=4.0)],
        score=60.0,
    )

    store.replace_findings("000001.SZ", "20250630", [finding])
    loaded = store.list_findings("000001.SZ", "20250630")

    assert loaded == [finding]
