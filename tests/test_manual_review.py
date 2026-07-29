from copilot.eval.manual_review import ReviewLabel, compute_precision, load_review_labels


def test_compute_precision_uses_only_reviewed_findings():
    labels = [
        ReviewLabel(ts_code="000001.SZ", period="20250630", rule_id="a", label="TRUE"),
        ReviewLabel(ts_code="000002.SZ", period="20250630", rule_id="b", label="FALSE"),
        ReviewLabel(ts_code="000003.SZ", period="20250630", rule_id="c", label="UNREVIEWED"),
    ]

    result = compute_precision(labels)

    assert result.reviewed_count == 2
    assert result.true_positive_count == 1
    assert result.false_positive_count == 1
    assert result.precision_pct == 50.0


def test_load_review_labels_reads_csv(tmp_path):
    path = tmp_path / "review.csv"
    path.write_text(
        "ts_code,period,rule_id,label,notes\n000001.SZ,20250630,a,TRUE,ok\n",
        encoding="utf-8",
    )

    labels = load_review_labels(path)

    assert labels == [ReviewLabel(ts_code="000001.SZ", period="20250630", rule_id="a", label="TRUE", notes="ok")]
