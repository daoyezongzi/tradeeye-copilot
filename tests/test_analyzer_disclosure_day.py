from copilot.datasource.calendar import DisclosureEvent
from copilot.models import PeriodSnapshot
from copilot.service.analyzer import AnalyzerService


class FakeCalendar:
    def fetch_events(self, date, coverage_pool):
        assert date == "20250821"
        assert coverage_pool == {"000001.SZ", "600000.SH"}
        return [
            DisclosureEvent(ts_code="000001.SZ", ann_date="20250821", period="20250630"),
            DisclosureEvent(ts_code="600000.SH", ann_date="20250821", period="20250630"),
        ]


class EmptyCalendar:
    def fetch_events(self, date, coverage_pool):
        return []


class FakeFundamentals:
    def fetch_snapshot(self, ts_code, period):
        return PeriodSnapshot(
            ts_code=ts_code,
            period=period,
            ann_date="20250821",
            revenue=100.0,
            net_profit=10.0,
            deducted_net_profit=9.0,
            gross_margin_pct=30.0,
            operating_cash_flow=8.0,
            accounts_receivable=20.0,
            inventory=15.0,
        )


class FakeStore:
    def __init__(self):
        self.snapshots = {}
        self.findings = {}

    def upsert_snapshot(self, snapshot):
        self.snapshots[(snapshot.ts_code, snapshot.period)] = snapshot

    def get_snapshot(self, ts_code, period):
        return self.snapshots.get((ts_code, period))

    def replace_findings(self, ts_code, period, findings):
        self.findings[(ts_code, period)] = findings


def test_analyze_disclosure_day_builds_summary_for_coverage_events():
    service = AnalyzerService(
        fundamentals=FakeFundamentals(),
        store=FakeStore(),
        coverage_pool=["000001.SZ", "600000.SH"],
        calendar=FakeCalendar(),
    )

    summary = service.analyze_disclosure_day("20250821")

    assert summary.date == "20250821"
    assert summary.coverage_count == 2
    assert summary.disclosed_count == 2
    assert [card.ts_code for card in summary.cards] == ["000001.SZ", "600000.SH"]

def test_analyze_disclosure_day_returns_empty_summary_when_no_events():
    service = AnalyzerService(
        fundamentals=FakeFundamentals(),
        store=FakeStore(),
        coverage_pool=["000001.SZ"],
        calendar=EmptyCalendar(),
    )

    summary = service.analyze_disclosure_day("20250821")

    assert summary.coverage_count == 1
    assert summary.disclosed_count == 0
    assert summary.cards == []


def test_analyze_disclosure_day_preserves_disclosed_count_when_one_company_not_ready():
    class PartiallyReadyFundamentals:
        def fetch_snapshot(self, ts_code, period):
            if ts_code == "600000.SH":
                return PeriodSnapshot(ts_code=ts_code, period=period)
            return PeriodSnapshot(
                ts_code=ts_code,
                period=period,
                ann_date="20250821",
                revenue=100.0,
                net_profit=10.0,
                deducted_net_profit=9.0,
                gross_margin_pct=30.0,
                operating_cash_flow=8.0,
                accounts_receivable=20.0,
                inventory=15.0,
            )

    service = AnalyzerService(
        fundamentals=PartiallyReadyFundamentals(),
        store=FakeStore(),
        coverage_pool=["000001.SZ", "600000.SH"],
        calendar=FakeCalendar(),
    )

    summary = service.analyze_disclosure_day("20250821")

    assert summary.disclosed_count == 2
    assert [card.ts_code for card in summary.cards] == ["000001.SZ"]
