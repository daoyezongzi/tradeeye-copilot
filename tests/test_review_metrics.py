from copilot.service.review_metrics import ReviewMetricsService
from copilot.service.review_store import ReviewLabelStore


def test_review_metrics_service_computes_precision_breakdown_from_store(tmp_path):
    store = ReviewLabelStore(tmp_path / "reviews.sqlite")
    store.upsert_label("603026.SH", "20250630", "cashflow_quality", "TRUE", severity="RED", industry="generic", reviewer="a")
    store.upsert_label("600000.SH", "20250630", "cashflow_quality", "FALSE", severity="RED", industry="bank", reviewer="b")
    store.upsert_label("000001.SZ", "20250630", "bank_asset_quality", "UNREVIEWED", severity="YELLOW", industry="bank", reviewer="c")

    metrics = ReviewMetricsService(store).compute_breakdown(period="20250630")

    assert metrics.overall.reviewed_count == 2
    assert metrics.overall.precision_pct == 50.0
    assert metrics.by_rule["cashflow_quality"].false_positive_count == 1
    assert metrics.by_severity["RED"].reviewed_count == 2
    assert metrics.by_industry["bank"].precision_pct == 0.0
