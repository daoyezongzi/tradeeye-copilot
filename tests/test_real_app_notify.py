from copilot.models import Finding, Severity
from copilot.notify.feishu import render_formal_disclosure_text
from copilot.report.builder import CompanyCard, DailySummary
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureScanEvent, build_scan_result


def test_formal_notify_text_combines_summary_and_scan():
    card = CompanyCard(
        ts_code="603026.SH",
        period="20250630",
        fact_line="fact",
        findings=[Finding(rule_id="x", severity=Severity.RED, title="异常", detail="证据", evidence=[], score=99.0)],
        max_severity=Severity.RED,
        max_score=99.0,
    )
    summary = DailySummary(date="20250825", coverage_count=2, disclosed_count=2, red_count=1, yellow_count=0, ok_count=0, cards=[card])
    scan = build_scan_result(
        date="20250825",
        coverage_count=2,
        events=[
            DisclosureScanEvent(ts_code="603026.SH", period="20250630", status=CompanyAnalysisStatus.OK, message="ok", has_card=True, industry="generic"),
            DisclosureScanEvent(ts_code="000001.SZ", period="20250630", status=CompanyAnalysisStatus.DATA_NOT_READY, message="missing", has_card=False, industry="bank"),
        ],
    )

    text = render_formal_disclosure_text(summary, scan, {"603026.SH": "石大胜华", "000001.SZ": "平安银行"})

    assert "603026.SH 石大胜华" in text
    assert "000001.SZ 平安银行 DATA_NOT_READY：missing" in text
