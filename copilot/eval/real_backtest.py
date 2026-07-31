from collections import Counter

from pydantic import BaseModel

from copilot.service.disclosure_scan import CompanyAnalysisStatus


class ScanFailureSummary(BaseModel):
    by_status: dict[str, int]
    by_industry: dict[str, int]
    by_reason: dict[str, int]


def summarize_scan_counts(scans) -> dict[str, int]:
    return {
        "days": len(scans),
        "disclosed_count": sum(scan.disclosed_count for scan in scans),
        "ok_count": sum(scan.ok_count for scan in scans),
        "data_not_ready_count": sum(scan.data_not_ready_count for scan in scans),
        "data_incomplete_count": sum(scan.data_incomplete_count for scan in scans),
        "error_count": sum(scan.error_count for scan in scans),
    }


def summarize_scan_failures(scans) -> ScanFailureSummary:
    by_status = Counter()
    by_industry = Counter()
    by_reason = Counter()
    for scan in scans:
        for event in scan.events:
            if event.status == CompanyAnalysisStatus.OK:
                continue
            by_status[event.status.value] += 1
            if event.industry:
                by_industry[event.industry] += 1
            by_reason[event.message] += 1
    return ScanFailureSummary(
        by_status=dict(sorted(by_status.items())),
        by_industry=dict(sorted(by_industry.items())),
        by_reason=dict(sorted(by_reason.items())),
    )
