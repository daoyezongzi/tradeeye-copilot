from fastapi.testclient import TestClient

from copilot.api.app import AppMeta, FeishuPreview, NotifyResult, create_app
from copilot.report.builder import CompanyCard, DailySummary
from copilot.rss.service import RssPollResult
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureAnalysisBundle, build_analysis_bundle


class FakeJobService:
    def __init__(self):
        self.started_dates = []
        self.start_resume_from = []
        self.cancelled_jobs = []
        self.ran_background_jobs = []
        self.prune_requests = []
        self.start_owner_ids = []
        self.list_owner_ids = []
        self.get_owner_ids = []
        self.cancel_owner_ids = []

    def get_company_card(self, ts_code, period):
        return None

    def get_daily_summary(self, date):
        return None

    def get_evidence(self, ts_code, period, rule_id):
        return []

    def get_quarterly_review(self):
        return None

    def get_meta(self):
        return AppMeta(coverage_count=2, company_names={}, tushare_ready=True, feishu_ready=False)

    def analyze_company(self, ts_code, period):
        return CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok")

    def analyze_disclosure_day(self, date):
        return self.analyze_disclosure_day_bundle(date).summary

    def scan_disclosure_day(self, date):
        return self.analyze_disclosure_day_bundle(date).scan

    def analyze_disclosure_day_bundle(self, date):
        return build_analysis_bundle(date=date, coverage_count=2, results=[])

    def poll_rss(self):
        return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])

    def preview_feishu_disclosure_day(self, date):
        return FeishuPreview(date=date, text="", sendable=False, reason="webhook_not_configured")

    def notify_feishu_disclosure_day(self, date):
        return NotifyResult(sent=False, reason="webhook_not_configured")

    def start_disclosure_day_job(self, date, resume_from_job_id=None, owner_id=None):
        self.started_dates.append(date)
        self.start_resume_from.append(resume_from_job_id)
        self.start_owner_ids.append(owner_id)
        return {
            "job_id": "job-1",
            "date": date,
            "status": "running",
            "processed_count": 0,
            "total_count": 2,
            "ok_count": 0,
            "data_problem_count": 0,
            "current_ts_code": None,
            "current_name": None,
            "current_period": None,
            "current_stage": "queued",
            "elapsed_seconds": 0.0,
            "logs": [],
            "bundle": None,
        }

    def run_disclosure_day_job(self, job_id):
        self.ran_background_jobs.append(job_id)

    def list_disclosure_day_jobs(self, limit=20, owner_id=None):
        self.list_owner_ids.append(owner_id)
        assert limit == 2
        return [
            {
                "job_id": "job-2",
                "date": "20250826",
                "status": "completed",
                "processed_count": 2,
                "total_count": 2,
                "ok_count": 2,
                "data_problem_count": 0,
                "current_ts_code": None,
                "current_name": None,
                "current_period": None,
                "current_stage": "completed",
                "elapsed_seconds": 3.0,
                "logs": [],
                "bundle": None,
            },
            self.get_disclosure_day_job("job-1", owner_id=owner_id),
        ]

    def get_disclosure_day_job(self, job_id, owner_id=None):
        self.get_owner_ids.append(owner_id)
        assert job_id == "job-1"
        return {
            "job_id": job_id,
            "date": "20250825",
            "status": "running",
            "processed_count": 1,
            "total_count": 2,
            "ok_count": 1,
            "data_problem_count": 0,
            "current_ts_code": "603026.SH",
            "current_name": "石大胜华",
            "current_period": "20250630",
            "current_stage": "fetch_cashflow",
            "elapsed_seconds": 1.2,
            "logs": ["603026.SH fetch_cashflow"],
            "bundle": None,
        }

    def cancel_disclosure_day_job(self, job_id, owner_id=None):
        self.cancel_owner_ids.append(owner_id)
        self.cancelled_jobs.append(job_id)
        return {
            "job_id": job_id,
            "date": "20250825",
            "status": "cancelled",
            "processed_count": 1,
            "total_count": 2,
            "ok_count": 1,
            "data_problem_count": 0,
            "current_ts_code": "603026.SH",
            "current_name": "石大胜华",
            "current_period": "20250630",
            "current_stage": "cancelled",
            "elapsed_seconds": 1.3,
            "logs": ["cancel requested"],
            "bundle": None,
        }

    def prune_disclosure_day_jobs(self, keep_recent=20):
        self.prune_requests.append(keep_recent)
        return 3


def test_disclosure_day_job_routes_start_poll_and_cancel():
    service = FakeJobService()
    client = TestClient(create_app(service))

    started = client.post("/api/disclosure-day/jobs", json={"date": "20250825"})
    assert started.status_code == 200
    assert started.json()["job_id"] == "job-1"
    assert started.json()["status"] == "running"
    assert service.started_dates == ["20250825"]
    assert service.start_resume_from == [None]
    assert service.ran_background_jobs == ["job-1"]

    progress = client.get("/api/disclosure-day/jobs/job-1")
    assert progress.status_code == 200
    assert progress.json()["processed_count"] == 1
    assert progress.json()["current_stage"] == "fetch_cashflow"
    assert progress.json()["current_name"] == "石大胜华"

    cancelled = client.post("/api/disclosure-day/jobs/job-1/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert service.cancelled_jobs == ["job-1"]


def test_disclosure_day_job_routes_list_recent_jobs():
    client = TestClient(create_app(FakeJobService()))

    response = client.get("/api/disclosure-day/jobs?limit=2")

    assert response.status_code == 200
    assert [job["job_id"] for job in response.json()] == ["job-2", "job-1"]


def test_disclosure_day_job_route_accepts_resume_source():
    service = FakeJobService()
    client = TestClient(create_app(service))

    response = client.post("/api/disclosure-day/jobs", json={"date": "20250825", "resume_from_job_id": "job-cancelled"})

    assert response.status_code == 200
    assert service.start_resume_from == ["job-cancelled"]


def test_disclosure_day_job_route_prunes_finished_jobs():
    service = FakeJobService()
    client = TestClient(create_app(service))

    response = client.delete("/api/disclosure-day/jobs?keep_recent=7")

    assert response.status_code == 200
    assert response.json() == {"deleted": 3}
    assert service.prune_requests == [7]


def test_disclosure_day_job_routes_pass_owner_header_to_service():
    service = FakeJobService()
    client = TestClient(create_app(service))
    headers = {"X-TradeEye-Owner": "alice"}

    started = client.post("/api/disclosure-day/jobs", json={"date": "20250825"}, headers=headers)
    listed = client.get("/api/disclosure-day/jobs?limit=2", headers=headers)
    progress = client.get("/api/disclosure-day/jobs/job-1", headers=headers)
    cancelled = client.post("/api/disclosure-day/jobs/job-1/cancel", headers=headers)

    assert started.status_code == 200
    assert listed.status_code == 200
    assert progress.status_code == 200
    assert cancelled.status_code == 200
    assert service.start_owner_ids == ["alice"]
    assert service.list_owner_ids == ["alice"]
    assert service.get_owner_ids == ["alice", "alice"]
    assert service.cancel_owner_ids == ["alice"]
