from fastapi.testclient import TestClient

from copilot.api.app import create_app
from copilot.rss.service import RssPollResult


class FakeService:
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
        return RssPollResult(seen_count=2, matched_count=1, analyzed_count=0, pending_count=1, events=[])

    def poll_rss_and_notify_feishu(self, date=None):
        return {"rss": RssPollResult(seen_count=2, matched_count=1, analyzed_count=0, pending_count=0, events=[]), "sent": True, "reason": "ok"}


def test_rss_poll_notify_route_sends_feishu_reminder():
    client = TestClient(create_app(FakeService()))

    response = client.post("/api/rss/poll/notify", json={"date": "20250821"})

    assert response.status_code == 200
    assert response.json()["sent"] is True
    assert response.json()["reason"] == "ok"
    assert response.json()["rss"]["matched_count"] == 1



    client = TestClient(create_app(FakeService()))

    response = client.post("/api/rss/poll")

    assert response.status_code == 200
    assert response.json()["seen_count"] == 2
    assert response.json()["pending_count"] == 1
