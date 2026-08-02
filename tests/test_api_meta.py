from fastapi.testclient import TestClient

from copilot.api.app import AppMeta, create_app


class FakeService:
    def get_company_card(self, ts_code, period):
        return None

    def get_daily_summary(self, date):
        return None

    def get_evidence(self, ts_code, period, rule_id):
        return []

    def get_quarterly_review(self):
        return None

    def get_meta(self):
        return AppMeta(
            coverage_count=1,
            company_names={"000001.SZ": "平安银行"},
            tushare_ready=True,
            feishu_ready=False,
            agent_ready=False,
        )

    def analyze_company(self, ts_code, period):
        return None

    def analyze_disclosure_day(self, date):
        return None

    def scan_disclosure_day(self, date):
        return None

    def analyze_disclosure_day_bundle(self, date):
        return None

    def start_disclosure_day_job(self, date, resume_from_job_id=None, owner_id=None):
        return None

    def run_disclosure_day_job(self, job_id):
        return None

    def list_disclosure_day_jobs(self, limit=20, owner_id=None):
        return []

    def get_disclosure_day_job(self, job_id, owner_id=None):
        return None

    def cancel_disclosure_day_job(self, job_id, owner_id=None):
        return None

    def prune_disclosure_day_jobs(self, keep_recent=20):
        return 0

    def upsert_review_label(self, label):
        return None

    def list_review_labels(self, ts_code=None, period=None):
        return []

    def delete_review_label(self, ts_code, period, rule_id):
        return False

    def get_review_metrics(self, ts_code=None, period=None):
        return None

    def run_disclosure_automation(self, date, notify=True):
        return None

    def list_notify_logs(self, limit=20):
        return []

    def poll_rss(self):
        return None

    def verify_feishu_callback_token(self, token):
        return True

    def verify_automation_trigger_token(self, token):
        return True

    def preview_feishu_disclosure_day(self, date):
        return None

    def notify_feishu_disclosure_day(self, date):
        return None


def test_meta_includes_agent_ready():
    client = TestClient(create_app(FakeService(), agent_service=object()))

    payload = client.get("/api/meta").json()

    assert payload["agent_ready"] is False
