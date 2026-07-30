from types import SimpleNamespace

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from copilot.api.app import create_app
from copilot.api.real_app import RealReportService
from copilot.config import RuleSettings
from copilot.models import PeriodSnapshot
from copilot.rss.service import RssPollService
from copilot.service.analyzer import AnalyzerService, CompanyAnalysisStatus


class ExplodingFundamentals:
    def fetch_snapshot(self, ts_code, period):
        raise RuntimeError("upstream unavailable")


class FakeStore:
    def upsert_snapshot(self, snapshot):
        raise AssertionError("not reached")

    def get_snapshot(self, ts_code, period):
        return None

    def replace_findings(self, ts_code, period, findings):
        raise AssertionError("not reached")


class MissingTokenService:
    def get_company_card(self, ts_code, period):
        return None

    def get_daily_summary(self, date):
        return None

    def get_evidence(self, ts_code, period, rule_id):
        return []

    def get_quarterly_review(self):
        return None

    def analyze_company(self, ts_code, period):
        raise HTTPException(status_code=503, detail="未配置 TUSHARE_TOKEN")

    def analyze_disclosure_day(self, date):
        raise HTTPException(status_code=503, detail="未配置 TUSHARE_TOKEN")

    def poll_rss(self):
        raise AssertionError("not used")

    def notify_feishu_disclosure_day(self, date):
        raise AssertionError("not used")


def test_analyze_company_converts_provider_exceptions_to_error_status():
    service = AnalyzerService(fundamentals=ExplodingFundamentals(), store=FakeStore())

    result = service.analyze_company("000001.SZ", "20250630")

    assert result.status == CompanyAnalysisStatus.ERROR
    assert "upstream unavailable" in result.message
    assert result.card is None


def test_real_report_service_raises_503_when_tushare_token_missing(monkeypatch, tmp_path):
    settings = SimpleNamespace(
        database=SimpleNamespace(path=tmp_path / "app.sqlite"),
        tushare=SimpleNamespace(token=None, max_retries=1),
        rules=RuleSettings(),
        eval=SimpleNamespace(coverage_pool=[], start_date="20250801", end_date="20250831"),
        rss=SimpleNamespace(feeds=[], max_entries=50),
    )
    monkeypatch.setattr("copilot.api.real_app.load_settings", lambda: settings)
    service = RealReportService()

    try:
        service.analyze_company("000001.SZ", "20250630")
    except HTTPException as exc:
        assert exc.status_code == 503
        assert exc.detail == "未配置 TUSHARE_TOKEN"
    else:
        raise AssertionError("expected HTTPException")

    try:
        service.analyze_disclosure_day("20250821")
    except HTTPException as exc:
        assert exc.status_code == 503
        assert exc.detail == "未配置 TUSHARE_TOKEN"
    else:
        raise AssertionError("expected HTTPException")

class PendingThenOkAnalyzer:
    def __init__(self):
        self.calls = 0

    def analyze_company(self, ts_code, period):
        self.calls += 1
        if self.calls == 1:
            from copilot.service.analyzer import CompanyAnalysisResult, CompanyAnalysisStatus

            return CompanyAnalysisResult(status=CompanyAnalysisStatus.DATA_NOT_READY, message="pending")
        from copilot.models import Context
        from copilot.report.builder import build_company_card
        from copilot.service.analyzer import CompanyAnalysisResult, CompanyAnalysisStatus

        snapshot = PeriodSnapshot(
            ts_code=ts_code,
            period=period,
            revenue=100.0,
            net_profit=10.0,
            deducted_net_profit=9.0,
            gross_margin_pct=30.0,
            operating_cash_flow=8.0,
            accounts_receivable=20.0,
            inventory=15.0,
        )
        return CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=build_company_card(Context(ts_code=ts_code, current=snapshot), []))


def test_rss_pending_event_is_retried_on_next_manual_poll():
    xml = """
    <rss><channel>
      <item><title>平安银行：2025年半年度报告</title><link>https://example.com/a</link></item>
    </channel></rss>
    """

    def handler(request):
        return httpx.Response(200, text=xml)

    analyzer = PendingThenOkAnalyzer()
    service = RssPollService(
        feeds=["https://example.com/rss.xml"],
        max_entries=10,
        company_to_ts_code={"平安银行": "000001.SZ"},
        analyzer=analyzer,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    first = service.poll()
    second = service.poll()

    assert first.pending_count == 1
    assert second.analyzed_count == 1
    assert analyzer.calls == 2


def test_rss_poll_result_reports_ignored_entries_and_errors():
    def handler(request):
        return httpx.Response(500, text="bad gateway")

    analyzer = PendingThenOkAnalyzer()
    service = RssPollService(
        feeds=["https://example.com/rss.xml"],
        max_entries=10,
        company_to_ts_code={"平安银行": "000001.SZ"},
        analyzer=analyzer,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = service.poll()

    assert result.errors
    assert result.errors[0].startswith("https://example.com/rss.xml")
    assert result.ignored_count == 0
