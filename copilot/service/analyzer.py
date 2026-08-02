from typing import Protocol

from pydantic import BaseModel

from copilot.checks.reconcile import CheckStatus, run_hard_checks
from copilot.config import RuleThresholds
from copilot.context import assemble_context, prior_quarter_period, prior_year_period
from copilot.datasource.fundamentals import CompanyProfile, TushareFetchCancelled
from copilot.industry import industry_for_ts_code, resolve_classification
from copilot.models import ClassificationResult, MappingStatus, PeriodSnapshot
from copilot.observability import RuntimeStats
from copilot.report.builder import CompanyCard, DailySummary, build_blocked_company_card, build_company_card, build_facts
from copilot.rules.registry import build_rules, evaluate_rule_results, run_rules
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureAnalysisBundle, DisclosureProgressEvent, DisclosureScanResult, build_analysis_bundle


class FundamentalsProvider(Protocol):
    def fetch_snapshot(self, ts_code: str, period: str) -> PeriodSnapshot: ...
    def fetch_company_profile(self, ts_code: str) -> CompanyProfile: ...


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
        industry_profiles: dict[str, str] | None = None,
        runtime_stats: RuntimeStats | None = None,
    ):
        self.fundamentals = fundamentals
        self.store = store
        self.thresholds = thresholds or RuleThresholds()
        self.coverage_pool = coverage_pool or []
        self.calendar = calendar
        self.company_industries = company_industries or {}
        self.industry_profiles = industry_profiles or {}
        self.runtime_stats = runtime_stats

    def _fetch_and_store(self, ts_code: str, period: str) -> PeriodSnapshot:
        if self.runtime_stats is not None:
            self.runtime_stats.record_snapshot_fetch()
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
        if self.runtime_stats is not None:
            self.runtime_stats.record_company()
        try:
            current = self._fetch_and_store(ts_code, period)
            self._fetch_and_store(ts_code, prior_quarter_period(period))
            self._fetch_and_store(ts_code, prior_year_period(period))

            if not self._current_ready(ts_code, current):
                message = f"Tushare 暂未返回 {ts_code} {period} 的完整财务快照"
                return CompanyAnalysisResult(
                    status=CompanyAnalysisStatus.DATA_NOT_READY,
                    message=message,
                    card=build_blocked_company_card(ts_code, period, message),
                )

            ctx = assemble_context(self.store, ts_code, period)
            ctx.metadata["industry"] = industry_for_ts_code(ts_code, self.company_industries).value
            check = run_hard_checks(ctx)
            if check.status != CheckStatus.OK:
                message = "；".join(check.messages)
                return CompanyAnalysisResult(
                    status=CompanyAnalysisStatus.DATA_INCOMPLETE,
                    message=message,
                    card=build_blocked_company_card(ts_code, period, message),
                )

            try:
                profile = self.fundamentals.fetch_company_profile(ts_code)
                classification = resolve_classification(profile.provider_industry, self.industry_profiles)
                company = profile.identity
            except Exception:
                classification = ClassificationResult(
                    provider="tushare.stock_basic",
                    mapping_status=MappingStatus.UNAVAILABLE,
                    rule_profile_id="generic",
                    industry_field="industry",
                )
                company = None

            rules = build_rules(self.thresholds)
            facts = build_facts(ctx)
            rule_results = evaluate_rule_results(ctx, rules, facts=facts)
            findings = run_rules(ctx, rules)
            self.store.replace_findings(ts_code, period, findings)
            card = build_company_card(
                ctx,
                findings,
                classification=classification,
                rule_results=rule_results,
                company=company,
            )
            return CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=card)
        except TushareFetchCancelled:
            raise
        except Exception as exc:
            message = str(exc)
            return CompanyAnalysisResult(
                status=CompanyAnalysisStatus.ERROR,
                message=message,
                card=build_blocked_company_card(ts_code, period, message),
            )

    def analyze_disclosure_day_bundle(
        self,
        date: str,
        progress_callback=None,
        should_cancel=None,
        should_pause=None,
        skip_ts_codes: set[str] | None = None,
    ) -> DisclosureAnalysisBundle:
        if self.calendar is None:
            return build_analysis_bundle(date, coverage_count=len(self.coverage_pool), results=[])
        skip_ts_codes = skip_ts_codes or set()
        events = [event for event in self.calendar.fetch_events(date, set(self.coverage_pool)) if event.ts_code not in skip_ts_codes]
        total_count = len(events)
        if progress_callback is not None:
            progress_callback(DisclosureProgressEvent(stage="events_loaded", processed_count=0, total_count=total_count))
        results = []
        for event in events:
            if should_cancel is not None and should_cancel():
                if progress_callback is not None:
                    progress_callback(DisclosureProgressEvent(stage="cancelled", processed_count=len(results), total_count=total_count))
                break
            if should_pause is not None and should_pause():
                if progress_callback is not None:
                    progress_callback(DisclosureProgressEvent(stage="paused", processed_count=len(results), total_count=total_count))
                break
            industry = industry_for_ts_code(event.ts_code, self.company_industries).value
            if progress_callback is not None:
                progress_callback(
                    DisclosureProgressEvent(
                        stage="company_started",
                        processed_count=len(results),
                        total_count=total_count,
                        ts_code=event.ts_code,
                        period=event.period,
                        industry=industry,
                    )
                )
            try:
                result = self.analyze_company(event.ts_code, event.period)
            except TushareFetchCancelled:
                if progress_callback is not None:
                    progress_callback(DisclosureProgressEvent(stage="cancelled", processed_count=len(results), total_count=total_count))
                break
            results.append((event.ts_code, event.period, industry, result))
            if progress_callback is not None:
                progress_callback(
                    DisclosureProgressEvent(
                        stage="company_completed",
                        processed_count=len(results),
                        total_count=total_count,
                        ts_code=event.ts_code,
                        period=event.period,
                        industry=industry,
                        status=result.status,
                        message=result.message,
                    )
                )
        return build_analysis_bundle(date=date, coverage_count=len(self.coverage_pool), results=results)

    def analyze_disclosure_day(self, date: str) -> DailySummary:
        return self.analyze_disclosure_day_bundle(date).summary

    def scan_disclosure_day(self, date: str) -> DisclosureScanResult:
        return self.analyze_disclosure_day_bundle(date).scan
