from copilot.models import PeriodSnapshot
from copilot.observability import RuntimeStats
from copilot.service.analyzer import AnalyzerService


def test_runtime_stats_records_company_and_snapshot_counts():
    stats = RuntimeStats()
    stats.record_company()
    stats.record_snapshot_fetch()
    stats.record_snapshot_fetch()

    assert stats.company_count == 1
    assert stats.snapshot_fetch_count == 2
    assert stats.as_lines() == ["companies=1", "snapshot_fetches=2"]


class StatsFundamentals:
    def fetch_snapshot(self, ts_code, period):
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


class StatsStore:
    def __init__(self):
        self.snapshots = {}

    def upsert_snapshot(self, snapshot):
        self.snapshots[(snapshot.ts_code, snapshot.period)] = snapshot

    def get_snapshot(self, ts_code, period):
        return self.snapshots.get((ts_code, period))

    def replace_findings(self, ts_code, period, findings):
        pass


def test_analyzer_records_runtime_stats():
    stats = RuntimeStats()
    service = AnalyzerService(fundamentals=StatsFundamentals(), store=StatsStore(), runtime_stats=stats)

    service.analyze_company("603026.SH", "20250630")

    assert stats.company_count == 1
    assert stats.snapshot_fetch_count == 3
