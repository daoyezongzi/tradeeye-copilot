from fastapi.testclient import TestClient

from copilot.api.app import create_app
from copilot.rss.service import RssPollResult
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureScanEvent, build_scan_result


class FakeScanService:
    def get_company_card(self, ts_code, period):
        return None

    def get_daily_summary(self, date):
        return None

    def get_evidence(self, ts_code, period, rule_id):
        return []

    def get_quarterly_review(self):
        return None

    def analyze_company(self, ts_code, period):
        raise AssertionError("not used")

    def analyze_disclosure_day(self, date):
        raise AssertionError("not used")

    def poll_rss(self):
        return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])

    def notify_feishu_disclosure_day(self, date):
        raise AssertionError("not used")

    def scan_disclosure_day(self, date):
        return build_scan_result(
            date=date,
            coverage_count=2,
            events=[
                DisclosureScanEvent(
                    ts_code="000001.SZ",
                    period="20250630",
                    status=CompanyAnalysisStatus.DATA_NOT_READY,
                    message="missing bank fields",
                    has_card=False,
                    industry="bank",
                ),
                DisclosureScanEvent(
                    ts_code="920056.BJ",
                    period="20250630",
                    status=CompanyAnalysisStatus.OK,
                    message="ok",
                    has_card=True,
                    industry="generic",
                ),
            ],
        )


def test_scan_disclosure_day_route_returns_diagnostics():
    client = TestClient(create_app(FakeScanService()))

    response = client.post("/api/scan/disclosure-day", json={"date": "20250821"})

    assert response.status_code == 200
    assert response.json()["data_not_ready_count"] == 1
    assert response.json()["events"][0]["industry"] == "bank"
