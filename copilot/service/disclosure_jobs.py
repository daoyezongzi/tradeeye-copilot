from time import monotonic
from uuid import uuid4

from pydantic import BaseModel, Field

from copilot.service.disclosure_scan import DisclosureAnalysisBundle, DisclosureProgressEvent


class DisclosureJobStatus(BaseModel):
    job_id: str
    date: str
    status: str
    processed_count: int = 0
    total_count: int = 0
    ok_count: int = 0
    data_problem_count: int = 0
    current_ts_code: str | None = None
    current_name: str | None = None
    current_period: str | None = None
    current_stage: str = "queued"
    elapsed_seconds: float = 0.0
    logs: list[str] = Field(default_factory=list)
    bundle: DisclosureAnalysisBundle | None = None


class DisclosureJobStore:
    def __init__(self, company_names: dict[str, str] | None = None):
        self.company_names = company_names or {}
        self._jobs: dict[str, DisclosureJobStatus] = {}
        self._started_at: dict[str, float] = {}
        self._cancel_requested: set[str] = set()
        self._active_job_id: str | None = None

    def start(self, date: str) -> DisclosureJobStatus:
        job_id = uuid4().hex
        status = DisclosureJobStatus(job_id=job_id, date=date, status="running")
        self._jobs[job_id] = status
        self._started_at[job_id] = monotonic()
        return status

    def get(self, job_id: str) -> DisclosureJobStatus:
        status = self._jobs[job_id]
        status.elapsed_seconds = round(monotonic() - self._started_at[job_id], 1)
        return status

    def set_active(self, job_id: str | None) -> None:
        self._active_job_id = job_id

    def apply_table_progress(self, stage: str, ts_code: str, period: str) -> DisclosureJobStatus | None:
        if self._active_job_id is None:
            return None
        status = self._jobs[self._active_job_id]
        return self.apply_progress(
            self._active_job_id,
            stage=stage,
            processed_count=status.processed_count,
            total_count=status.total_count,
            ts_code=ts_code,
            period=period,
        )

    def active_should_cancel(self) -> bool:
        return self._active_job_id is not None and self.should_cancel(self._active_job_id)

    def apply_progress(self, job_id: str, event: DisclosureProgressEvent | None = None, **values) -> DisclosureJobStatus:
        if event is None:
            event = DisclosureProgressEvent(**values)
        status = self._jobs[job_id]
        status.current_stage = event.stage
        status.processed_count = event.processed_count
        status.total_count = event.total_count
        status.current_ts_code = event.ts_code
        status.current_name = self.company_names.get(event.ts_code, event.ts_code) if event.ts_code else None
        status.current_period = event.period
        if event.status is not None:
            if event.status.value == "OK":
                status.ok_count += 1
            else:
                status.data_problem_count += 1
        status.logs.append(self._format_log(event))
        return self.get(job_id)

    def request_cancel(self, job_id: str) -> DisclosureJobStatus:
        self._cancel_requested.add(job_id)
        status = self._jobs[job_id]
        if status.status == "running":
            status.current_stage = "cancel_requested"
            status.logs.append("cancel requested")
        return self.get(job_id)

    def should_cancel(self, job_id: str) -> bool:
        return job_id in self._cancel_requested

    def mark_completed(self, job_id: str, bundle: DisclosureAnalysisBundle) -> DisclosureJobStatus:
        status = self._jobs[job_id]
        status.status = "completed"
        status.current_stage = "completed"
        self._apply_bundle_counts(status, bundle)
        status.bundle = bundle
        return self.get(job_id)

    def mark_cancelled(self, job_id: str, bundle: DisclosureAnalysisBundle) -> DisclosureJobStatus:
        status = self._jobs[job_id]
        status.status = "cancelled"
        status.current_stage = "cancelled"
        self._apply_bundle_counts(status, bundle)
        status.bundle = bundle
        return self.get(job_id)

    def mark_failed(self, job_id: str, message: str) -> DisclosureJobStatus:
        status = self._jobs[job_id]
        status.status = "failed"
        status.current_stage = "failed"
        status.logs.append(message)
        return self.get(job_id)

    def _apply_bundle_counts(self, status: DisclosureJobStatus, bundle: DisclosureAnalysisBundle) -> None:
        status.processed_count = bundle.scan.disclosed_count
        status.total_count = max(status.total_count, bundle.scan.disclosed_count)
        status.ok_count = bundle.scan.ok_count
        status.data_problem_count = bundle.scan.data_not_ready_count + bundle.scan.data_incomplete_count + bundle.scan.error_count

    def _format_log(self, event: DisclosureProgressEvent) -> str:
        parts = [event.stage]
        if event.ts_code:
            parts.append(event.ts_code)
        if event.period:
            parts.append(event.period)
        if event.status:
            parts.append(event.status.value)
        if event.message:
            parts.append(event.message)
        return " ".join(parts)
