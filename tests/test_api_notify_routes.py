from fastapi.testclient import TestClient
from pydantic import BaseModel

from copilot.api.app import create_app
from copilot.models import Context
from copilot.report.builder import build_company_card, build_daily_summary
from copilot.rss.service import RssPollResult


class NotifyResult(BaseModel):
    sent: bool
    reason: str


class FakeNotifyService:
    def __init__(self, make_snapshot, summary):
        self.summary = summary
        self.card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])

    def get_company_card(self, ts_code, period):
        return self.card

    def get_daily_summary(self, date):
        return self.summary

    def get_evidence(self, ts_code, period, rule_id):
        return []

    def get_quarterly_review(self):
        return None

    def analyze_company(self, ts_code, period):
        raise AssertionError("not used")

    def analyze_disclosure_day(self, date):
        return self.summary

    def poll_rss(self):
        return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])

    def notify_feishu_disclosure_day(self, date):
        return NotifyResult(
            sent=self.summary.disclosed_count > 0,
            reason="ok" if self.summary.disclosed_count > 0 else "no_disclosures",
        )


def test_notify_feishu_disclosure_day_sends_when_summary_has_cards(make_snapshot):
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    summary = build_daily_summary("20250821", 1, [card])
    client = TestClient(create_app(FakeNotifyService(make_snapshot, summary)))

    response = client.post("/api/notify/feishu/disclosure-day/20250821")

    assert response.status_code == 200
    assert response.json() == {"sent": True, "reason": "ok"}


def test_notify_feishu_disclosure_day_skips_when_no_disclosures(make_snapshot):
    summary = build_daily_summary("20250821", 1, [])
    client = TestClient(create_app(FakeNotifyService(make_snapshot, summary)))

    response = client.post("/api/notify/feishu/disclosure-day/20250821")

    assert response.status_code == 200
    assert response.json() == {"sent": False, "reason": "no_disclosures"}
