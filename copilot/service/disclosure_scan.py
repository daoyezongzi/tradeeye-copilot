from enum import StrEnum

from pydantic import BaseModel


class CompanyAnalysisStatus(StrEnum):
    OK = "OK"
    DATA_INCOMPLETE = "DATA_INCOMPLETE"
    DATA_NOT_READY = "DATA_NOT_READY"
    ERROR = "ERROR"


class DisclosureScanEvent(BaseModel):
    ts_code: str
    period: str
    status: CompanyAnalysisStatus
    message: str
    has_card: bool
    industry: str | None = None


class DisclosureScanResult(BaseModel):
    date: str
    coverage_count: int
    disclosed_count: int
    ok_count: int
    data_not_ready_count: int
    data_incomplete_count: int
    error_count: int
    events: list[DisclosureScanEvent]


def build_scan_result(date: str, coverage_count: int, events: list[DisclosureScanEvent]) -> DisclosureScanResult:
    return DisclosureScanResult(
        date=date,
        coverage_count=coverage_count,
        disclosed_count=len(events),
        ok_count=sum(1 for event in events if event.status == CompanyAnalysisStatus.OK),
        data_not_ready_count=sum(1 for event in events if event.status == CompanyAnalysisStatus.DATA_NOT_READY),
        data_incomplete_count=sum(1 for event in events if event.status == CompanyAnalysisStatus.DATA_INCOMPLETE),
        error_count=sum(1 for event in events if event.status == CompanyAnalysisStatus.ERROR),
        events=events,
    )
