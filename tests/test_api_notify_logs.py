from fastapi.testclient import TestClient

from copilot.api.app import AppMeta, FeishuPreview, NotifyResult, create_app
from copilot.rss.service import RssPollResult
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_scan import CompanyAnalysisStatus, build_analysis_bundle
from copilot.service.notify_store import NotifyLogEvent


class FakeNotifyLogService:
    def get_company_card(self, ts_code, period):
        return None

    def get_daily_summary(self, date):
        return None

    def get_evidence(self, ts_code, period, rule_id):
        return []

    def get_quarterly_review(self):
        return None

    def get_meta(self):
        return AppMeta(coverage_count=0, company_names={}, tushare_ready=True, feishu_ready=True)

    def analyze_company(self, ts_code, period):
        return CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok")

    def analyze_disclosure_day(self, date):
        return self.analyze_disclosure_day_bundle(date).summary

    def scan_disclosure_day(self, date):
        return self.analyze_disclosure_day_bundle(date).scan

    def analyze_disclosure_day_bundle(self, date):
        return build_analysis_bundle(date=date, coverage_count=0, results=[])

    def start_disclosure_day_job(self, date):
        raise AssertionError("not used")

    def run_disclosure_day_job(self, job_id):
        raise AssertionError("not used")

    def list_disclosure_day_jobs(self, limit=20):
        return []

    def get_disclosure_day_job(self, job_id):
        raise AssertionError("not used")

    def cancel_disclosure_day_job(self, job_id):
        raise AssertionError("not used")

    def upsert_review_label(self, label):
        raise AssertionError("not used")

    def list_review_labels(self, ts_code=None, period=None):
        return []

    def run_disclosure_automation(self, date, notify=True):
        raise AssertionError("not used")

    def poll_rss(self):
        return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])

    def verify_feishu_callback_token(self, token):
        return True

    def preview_feishu_disclosure_day(self, date):
        return FeishuPreview(date=date, text="", sendable=False, reason="webhook_not_configured")

    def notify_feishu_disclosure_day(self, date):
        return NotifyResult(sent=True, reason="ok")

    def list_notify_logs(self, limit=20):
        assert limit == 2
        return [
            NotifyLogEvent(id=2, channel="feishu_disclosure_day", dedupe_key="20250826", sent=False, reason="send_failed", created_at=2.0),
            NotifyLogEvent(id=1, channel="feishu_disclosure_day", dedupe_key="20250825", sent=True, reason="ok", created_at=1.0),
        ]


def test_notify_logs_route_lists_recent_attempts():
    client = TestClient(create_app(FakeNotifyLogService()))

    response = client.get("/api/notify/logs?limit=2")

    assert response.status_code == 200
    assert [event["dedupe_key"] for event in response.json()] == ["20250826", "20250825"]
    assert response.json()[0]["reason"] == "send_failed"
