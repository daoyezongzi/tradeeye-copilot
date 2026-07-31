from pathlib import Path

from fastapi.testclient import TestClient

from copilot.api.app import AppMeta, FeishuPreview, NotifyResult, create_app
from copilot.rss.service import RssPollResult
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_scan import CompanyAnalysisStatus, build_analysis_bundle


class FakeAutomationApiService:
    def __init__(self):
        self.automation_dates = []

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

    def delete_review_label(self, ts_code, period, rule_id):
        return False

    def get_review_metrics(self, ts_code=None, period=None):
        raise AssertionError("not used")

    def poll_rss(self):
        return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])

    def verify_feishu_callback_token(self, token):
        return True

    def verify_automation_trigger_token(self, token):
        return token == "cron-secret"

    def preview_feishu_disclosure_day(self, date):
        return FeishuPreview(date=date, text="", sendable=False, reason="webhook_not_configured")

    def notify_feishu_disclosure_day(self, date):
        return NotifyResult(sent=True, reason="ok")

    def run_disclosure_automation(self, date, notify=True):
        self.automation_dates.append((date, notify))
        return {"date": date, "job_id": "job-1", "scan_status": "completed", "notify_sent": notify, "notify_reason": "ok" if notify else "disabled"}


def test_disclosure_automation_route_runs_scan_and_notify():
    service = FakeAutomationApiService()
    client = TestClient(create_app(service))

    response = client.post("/api/automation/disclosure-day", json={"date": "20250825", "notify": True})

    assert response.status_code == 200
    assert response.json() == {"date": "20250825", "job_id": "job-1", "scan_status": "completed", "notify_sent": True, "notify_reason": "ok"}
    assert service.automation_dates == [("20250825", True)]


def test_disclosure_automation_cron_route_requires_trigger_token():
    service = FakeAutomationApiService()
    client = TestClient(create_app(service))

    missing = client.post("/api/automation/disclosure-day/cron", json={"date": "20250825", "notify": True})
    wrong = client.post("/api/automation/disclosure-day/cron", json={"date": "20250825", "notify": True}, headers={"X-Automation-Token": "wrong"})
    ok = client.post("/api/automation/disclosure-day/cron", json={"date": "20250825", "notify": True}, headers={"X-Automation-Token": "cron-secret"})

    assert missing.status_code == 403
    assert wrong.status_code == 403
    assert ok.status_code == 200
    assert service.automation_dates == [("20250825", True)]


def test_disclosure_automation_github_actions_workflow_is_configured():
    workflow = Path(".github/workflows/disclosure-automation.yml").read_text(encoding="utf-8")

    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "TRADEEYE_API_BASE_URL" in workflow
    assert "AUTOMATION_TRIGGER_TOKEN" in workflow
    assert "/api/automation/disclosure-day/cron" in workflow
    assert "X-Automation-Token" in workflow
