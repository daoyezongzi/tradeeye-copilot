from copilot.api.app import create_app
from copilot.config import load_settings
from copilot.datasource.calendar import TushareDisclosureCalendarClient
from copilot.datasource.fundamentals import TushareFundamentalsClient
from copilot.datasource.tushare_client import TushareTokenMissing, create_tushare_pro
from copilot.eval.backtest import BacktestSummary
from copilot.report.builder import build_daily_summary, build_quarterly_review
from copilot.service.analyzer import AnalyzerService, CompanyAnalysisResult, CompanyAnalysisStatus
from copilot.service.report_cache import ReportCache
from copilot.store.sqlite import SQLiteStore


class RealReportService:
    def __init__(self):
        self.settings = load_settings()
        self.cache = ReportCache()
        self.store = SQLiteStore(self.settings.database.path)
        self.store.init_schema()
        try:
            pro = create_tushare_pro(self.settings.tushare.token)
        except TushareTokenMissing:
            pro = None
        self.analyzer = None
        if pro is not None:
            self.analyzer = AnalyzerService(
                fundamentals=TushareFundamentalsClient(pro, max_retries=self.settings.tushare.max_retries),
                store=self.store,
                thresholds=self.settings.rules.thresholds,
                coverage_pool=self.settings.eval.coverage_pool,
                calendar=TushareDisclosureCalendarClient(pro),
            )

    def get_company_card(self, ts_code, period):
        return self.cache.get_company(ts_code, period)

    def get_daily_summary(self, date):
        return self.cache.get_daily(date)

    def get_evidence(self, ts_code, period, rule_id):
        card = self.cache.get_company(ts_code, period)
        if card is None:
            return []
        for finding in card.findings:
            if finding.rule_id == rule_id:
                return finding.evidence
        return []

    def get_quarterly_review(self):
        return build_quarterly_review(
            BacktestSummary(
                start_date=self.settings.eval.start_date,
                end_date=self.settings.eval.end_date,
                coverage_count=len(self.settings.eval.coverage_pool),
                disclosed_count=0,
                ok_count=0,
                data_incomplete_count=0,
                finding_count=0,
                finding_distribution={},
                company_results=[],
            ),
            precision_pct=None,
        )

    def analyze_company(self, ts_code, period):
        if self.analyzer is None:
            return CompanyAnalysisResult(status=CompanyAnalysisStatus.ERROR, message="未配置 TUSHARE_TOKEN")
        result = self.analyzer.analyze_company(ts_code, period)
        if result.card is not None:
            self.cache.put_company(result.card)
        return result

    def analyze_disclosure_day(self, date):
        if self.analyzer is None:
            summary = build_daily_summary(date, len(self.settings.eval.coverage_pool), [])
            self.cache.put_daily(summary)
            return summary
        summary = self.analyzer.analyze_disclosure_day(date)
        for card in summary.cards:
            self.cache.put_company(card)
        self.cache.put_daily(summary)
        return summary


app = create_app(RealReportService())
