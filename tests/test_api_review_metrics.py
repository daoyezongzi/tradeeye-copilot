from fastapi.testclient import TestClient

from copilot.api.app import AppMeta, FeishuPreview, NotifyResult, create_app
from copilot.eval.manual_review import PrecisionBreakdown, PrecisionResult
from copilot.rss.service import RssPollResult
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_scan import CompanyAnalysisStatus, build_analysis_bundle
from copilot.service.review_store import StoredReviewLabel


class FakeReviewMetricsService:
    def __init__(self):
        self.filters = []

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
        return [
            StoredReviewLabel(
                ts_code="603026.SH",
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

    def get_review_metrics(self, ts_code=None, period=None):
        self.filters.append((ts_code, period))
        return PrecisionBreakdown(
            overall=PrecisionResult(reviewed_count=2, true_positive_count=1, false_positive_count=1, precision_pct=50.0),
            by_rule={"cashflow_quality": PrecisionResult(reviewed_count=2, true_positive_count=1, false_positive_count=1, precision_pct=50.0)},
            by_severity={},
            by_industry={},
        )

    def run_disclosure_automation(self, date, notify=True):
        raise AssertionError("not used")

    def list_notify_logs(self, limit=20):
        return []

    def poll_rss(self):
        return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])

    def verify_feishu_callback_token(self, token):
        return True

    def preview_feishu_disclosure_day(self, date):
        return FeishuPreview(date=date, text="", sendable=False, reason="webhook_not_configured")

    def notify_feishu_disclosure_day(self, date):
        return NotifyResult(sent=True, reason="ok")


def test_review_metrics_route_returns_precision_breakdown():
    service = FakeReviewMetricsService()
    client = TestClient(create_app(service))

    response = client.get("/api/reviews/metrics?period=20250630")

    assert response.status_code == 200
    assert response.json()["overall"]["precision_pct"] == 50.0
    assert response.json()["by_rule"]["cashflow_quality"]["false_positive_count"] == 1
    assert service.filters == [(None, "20250630")]


def test_review_labels_csv_route_exports_labels():
    client = TestClient(create_app(FakeReviewMetricsService()))

    response = client.get("/api/reviews/labels.csv?period=20250630")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "ts_code,period,rule_id,label,notes,severity,industry,reviewer,updated_at" in response.text
    assert "603026.SH,20250630,cashflow_quality,TRUE" in response.text
