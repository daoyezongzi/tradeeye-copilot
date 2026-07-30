from copilot.models import Evidence, Finding, Severity
from copilot.notify.feishu import render_formal_disclosure_text
from copilot.report.builder import CompanyCard, DailySummary
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureScanEvent, build_scan_result


def finding(rule_id, severity, title, detail, score):
    return Finding(
        rule_id=rule_id,
        severity=severity,
        title=title,
        detail=detail,
        evidence=[Evidence(source="tushare", field="revenue", period="20250630", value=100.0)],
        score=score,
    )


def card(ts_code, severity, score):
    top = finding("cashflow_quality", severity, "现金流质量偏弱", "OCF/NP = 27.0%，低于 50.0%", score)
    return CompanyCard(
        ts_code=ts_code,
        period="20250630",
        fact_line="营收 100.0 | 净利 10.0 | 毛利率 30.0% | 经营现金流 2.7",
        findings=[top],
        max_severity=severity,
        max_score=score,
    )


def test_formal_summary_includes_all_abnormal_cards_and_skips_normal_details():
    red = card("603026.SH", Severity.RED, 90.0)
    yellow = card("600151.SH", Severity.YELLOW, 40.0)
    normal = CompanyCard(ts_code="600032.SH", period="20250630", fact_line="ok", findings=[], max_severity=None, max_score=0.0)
    summary = DailySummary(
        date="20250825",
        coverage_count=3,
        disclosed_count=3,
        red_count=1,
        yellow_count=1,
        ok_count=1,
        cards=[red, yellow, normal],
    )
    scan = build_scan_result(
        date="20250825",
        coverage_count=3,
        events=[
            DisclosureScanEvent(ts_code="603026.SH", period="20250630", status=CompanyAnalysisStatus.OK, message="ok", has_card=True, industry="generic"),
            DisclosureScanEvent(ts_code="600151.SH", period="20250630", status=CompanyAnalysisStatus.OK, message="ok", has_card=True, industry="generic"),
            DisclosureScanEvent(ts_code="600032.SH", period="20250630", status=CompanyAnalysisStatus.OK, message="ok", has_card=True, industry="generic"),
        ],
    )

    text = render_formal_disclosure_text(summary, scan, {"603026.SH": "石大胜华", "600151.SH": "航天机电"})

    assert "20250825 财报披露研判 · 覆盖池 3 家" in text
    assert "🔴 红色异常：1 家" in text
    assert "🟡 黄色异常：1 家" in text
    assert "【红色异常 · 1/1】" in text
    assert "603026.SH 石大胜华" in text
    assert "600151.SH 航天机电" in text
    assert "600032.SH" not in text
    assert "未见异常：1 家，不逐条展开" in text


def test_formal_summary_lists_data_problem_events():
    summary = DailySummary(date="20250825", coverage_count=2, disclosed_count=2, red_count=0, yellow_count=0, ok_count=1, cards=[])
    scan = build_scan_result(
        date="20250825",
        coverage_count=2,
        events=[
            DisclosureScanEvent(ts_code="000001.SZ", period="20250630", status=CompanyAnalysisStatus.DATA_NOT_READY, message="missing bank fields", has_card=False, industry="bank"),
            DisclosureScanEvent(ts_code="600000.SH", period="20250630", status=CompanyAnalysisStatus.ERROR, message="tushare timeout", has_card=False, industry="bank"),
        ],
    )

    text = render_formal_disclosure_text(summary, scan, {"000001.SZ": "平安银行", "600000.SH": "浦发银行"})

    assert "【数据问题 · 2】" in text
    assert "000001.SZ 平安银行 DATA_NOT_READY：missing bank fields" in text
    assert "600000.SH 浦发银行 ERROR：tushare timeout" in text
