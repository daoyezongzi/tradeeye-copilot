from pydantic import BaseModel

from copilot.api.app import NotifyResult


class DisclosureSendJob(BaseModel):
    date: str


class DisclosureAutomationJob(BaseModel):
    date: str
    notify: bool = True


class DisclosureAutomationResult(BaseModel):
    date: str
    job_id: str
    scan_status: str
    notify_sent: bool = False
    notify_reason: str | None = None


def _job_value(job, key: str):
    if isinstance(job, dict):
        return job[key]
    return getattr(job, key)


def run_disclosure_send_job(job: DisclosureSendJob, report_service) -> NotifyResult:
    result = report_service.notify_feishu_disclosure_day(job.date)
    if isinstance(result, NotifyResult):
        return result
    return NotifyResult.model_validate(result)


def run_disclosure_automation_job(job: DisclosureAutomationJob, report_service) -> DisclosureAutomationResult:
    started = report_service.start_disclosure_day_job(job.date)
    job_id = _job_value(started, "job_id")
    finished = report_service.run_disclosure_day_job(job_id)
    notify_result = NotifyResult(sent=False, reason="disabled")
    if job.notify:
        notify_result = run_disclosure_send_job(DisclosureSendJob(date=job.date), report_service)
    return DisclosureAutomationResult(
        date=job.date,
        job_id=job_id,
        scan_status=_job_value(finished, "status"),
        notify_sent=notify_result.sent,
        notify_reason=notify_result.reason,
    )
