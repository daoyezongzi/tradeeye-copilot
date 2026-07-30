from fastapi.testclient import TestClient

from copilot.api.app import create_app
from copilot.eval.backtest import BacktestSummary
from copilot.models import Context
from copilot.report.builder import build_company_card, build_daily_summary, build_quarterly_review
from copilot.service.analyzer import CompanyAnalysisResult, CompanyAnalysisStatus


class FakeFullService:
    def __init__(self, make_snapshot):
        self.card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
        self.summary = build_daily_summary("20250821", 1, [self.card])
        self.quarterly = build_quarterly_review(
            BacktestSummary(
                start_date="20250801",
                end_date="20250831",
                coverage_count=1,
                disclosed_count=1,
                ok_count=1,
                data_incomplete_count=0,
                finding_count=0,
                finding_distribution={},
                company_results=[],
            ),
            precision_pct=None,
        )

    def get_company_card(self, ts_code, period):
        return self.card

    def get_daily_summary(self, date):
        return self.summary

    def get_evidence(self, ts_code, period, rule_id):
        return []

    def get_quarterly_review(self):
        return self.quarterly

    def analyze_company(self, ts_code, period):
        return CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=self.card)

    def analyze_disclosure_day(self, date):
        return self.summary


def test_analyze_company_route(make_snapshot):
    client = TestClient(create_app(FakeFullService(make_snapshot)))

    response = client.post("/api/analyze/company", json={"ts_code": "000001.SZ", "period": "20250630"})

    assert response.status_code == 200
    assert response.json()["status"] == "OK"
    assert response.json()["card"]["ts_code"] == "000001.SZ"


def test_analyze_disclosure_day_route(make_snapshot):
    client = TestClient(create_app(FakeFullService(make_snapshot)))

    response = client.post("/api/analyze/disclosure-day", json={"date": "20250821"})

    assert response.status_code == 200
    assert response.json()["date"] == "20250821"
    assert response.json()["disclosed_count"] == 1
