from typing import Protocol

from pydantic import BaseModel

from copilot.checks.reconcile import CheckStatus, run_hard_checks
from copilot.config import RuleThresholds
from copilot.context import assemble_context, prior_quarter_period, prior_year_period
from copilot.industry import industry_for_ts_code
from copilot.models import PeriodSnapshot
from copilot.report.builder import CompanyCard, DailySummary, build_company_card, build_daily_summary
from copilot.rules.registry import build_rules, run_rules
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureAnalysisBundle, DisclosureScanResult, build_analysis_bundle


class FundamentalsProvider(Protocol):
    def fetch_snapshot(self, ts_code: str, period: str) -> PeriodSnapshot: ...


class SnapshotStore(Protocol):
    def upsert_snapshot(self, snapshot: PeriodSnapshot) -> None: ...
    def get_snapshot(self, ts_code: str, period: str) -> PeriodSnapshot | None: ...
    def replace_findings(self, ts_code: str, period: str, findings) -> None: ...


class CompanyAnalysisResult(BaseModel):
    status: CompanyAnalysisStatus
    message: str
    card: CompanyCard | None = None


_GENERIC_REQUIRED_CURRENT_FIELDS = ["revenue", "net_profit", "gross_margin_pct", "operating_cash_flow"]
_BANK_REQUIRED_CURRENT_FIELDS = ["revenue", "net_profit", "operating_cash_flow"]


class AnalyzerService:
    def __init__(
        self,
        fundamentals: FundamentalsProvider,
        store: SnapshotStore,
        thresholds: RuleThresholds | None = None,
        coverage_pool: list[str] | None = None,
        calendar=None,
        company_industries: dict[str, str] | None = None,
    ):
        self.fundamentals = fundamentals
        self.store = store
        self.thresholds = thresholds or RuleThresholds()
        self.coverage_pool = coverage_pool or []
        self.calendar = calendar
        self.company_industries = company_industries or {}

    def _fetch_and_store(self, ts_code: str, period: str) -> PeriodSnapshot:
        snapshot = self.fundamentals.fetch_snapshot(ts_code, period)
        self.store.upsert_snapshot(snapshot)
        return snapshot

    def _required_current_fields(self, ts_code: str) -> list[str]:
        industry = industry_for_ts_code(ts_code, self.company_industries)
        if industry.value == "bank":
            return _BANK_REQUIRED_CURRENT_FIELDS
        return _GENERIC_REQUIRED_CURRENT_FIELDS

    def _current_ready(self, ts_code: str, snapshot: PeriodSnapshot) -> bool:
        return all(snapshot.value(field) is not None for field in self._required_current_fields(ts_code))

    def analyze_company(self, ts_code: str, period: str) -> CompanyAnalysisResult:
        try:
            current = self._fetch_and_store(ts_code, period)
            self._fetch_and_store(ts_code, prior_quarter_period(period))
            self._fetch_and_store(ts_code, prior_year_period(period))

            if not self._current_ready(ts_code, current):
                return CompanyAnalysisResult(
                    status=CompanyAnalysisStatus.DATA_NOT_READY,
                    message=f"Tushare 暂未返回 {ts_code} {period} 的完整财务快照",
                )

            ctx = assemble_context(self.store, ts_code, period)
            ctx.metadata["industry"] = industry_for_ts_code(ts_code, self.company_industries).value
            check = run_hard_checks(ctx)
            if check.status != CheckStatus.OK:
                return CompanyAnalysisResult(
                    status=CompanyAnalysisStatus.DATA_INCOMPLETE,
                    message="；".join(check.messages),
                )

            findings = run_rules(ctx, build_rules(self.thresholds))
            self.store.replace_findings(ts_code, period, findings)
            card = build_company_card(ctx, findings)
            return CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=card)
        except Exception as exc:
            return CompanyAnalysisResult(status=CompanyAnalysisStatus.ERROR, message=str(exc))

    def analyze_disclosure_day_bundle(self, date: str) -> DisclosureAnalysisBundle:
        if self.calendar is None:
            return build_analysis_bundle(date, coverage_count=len(self.coverage_pool), results=[])
        events = self.calendar.fetch_events(date, set(self.coverage_pool))
        results = []
        for event in events:
            result = self.analyze_company(event.ts_code, event.period)
            industry = industry_for_ts_code(event.ts_code, self.company_industries).value
            results.append((event.ts_code, event.period, industry, result))
        return build_analysis_bundle(date=date, coverage_count=len(self.coverage_pool), results=results)

    def analyze_disclosure_day(self, date: str) -> DailySummary:
        return self.analyze_disclosure_day_bundle(date).summary

    def scan_disclosure_day(self, date: str) -> DisclosureScanResult:
        return self.analyze_disclosure_day_bundle(date).scan
