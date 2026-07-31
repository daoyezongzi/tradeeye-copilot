from fastapi.testclient import TestClient

from copilot.api.app import AppMeta, FeishuPreview, NotifyResult, create_app
from copilot.models import Finding, Severity
from copilot.report.builder import CompanyCard
from copilot.rss.service import RssPollResult
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_scan import CompanyAnalysisStatus, build_analysis_bundle


def _card(ts_code: str, severity: Severity | None) -> CompanyCard:
    findings = []
    if severity is not None:
        findings = [Finding(rule_id="x", severity=severity, title="异常", detail="证据", evidence=[], score=99.0)]
    return CompanyCard(
        ts_code=ts_code,
        period="20250630",
        fact_line="fact",
        findings=findings,
        max_severity=severity,
        max_score=99.0 if severity else 0.0,
    )


def _bundle(date: str):
    return build_analysis_bundle(
        date=date,
        coverage_count=3,
        results=[
            ("603026.SH", "20250630", "generic", CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=_card("603026.SH", Severity.RED))),
            ("600151.SH", "20250630", "generic", CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=_card("600151.SH", Severity.YELLOW))),
            ("000001.SZ", "20250630", "bank", CompanyAnalysisResult(status=CompanyAnalysisStatus.DATA_NOT_READY, message="missing", card=None)),
        ],
    )


class FakeFrontendService:
    def __init__(self):
        self.bundle_calls = 0

    def get_company_card(self, ts_code, period):
        return None

    def get_daily_summary(self, date):
        return None

    def get_evidence(self, ts_code, period, rule_id):
        return []

    def get_quarterly_review(self):
        return None

    def get_meta(self):
        return AppMeta(
            coverage_count=3,
            company_names={"603026.SH": "石大胜华", "000001.SZ": "平安银行"},
            tushare_ready=True,
            feishu_ready=True,
        )

    def analyze_company(self, ts_code, period):
        return CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=_card(ts_code, Severity.RED))

    def analyze_disclosure_day(self, date):
        return _bundle(date).summary

    def scan_disclosure_day(self, date):
        return _bundle(date).scan

    def analyze_disclosure_day_bundle(self, date):
        self.bundle_calls += 1
        return _bundle(date)

    def preview_feishu_disclosure_day(self, date):
        return FeishuPreview(date=date, text="预览正文", sendable=True, reason="ok")

    def poll_rss(self):
        return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])

    def notify_feishu_disclosure_day(self, date):
        return NotifyResult(sent=True, reason="ok")


def test_meta_route_reports_readiness_without_secret_values():
    client = TestClient(create_app(FakeFrontendService()))

    response = client.get("/api/meta")

    assert response.status_code == 200
    payload = response.json()
    assert payload["coverage_count"] == 3
    assert payload["company_names"]["603026.SH"] == "石大胜华"
    assert payload["tushare_ready"] is True
    assert payload["feishu_ready"] is True
    assert "token" not in payload
    assert "webhook" not in payload


def test_bundle_route_returns_summary_and_scan_in_one_call():
    service = FakeFrontendService()
    client = TestClient(create_app(service))

    response = client.post("/api/disclosure-day/bundle", json={"date": "20250825"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["date"] == "20250825"
    assert payload["summary"]["red_count"] == 1
    assert payload["summary"]["yellow_count"] == 1
    assert payload["scan"]["data_not_ready_count"] == 1
    assert service.bundle_calls == 1


def test_feishu_preview_route_returns_text_without_sending():
    client = TestClient(create_app(FakeFrontendService()))

    response = client.post("/api/notify/feishu/disclosure-day/20250825/preview")

    assert response.status_code == 200
    assert response.json() == {"date": "20250825", "text": "预览正文", "sendable": True, "reason": "ok"}
