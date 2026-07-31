from copilot.service.review_store import ReviewLabelStore


def test_review_label_store_upserts_and_lists_labels(tmp_path):
    store = ReviewLabelStore(tmp_path / "reviews.sqlite")
    store.init_schema()

    first = store.upsert_label(
        ts_code="603026.SH",
        period="20250630",
        rule_id="cashflow_quality",
        label="FALSE",
        notes="误报，经营现金流季节性波动",
        severity="RED",
        industry="generic",
        reviewer="analyst-a",
    )
    second = store.upsert_label(
        ts_code="603026.SH",
        period="20250630",
        rule_id="cashflow_quality",
        label="TRUE",
        notes="确认异常",
        severity="RED",
        industry="generic",
        reviewer="analyst-b",
    )

    labels = store.list_labels(ts_code="603026.SH", period="20250630")

    assert first.updated_at <= second.updated_at
    assert len(labels) == 1
    assert labels[0].label == "TRUE"
    assert labels[0].notes == "确认异常"
    assert labels[0].reviewer == "analyst-b"
