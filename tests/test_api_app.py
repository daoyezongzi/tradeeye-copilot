from fastapi.testclient import TestClient

from copilot.api.app import create_app
from copilot.models import Context, Evidence, Finding, Severity
from copilot.report.builder import build_company_card, build_daily_summary


class FakeReportService:
    def __init__(self, card, summary):
        self.card = card
        self.summary = summary

    def get_company_card(self, ts_code, period):
        return self.card

    def get_daily_summary(self, date):
        return self.summary

    def get_evidence(self, ts_code, period, rule_id):
        return self.card.findings[0].evidence


def test_company_card_endpoint(make_snapshot):
    finding = Finding(
        rule_id="cashflow_quality",
        severity=Severity.YELLOW,
        title="现金流质量偏弱",
        detail="经营现金流/净利润 = 40.0%",
        evidence=[Evidence(source="tushare.cashflow", field="operating_cash_flow", period="20250630", value=4.0)],
        score=60.0,
    )
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [finding])
    summary = build_daily_summary("20250821", 42, [card])
    client = TestClient(create_app(FakeReportService(card, summary)))

    response = client.get("/api/company/000001.SZ/20250630")

    assert response.status_code == 200
    assert response.json()["ts_code"] == "000001.SZ"
    assert response.json()["findings"][0]["rule_id"] == "cashflow_quality"


def test_daily_summary_endpoint(make_snapshot):
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    summary = build_daily_summary("20250821", 42, [card])
    client = TestClient(create_app(FakeReportService(card, summary)))

    response = client.get("/api/daily/20250821")

    assert response.status_code == 200
    assert response.json()["coverage_count"] == 42


def test_evidence_endpoint(make_snapshot):
    finding = Finding(
        rule_id="cashflow_quality",
        severity=Severity.YELLOW,
        title="现金流质量偏弱",
        detail="经营现金流/净利润 = 40.0%",
        evidence=[Evidence(source="tushare.cashflow", field="operating_cash_flow", period="20250630", value=4.0)],
        score=60.0,
    )
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [finding])
    summary = build_daily_summary("20250821", 42, [card])
    client = TestClient(create_app(FakeReportService(card, summary)))

    response = client.get("/api/evidence/000001.SZ/20250630/cashflow_quality")

    assert response.status_code == 200
    assert response.json()[0]["field"] == "operating_cash_flow"
