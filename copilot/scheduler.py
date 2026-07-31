from pydantic import BaseModel

from copilot.api.app import NotifyResult


class DisclosureSendJob(BaseModel):
    date: str


def run_disclosure_send_job(job: DisclosureSendJob, report_service) -> NotifyResult:
    result = report_service.notify_feishu_disclosure_day(job.date)
    if isinstance(result, NotifyResult):
        return result
    return NotifyResult.model_validate(result)
