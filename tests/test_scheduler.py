from copilot.scheduler import DisclosureAutomationJob, DisclosureSendJob, run_disclosure_automation_job, run_disclosure_send_job


class FakeReportService:
    def __init__(self):
        self.sent_dates = []

    def notify_feishu_disclosure_day(self, date):
        self.sent_dates.append(date)
        return {"sent": True, "reason": "ok"}


class FakeAutomationService(FakeReportService):
    def __init__(self):
        super().__init__()
        self.started_dates = []
        self.ran_jobs = []

    def start_disclosure_day_job(self, date):
        self.started_dates.append(date)
        return {"job_id": "job-1", "date": date, "status": "running"}

    def run_disclosure_day_job(self, job_id):
        self.ran_jobs.append(job_id)
        return {"job_id": job_id, "date": "20250825", "status": "completed"}


def test_run_disclosure_send_job_calls_notify_once():
    service = FakeReportService()
    job = DisclosureSendJob(date="20250825")

    result = run_disclosure_send_job(job, service)

    assert service.sent_dates == ["20250825"]
    assert result.sent is True
    assert result.reason == "ok"


def test_run_disclosure_automation_job_scans_then_notifies():
    service = FakeAutomationService()
    job = DisclosureAutomationJob(date="20250825", notify=True)

    result = run_disclosure_automation_job(job, service)

    assert result.job_id == "job-1"
    assert result.scan_status == "completed"
    assert result.notify_sent is True
    assert service.started_dates == ["20250825"]
    assert service.ran_jobs == ["job-1"]
    assert service.sent_dates == ["20250825"]
