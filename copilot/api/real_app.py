from fastapi import HTTPException

from copilot.api.app import NotifyResult, create_app
from copilot.config import load_settings
from copilot.datasource.calendar import TushareDisclosureCalendarClient
from copilot.datasource.fundamentals import TushareFundamentalsClient
from copilot.datasource.tushare_client import TushareTokenMissing, create_tushare_pro
from copilot.eval.backtest import BacktestSummary
from copilot.notify.feishu import FeishuNotifier, render_formal_disclosure_text
from copilot.report.builder import build_daily_summary, build_quarterly_review
from copilot.rss.service import RssPollResult, RssPollService
from copilot.service.analyzer import AnalyzerService
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
                company_industries=self.settings.eval.company_industries,
            )
        self.rss_service = None
        if self.analyzer is not None:
            company_to_ts_code = self.settings.rss.company_names or {ts_code: ts_code for ts_code in self.settings.eval.coverage_pool}
            self.rss_service = RssPollService(
                feeds=self.settings.rss.feeds,
                max_entries=self.settings.rss.max_entries,
                company_to_ts_code=company_to_ts_code,
                analyzer=self.analyzer,
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
            raise HTTPException(status_code=503, detail="未配置 TUSHARE_TOKEN")
        result = self.analyzer.analyze_company(ts_code, period)
        if result.card is not None:
            self.cache.put_company(result.card)
        return result

    def analyze_disclosure_day(self, date):
        if self.analyzer is None:
            raise HTTPException(status_code=503, detail="未配置 TUSHARE_TOKEN")
        bundle = self.analyzer.analyze_disclosure_day_bundle(date)
        for card in bundle.summary.cards:
            self.cache.put_company(card)
        self.cache.put_daily(bundle.summary)
        return bundle.summary

    def scan_disclosure_day(self, date):
        if self.analyzer is None:
            raise HTTPException(status_code=503, detail="未配置 TUSHARE_TOKEN")
        return self.analyzer.analyze_disclosure_day_bundle(date).scan

    def poll_rss(self):
        if self.rss_service is None:
            return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])
        return self.rss_service.poll()

    def _send_feishu_text(self, text):
        webhook = self.settings.notify.feishu_webhook
        if not webhook:
            return False
        return FeishuNotifier(webhook).send_text(text)

    def notify_feishu_disclosure_day(self, date):
        if self.analyzer is None:
            raise HTTPException(status_code=503, detail="未配置 TUSHARE_TOKEN")
        bundle = self.analyzer.analyze_disclosure_day_bundle(date)
        for card in bundle.summary.cards:
            self.cache.put_company(card)
        self.cache.put_daily(bundle.summary)
        if bundle.summary.disclosed_count == 0 and bundle.scan.disclosed_count == 0:
            return NotifyResult(sent=False, reason="no_disclosures")
        if not self.settings.notify.feishu_webhook:
            return NotifyResult(sent=False, reason="webhook_not_configured")
        text = render_formal_disclosure_text(bundle.summary, bundle.scan, self.settings.eval.company_names)
        sent = self._send_feishu_text(text)
        return NotifyResult(sent=sent, reason="ok" if sent else "send_failed")


app = create_app(RealReportService())
