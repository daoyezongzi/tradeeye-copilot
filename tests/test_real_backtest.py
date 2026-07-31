from copilot.eval.real_backtest import summarize_scan_counts
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureScanEvent, build_scan_result


def test_summarize_scan_counts_aggregates_multiple_days():
    day1 = build_scan_result(
        date="20250825",
        coverage_count=2,
        events=[
            DisclosureScanEvent(ts_code="603026.SH", period="20250630", status=CompanyAnalysisStatus.OK, message="ok", has_card=True, industry="generic"),
            DisclosureScanEvent(ts_code="000001.SZ", period="20250630", status=CompanyAnalysisStatus.ERROR, message="timeout", has_card=False, industry="bank"),
        ],
    )
    day2 = build_scan_result(
        date="20250826",
        coverage_count=2,
        events=[
            DisclosureScanEvent(ts_code="600151.SH", period="20250630", status=CompanyAnalysisStatus.DATA_NOT_READY, message="missing", has_card=False, industry="generic"),
        ],
    )

    summary = summarize_scan_counts([day1, day2])

    assert summary == {
        "days": 2,
        "disclosed_count": 3,
        "ok_count": 1,
        "data_not_ready_count": 1,
        "data_incomplete_count": 0,
        "error_count": 1,
    }
