from fastapi.testclient import TestClient

from copilot.api.app import AppMeta, FeishuPreview, NotifyResult, create_app
from copilot.rss.service import RssPollResult
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_scan import CompanyAnalysisStatus, build_analysis_bundle
from copilot.service.review_store import StoredReviewLabel


class FakeReviewService:
    def __init__(self):
        self.saved = []
        self.deleted = []

    def get_company_card(self, ts_code, period):
        return None

    def get_daily_summary(self, date):
        return None

    def get_evidence(self, ts_code, period, rule_id):
        return []

    def get_quarterly_review(self):
        return None

    def get_meta(self):
        return AppMeta(coverage_count=0, company_names={}, tushare_ready=False, feishu_ready=False)

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

    def poll_rss(self):
        return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])

    def preview_feishu_disclosure_day(self, date):
        return FeishuPreview(date=date, text="", sendable=False, reason="webhook_not_configured")

    def notify_feishu_disclosure_day(self, date):
        return NotifyResult(sent=False, reason="webhook_not_configured")

    def upsert_review_label(self, label):
        self.saved.append(label)
        return StoredReviewLabel(**label.model_dump(), updated_at=1.0)

    def list_review_labels(self, ts_code=None, period=None):
        return [
            StoredReviewLabel(
                ts_code=ts_code or "603026.SH",
                period=period or "20250630",
                rule_id="cashflow_quality",
                label="TRUE",
                notes="确认异常",
                severity="RED",
                industry="generic",
                reviewer="analyst-a",
                updated_at=1.0,
            )
        ]

    def delete_review_label(self, ts_code, period, rule_id):
        self.deleted.append((ts_code, period, rule_id))
        return True


def test_review_label_routes_upsert_and_list():
    service = FakeReviewService()
    client = TestClient(create_app(service))

    saved = client.post(
        "/api/reviews/labels",
        json={
            "ts_code": "603026.SH",
            "period": "20250630",
            "rule_id": "cashflow_quality",
            "label": "TRUE",
            "notes": "确认异常",
            "severity": "RED",
            "industry": "generic",
            "reviewer": "analyst-a",
        },
    )

    assert saved.status_code == 200
    assert saved.json()["label"] == "TRUE"
    assert service.saved[0].rule_id == "cashflow_quality"

    listed = client.get("/api/reviews/labels?ts_code=603026.SH&period=20250630")

    assert listed.status_code == 200
    assert listed.json()[0]["reviewer"] == "analyst-a"


def test_review_label_route_deletes_label():
    service = FakeReviewService()
    client = TestClient(create_app(service))

    deleted = client.delete("/api/reviews/labels/603026.SH/20250630/cashflow_quality")

    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    assert service.deleted == [("603026.SH", "20250630", "cashflow_quality")]
