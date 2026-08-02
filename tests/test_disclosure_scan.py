from copilot.service.analyzer import CompanyAnalysisStatus
from copilot.service.disclosure_scan import DisclosureScanEvent, DisclosureScanResult, build_scan_result


def test_build_scan_result_counts_statuses():
    events = [
        DisclosureScanEvent(
            ts_code="000001.SZ",
            period="20250630",
            status=CompanyAnalysisStatus.DATA_NOT_READY,
            message="missing gross_margin_pct",
            has_card=False,
            industry="bank",
        ),
        DisclosureScanEvent(
            ts_code="920056.BJ",
            period="20250630",
            status=CompanyAnalysisStatus.OK,
            message="ok",
            has_card=True,
            industry="generic",
        ),
        DisclosureScanEvent(
            ts_code="600000.SH",
            period="20250630",
            status=CompanyAnalysisStatus.DATA_INCOMPLETE,
            message="current.revenue is negative",
            has_card=False,
            industry="bank",
        ),
    ]

    result = build_scan_result(date="20250821", coverage_count=3, events=events)

    assert result == DisclosureScanResult(
        date="20250821",
        coverage_count=3,
        disclosed_count=3,
        ok_count=1,
        data_not_ready_count=1,
        data_incomplete_count=1,
        error_count=0,
        events=events,
    )


def test_disclosure_scan_event_keeps_failure_reason_visible():
    event = DisclosureScanEvent(
        ts_code="000001.SZ",
        period="20250630",
        status=CompanyAnalysisStatus.DATA_NOT_READY,
        message="Tushare 暂未返回 000001.SZ 20250630 的完整财务快照",
        has_card=False,
        industry="bank",
    )
    assert event.industry == "bank"
    assert "完整财务快照" in event.message


from copilot.datasource.calendar import DisclosureEvent
from copilot.models import PeriodSnapshot
from copilot.service.analyzer import AnalyzerService


class ScanCalendar:
    def fetch_events(self, date, coverage_pool):
        return [
            DisclosureEvent(ts_code="000001.SZ", ann_date=date, period="20250630"),
            DisclosureEvent(ts_code="920056.BJ", ann_date=date, period="20250630"),
        ]


class ScanFundamentals:
    def fetch_snapshot(self, ts_code, period):
        if ts_code == "000001.SZ":
            return PeriodSnapshot(ts_code=ts_code, period=period)
        return PeriodSnapshot(
            ts_code=ts_code,
            period=period,
            revenue=100.0,
            net_profit=10.0,
            deducted_net_profit=9.0,
            gross_margin_pct=30.0,
            operating_cash_flow=8.0,
            accounts_receivable=20.0,
            inventory=15.0,
        )


class ScanStore:
    def __init__(self):
        self.snapshots = {}

    def upsert_snapshot(self, snapshot):
        self.snapshots[(snapshot.ts_code, snapshot.period)] = snapshot

    def get_snapshot(self, ts_code, period):
        return self.snapshots.get((ts_code, period))

    def replace_findings(self, ts_code, period, findings):
        pass


def test_analyzer_disclosure_scan_returns_status_for_each_event():
    service = AnalyzerService(
        fundamentals=ScanFundamentals(),
        store=ScanStore(),
        coverage_pool=["000001.SZ", "920056.BJ"],
        calendar=ScanCalendar(),
        company_industries={"000001.SZ": "bank", "920056.BJ": "generic"},
    )

    result = service.scan_disclosure_day("20250821")

    assert result.date == "20250821"
    assert result.coverage_count == 2
    assert result.disclosed_count == 2
    assert [(event.ts_code, event.status, event.has_card, event.industry) for event in result.events] == [
        ("000001.SZ", CompanyAnalysisStatus.DATA_NOT_READY, True, "bank"),
        ("920056.BJ", CompanyAnalysisStatus.OK, True, "generic"),
    ]
