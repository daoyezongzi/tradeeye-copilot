from pathlib import Path
import sqlite3
from time import time
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
    owner_id: str | None = None
    resume_from_job_id: str | None = None
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

    def start(self, date: str, resume_from_job_id: str | None = None, owner_id: str | None = None) -> DisclosureJobStatus:
        if resume_from_job_id is not None:
            self.get(resume_from_job_id, owner_id=owner_id)
        job_id = uuid4().hex
        status = DisclosureJobStatus(job_id=job_id, date=date, status="running", owner_id=owner_id, resume_from_job_id=resume_from_job_id)
        self._jobs[job_id] = status
        self._started_at[job_id] = time()
        return status

    def list_recent(self, limit: int = 20, owner_id: str | None = None) -> list[DisclosureJobStatus]:
        jobs = sorted(self._jobs.values(), key=lambda job: self._started_at[job.job_id], reverse=True)
        if owner_id is not None:
            jobs = [job for job in jobs if job.owner_id == owner_id]
        return [self.get(job.job_id, owner_id=owner_id) for job in jobs[:limit]]

    def get(self, job_id: str, owner_id: str | None = None) -> DisclosureJobStatus:
        status = self._jobs[job_id]
        if owner_id is not None and status.owner_id != owner_id:
            raise PermissionError(f"job {job_id} is not visible to owner {owner_id}")
        status.elapsed_seconds = round(time() - self._started_at[job_id], 1)
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

    def request_cancel(self, job_id: str, owner_id: str | None = None) -> DisclosureJobStatus:
        status = self.get(job_id, owner_id=owner_id)
        self._cancel_requested.add(job_id)
        if status.status == "running":
            status.current_stage = "cancel_requested"
            status.logs.append("cancel requested")
        return self.get(job_id, owner_id=owner_id)

    def should_cancel(self, job_id: str) -> bool:
        return job_id in self._cancel_requested

    def prune_finished(self, keep_recent: int = 20) -> int:
        finished = [
            job
            for job in self._jobs.values()
            if job.status in {"completed", "cancelled", "failed"}
        ]
        finished.sort(key=lambda job: self._started_at[job.job_id], reverse=True)
        to_remove = finished[keep_recent:]
        for job in to_remove:
            self._jobs.pop(job.job_id, None)
            self._started_at.pop(job.job_id, None)
            self._cancel_requested.discard(job.job_id)
        return len(to_remove)

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


class SQLiteDisclosureJobStore(DisclosureJobStore):
    def __init__(self, path: str | Path, company_names: dict[str, str] | None = None):
        super().__init__(company_names=company_names)
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS disclosure_jobs (
                    job_id TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    cancel_requested INTEGER NOT NULL,
                    started_at REAL NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )

    def start(self, date: str, resume_from_job_id: str | None = None, owner_id: str | None = None) -> DisclosureJobStatus:
        status = super().start(date, resume_from_job_id=resume_from_job_id, owner_id=owner_id)
        self._persist(status)
        return status

    def get(self, job_id: str, owner_id: str | None = None) -> DisclosureJobStatus:
        if job_id not in self._jobs:
            self._load(job_id)
        return super().get(job_id, owner_id=owner_id)

    def list_recent(self, limit: int = 20, owner_id: str | None = None) -> list[DisclosureJobStatus]:
        self.init_schema()
        query = "SELECT job_id FROM disclosure_jobs ORDER BY started_at DESC"
        params = ()
        if owner_id is None:
            query += " LIMIT ?"
            params = (limit,)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        jobs = []
        for row in rows:
            job = self.get(row["job_id"])
            if owner_id is None or job.owner_id == owner_id:
                jobs.append(self.get(row["job_id"], owner_id=owner_id))
            if len(jobs) >= limit:
                break
        return jobs

    def apply_progress(self, job_id: str, event: DisclosureProgressEvent | None = None, **values) -> DisclosureJobStatus:
        status = super().apply_progress(job_id, event, **values)
        self._persist(status)
        return status

    def request_cancel(self, job_id: str, owner_id: str | None = None) -> DisclosureJobStatus:
        status = super().request_cancel(job_id, owner_id=owner_id)
        self._persist(status)
        return status

    def mark_completed(self, job_id: str, bundle: DisclosureAnalysisBundle) -> DisclosureJobStatus:
        status = super().mark_completed(job_id, bundle)
        self._persist(status)
        return status

    def mark_cancelled(self, job_id: str, bundle: DisclosureAnalysisBundle) -> DisclosureJobStatus:
        status = super().mark_cancelled(job_id, bundle)
        self._persist(status)
        return status

    def mark_failed(self, job_id: str, message: str) -> DisclosureJobStatus:
        status = super().mark_failed(job_id, message)
        self._persist(status)
        return status

    def prune_finished(self, keep_recent: int = 20) -> int:
        self.init_schema()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT job_id FROM disclosure_jobs
                WHERE status IN ('completed', 'cancelled', 'failed')
                ORDER BY started_at DESC
                """
            ).fetchall()
            to_remove = [row["job_id"] for row in rows[keep_recent:]]
            if to_remove:
                conn.executemany("DELETE FROM disclosure_jobs WHERE job_id = ?", [(job_id,) for job_id in to_remove])
        for job_id in to_remove:
            self._jobs.pop(job_id, None)
            self._started_at.pop(job_id, None)
            self._cancel_requested.discard(job_id)
        return len(to_remove)

    def _persist(self, status: DisclosureJobStatus) -> None:
        self.init_schema()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO disclosure_jobs (job_id, date, status, cancel_requested, started_at, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    date = excluded.date,
                    status = excluded.status,
                    cancel_requested = excluded.cancel_requested,
                    started_at = excluded.started_at,
                    payload = excluded.payload
                """,
                (
                    status.job_id,
                    status.date,
                    status.status,
                    1 if status.job_id in self._cancel_requested else 0,
                    self._started_at[status.job_id],
                    status.model_dump_json(),
                ),
            )

    def _load(self, job_id: str) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload, started_at, cancel_requested FROM disclosure_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        status = DisclosureJobStatus.model_validate_json(row["payload"])
        self._jobs[job_id] = status
        self._started_at[job_id] = row["started_at"]
        if row["cancel_requested"]:
            self._cancel_requested.add(job_id)
