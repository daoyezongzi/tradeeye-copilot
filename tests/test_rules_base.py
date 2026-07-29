from copilot.models import Evidence
from copilot.rules.base import pct_gap, source_evidence


def test_pct_gap_returns_difference_when_both_values_exist():
    assert pct_gap(47.0, 12.0) == 35.0


def test_pct_gap_returns_none_when_either_value_missing():
    assert pct_gap(None, 12.0) is None
    assert pct_gap(47.0, None) is None


def test_source_evidence_builds_standard_evidence():
    evidence = source_evidence("tushare.income", "revenue", "20250630", 100.0)

    assert evidence == Evidence(source="tushare.income", field="revenue", period="20250630", value=100.0)
