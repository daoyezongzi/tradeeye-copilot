from copilot.eval.manual_review import ReviewLabel, compute_precision, compute_precision_breakdown, load_review_labels


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


def test_compute_precision_breakdown_groups_reviewed_findings():
    labels = [
        ReviewLabel(ts_code="000001.SZ", period="20250630", rule_id="cashflow_quality", label="TRUE", severity="RED", industry="bank"),
        ReviewLabel(ts_code="000002.SZ", period="20250630", rule_id="cashflow_quality", label="FALSE", severity="RED", industry="generic"),
        ReviewLabel(ts_code="000003.SZ", period="20250630", rule_id="gross_margin_change", label="TRUE", severity="YELLOW", industry="generic"),
        ReviewLabel(ts_code="000004.SZ", period="20250630", rule_id="gross_margin_change", label="UNREVIEWED", severity="YELLOW", industry="generic"),
    ]

    breakdown = compute_precision_breakdown(labels)

    assert breakdown.by_rule["cashflow_quality"].precision_pct == 50.0
    assert breakdown.by_rule["gross_margin_change"].precision_pct == 100.0
    assert breakdown.by_severity["RED"].reviewed_count == 2
    assert breakdown.by_severity["YELLOW"].true_positive_count == 1
    assert breakdown.by_industry["bank"].precision_pct == 100.0
    assert breakdown.by_industry["generic"].precision_pct == 50.0
