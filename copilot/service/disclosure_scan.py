from enum import StrEnum

from pydantic import BaseModel

from copilot.report.builder import DailySummary, build_daily_summary


class CompanyAnalysisStatus(StrEnum):
    OK = "OK"
    DATA_INCOMPLETE = "DATA_INCOMPLETE"
    DATA_NOT_READY = "DATA_NOT_READY"
    ERROR = "ERROR"


class DisclosureProgressEvent(BaseModel):
    stage: str
    processed_count: int
    total_count: int
    ts_code: str | None = None
    period: str | None = None
    industry: str | None = None
    status: CompanyAnalysisStatus | None = None
    message: str | None = None


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


class DisclosureAnalysisBundle(BaseModel):
    date: str
    summary: DailySummary
    scan: DisclosureScanResult


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


def build_analysis_bundle(date: str, coverage_count: int, results) -> DisclosureAnalysisBundle:
    cards = [result.card for _, _, _, result in results if result.card is not None]
    events = [
        DisclosureScanEvent(
            ts_code=ts_code,
            period=period,
            status=result.status,
            message=result.message,
            has_card=result.card is not None,
            industry=industry,
        )
        for ts_code, period, industry, result in results
    ]
    scan = build_scan_result(date=date, coverage_count=coverage_count, events=events)
    summary = build_daily_summary(date=date, coverage_count=coverage_count, cards=cards, disclosed_count=len(results))
    return DisclosureAnalysisBundle(date=date, summary=summary, scan=scan)
