from copilot.scheduler import DisclosureSendJob, run_disclosure_send_job


class FakeReportService:
    def __init__(self):
        self.sent_dates = []

    def notify_feishu_disclosure_day(self, date):
        self.sent_dates.append(date)
        return {"sent": True, "reason": "ok"}


def test_run_disclosure_send_job_calls_notify_once():
    service = FakeReportService()
    job = DisclosureSendJob(date="20250825")

    result = run_disclosure_send_job(job, service)

    assert service.sent_dates == ["20250825"]
    assert result.sent is True
    assert result.reason == "ok"
