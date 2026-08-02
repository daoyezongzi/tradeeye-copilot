from copilot.models import Finding, Severity
from copilot.report.builder import CompanyCard
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureScanEvent, build_analysis_bundle


def test_build_analysis_bundle_derives_summary_and_scan_from_one_result_set():
    card = CompanyCard(
        ts_code="603026.SH",
        period="20250630",
        fact_line="fact",
        findings=[Finding(rule_id="x", severity=Severity.RED, title="异常", detail="证据", evidence=[], score=99.0)],
        max_severity=Severity.RED,
        max_score=99.0,
    )
    blocked_card = CompanyCard(
        ts_code="000001.SZ",
        period="20250630",
        fact_line="数据问题：missing",
        findings=[],
        max_severity=None,
        max_score=0.0,
        card_status="BLOCKED",
    )
    results = [
        ("603026.SH", "20250630", "generic", CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=card)),
        ("000001.SZ", "20250630", "bank", CompanyAnalysisResult(status=CompanyAnalysisStatus.DATA_NOT_READY, message="missing", card=blocked_card)),
    ]

    bundle = build_analysis_bundle(date="20250825", coverage_count=2, results=results)

    assert bundle.date == "20250825"
    assert bundle.summary.coverage_count == 2
    assert bundle.summary.disclosed_count == 2
    assert bundle.summary.red_count == 1
    assert [card.ts_code for card in bundle.summary.cards] == ["603026.SH", "000001.SZ"]
    assert bundle.summary.cards[1].card_status.value == "BLOCKED"
    assert bundle.summary.cards[1].fact_line == "数据问题：missing"
    assert bundle.scan.coverage_count == 2
    assert bundle.scan.disclosed_count == 2
    assert bundle.scan.data_not_ready_count == 1
    assert bundle.scan.events == [
        DisclosureScanEvent(ts_code="603026.SH", period="20250630", status=CompanyAnalysisStatus.OK, message="ok", has_card=True, industry="generic"),
        DisclosureScanEvent(ts_code="000001.SZ", period="20250630", status=CompanyAnalysisStatus.DATA_NOT_READY, message="missing", has_card=True, industry="bank"),
    ]


from copilot.datasource.calendar import DisclosureEvent
from copilot.models import PeriodSnapshot
from copilot.service.analyzer import AnalyzerService


class BundleCalendar:
    def fetch_events(self, date, coverage_pool):
        return [
            DisclosureEvent(ts_code="603026.SH", ann_date=date, period="20250630"),
            DisclosureEvent(ts_code="000001.SZ", ann_date=date, period="20250630"),
        ]


class BundleFundamentals:
    def __init__(self):
        self.calls = []

    def fetch_snapshot(self, ts_code, period):
        self.calls.append((ts_code, period))
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


class BundleStore:
    def __init__(self):
        self.snapshots = {}

    def upsert_snapshot(self, snapshot):
        self.snapshots[(snapshot.ts_code, snapshot.period)] = snapshot

    def get_snapshot(self, ts_code, period):
        return self.snapshots.get((ts_code, period))

    def replace_findings(self, ts_code, period, findings):
        pass


def test_analyzer_analyze_disclosure_day_bundle_fetches_each_event_once():
    fundamentals = BundleFundamentals()
    service = AnalyzerService(
        fundamentals=fundamentals,
        store=BundleStore(),
        coverage_pool=["603026.SH", "000001.SZ"],
        calendar=BundleCalendar(),
        company_industries={"603026.SH": "generic", "000001.SZ": "bank"},
    )

    bundle = service.analyze_disclosure_day_bundle("20250825")

    assert bundle.summary.disclosed_count == 2
    assert bundle.scan.disclosed_count == 2
    assert len([call for call in fundamentals.calls if call[0] == "603026.SH" and call[1] == "20250630"]) == 1


def test_analyzer_returns_blocked_card_when_current_snapshot_not_ready():
    fundamentals = BundleFundamentals()
    service = AnalyzerService(
        fundamentals=fundamentals,
        store=BundleStore(),
        coverage_pool=["000001.SZ"],
        calendar=BundleCalendar(),
        company_industries={"000001.SZ": "bank"},
    )

    result = service.analyze_company("000001.SZ", "20250630")

    assert result.status == CompanyAnalysisStatus.DATA_NOT_READY
    assert result.card is not None
    assert result.card.ts_code == "000001.SZ"
    assert result.card.period == "20250630"
    assert result.card.card_status.value == "BLOCKED"
    assert result.card.fact_line.startswith("数据问题：Tushare 暂未返回")


def test_analyzer_bundle_reports_progress_and_stops_when_paused():
    class PauseBeforeSecondCompany:
        def __init__(self):
            self.events = []

        def progress(self, event):
            self.events.append(event)

        def should_pause(self):
            return any(event.stage == "company_completed" for event in self.events)

    callbacks = PauseBeforeSecondCompany()
    service = AnalyzerService(
        fundamentals=BundleFundamentals(),
        store=BundleStore(),
        coverage_pool=["603026.SH", "000001.SZ"],
        calendar=BundleCalendar(),
        company_industries={"603026.SH": "generic", "000001.SZ": "bank"},
    )

    bundle = service.analyze_disclosure_day_bundle(
        "20250825",
        progress_callback=callbacks.progress,
        should_pause=callbacks.should_pause,
    )

    assert bundle.scan.disclosed_count == 1
    assert [event.stage for event in callbacks.events] == [
        "events_loaded",
        "company_started",
        "company_completed",
        "paused",
    ]
    assert callbacks.events[-1].processed_count == 1


def test_analyzer_bundle_reports_progress_and_stops_when_cancelled():
    class CancelAfterFirstCompany:
        def __init__(self):
            self.events = []

        def progress(self, event):
            self.events.append(event)

        def should_cancel(self):
            return any(event.stage == "company_completed" for event in self.events)

    callbacks = CancelAfterFirstCompany()
    service = AnalyzerService(
        fundamentals=BundleFundamentals(),
        store=BundleStore(),
        coverage_pool=["603026.SH", "000001.SZ"],
        calendar=BundleCalendar(),
        company_industries={"603026.SH": "generic", "000001.SZ": "bank"},
    )

    bundle = service.analyze_disclosure_day_bundle(
        "20250825",
        progress_callback=callbacks.progress,
        should_cancel=callbacks.should_cancel,
    )

    assert bundle.scan.disclosed_count == 1
    assert [event.stage for event in callbacks.events] == [
        "events_loaded",
        "company_started",
        "company_completed",
        "cancelled",
    ]
    assert callbacks.events[1].ts_code == "603026.SH"
    assert callbacks.events[-1].processed_count == 1
