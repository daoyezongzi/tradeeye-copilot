from fastapi.testclient import TestClient

from copilot.api.app import AppMeta, FeishuPreview, NotifyResult, create_app
from copilot.rss.service import RssPollResult
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_scan import CompanyAnalysisStatus, build_analysis_bundle
from copilot.service.review_store import StoredReviewLabel


class FakeFeishuCallbackService:
    def __init__(self):
        self.labels = []

    def get_company_card(self, ts_code, period):
        return None

    def get_daily_summary(self, date):
        return None

    def get_evidence(self, ts_code, period, rule_id):
        return []

    def get_quarterly_review(self):
        return None

    def get_meta(self):
        return AppMeta(coverage_count=0, company_names={}, tushare_ready=False, feishu_ready=True)

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
        self.labels.append(label)
        return StoredReviewLabel(**label.model_dump(), updated_at=1.0)

    def list_review_labels(self, ts_code=None, period=None):
        return []

    def poll_rss(self):
        return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])

    def preview_feishu_disclosure_day(self, date):
        return FeishuPreview(date=date, text="", sendable=False, reason="webhook_not_configured")

    def notify_feishu_disclosure_day(self, date):
        return NotifyResult(sent=False, reason="webhook_not_configured")


def test_feishu_callback_records_review_label():
    service = FakeFeishuCallbackService()
    client = TestClient(create_app(service))

    response = client.post(
        "/api/notify/feishu/callback",
        json={
            "action": {"value": {"action": "review_label", "label": "FALSE", "ts_code": "603026.SH", "period": "20250630", "rule_id": "cashflow_quality", "severity": "RED"}},
            "operator": {"name": "张三"},
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "reason": "review_recorded"}
    assert service.labels[0].label == "FALSE"
    assert service.labels[0].reviewer == "张三"
