from fastapi import HTTPException

from copilot.api.app import AppMeta, FeishuPreview, NotifyResult, create_app
from copilot.config import load_settings
from copilot.datasource.calendar import TushareDisclosureCalendarClient
from copilot.datasource.fundamentals import TushareFundamentalsClient
from copilot.datasource.tushare_client import TushareTokenMissing, create_tushare_pro
from copilot.eval.backtest import BacktestSummary
from copilot.notify.feishu import FeishuNotifier, render_disclosure_interactive_card, render_formal_disclosure_text, split_feishu_text
from copilot.report.builder import build_daily_summary, build_quarterly_review
from copilot.scheduler import DisclosureAutomationJob, run_disclosure_automation_job
from copilot.rss.service import RssPollResult, RssPollService
from copilot.service.analyzer import AnalyzerService
from copilot.service.disclosure_jobs import SQLiteDisclosureJobStore
from copilot.service.notify_store import NotifyLogStore
from copilot.service.report_cache import ReportCache
from copilot.service.review_metrics import ReviewMetricsService
from copilot.service.review_store import ReviewLabelStore
from copilot.store.sqlite import SQLiteStore


class RealReportService:
    def __init__(self):
        self.settings = load_settings()
        self.cache = ReportCache()
        self.job_store = SQLiteDisclosureJobStore(
            self.settings.database.path,
            company_names=getattr(self.settings.eval, "company_names", {}),
        )
        self.job_store.init_schema()
        self.review_store = ReviewLabelStore(self.settings.database.path)
        self.review_store.init_schema()
        self.review_metrics = ReviewMetricsService(self.review_store)
        self.notify_store = NotifyLogStore(self.settings.database.path)
        self.notify_store.init_schema()
        self.store = SQLiteStore(self.settings.database.path)
        self.store.init_schema()
        try:
            pro = create_tushare_pro(self.settings.tushare.token)
        except TushareTokenMissing:
            pro = None
        self.analyzer = None
        if pro is not None:
            self.analyzer = AnalyzerService(
                fundamentals=TushareFundamentalsClient(
                    pro,
                    max_retries=self.settings.tushare.max_retries,
                    progress_callback=self.job_store.apply_table_progress,
                    should_cancel=self.job_store.active_should_cancel,
                ),
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

    def get_meta(self):
        return AppMeta(
            coverage_count=len(self.settings.eval.coverage_pool),
            company_names=self.settings.eval.company_names,
            tushare_ready=self.analyzer is not None,
            feishu_ready=bool(self.settings.notify.feishu_webhook),
        )

    def analyze_disclosure_day_bundle(self, date):
        if self.analyzer is None:
            raise HTTPException(status_code=503, detail="未配置 TUSHARE_TOKEN")
        bundle = self.analyzer.analyze_disclosure_day_bundle(date)
        self._cache_bundle(bundle)
        return bundle

    def _cache_bundle(self, bundle):
        for card in bundle.summary.cards:
            self.cache.put_company(card)
        self.cache.put_daily(bundle.summary)

    def start_disclosure_day_job(self, date):
        if self.analyzer is None:
            raise HTTPException(status_code=503, detail="未配置 TUSHARE_TOKEN")
        return self.job_store.start(date)

    def run_disclosure_day_job(self, job_id):
        job = self.job_store.get(job_id)
        self.job_store.set_active(job_id)
        try:
            bundle = self.analyzer.analyze_disclosure_day_bundle(
                job.date,
                progress_callback=lambda event: self.job_store.apply_progress(job_id, event),
                should_cancel=lambda: self.job_store.should_cancel(job_id),
            )
            self._cache_bundle(bundle)
            if self.job_store.should_cancel(job_id):
                return self.job_store.mark_cancelled(job_id, bundle)
            return self.job_store.mark_completed(job_id, bundle)
        except Exception as exc:
            return self.job_store.mark_failed(job_id, str(exc))
        finally:
            self.job_store.set_active(None)

    def list_disclosure_day_jobs(self, limit=20):
        return self.job_store.list_recent(limit)

    def get_disclosure_day_job(self, job_id):
        return self.job_store.get(job_id)

    def cancel_disclosure_day_job(self, job_id):
        return self.job_store.request_cancel(job_id)

    def analyze_disclosure_day(self, date):
        return self.analyze_disclosure_day_bundle(date).summary

    def scan_disclosure_day(self, date):
        return self.analyze_disclosure_day_bundle(date).scan

    def upsert_review_label(self, label):
        return self.review_store.upsert_label(**label.model_dump())

    def list_review_labels(self, ts_code=None, period=None):
        return self.review_store.list_labels(ts_code=ts_code, period=period)

    def delete_review_label(self, ts_code, period, rule_id):
        return self.review_store.delete_label(ts_code=ts_code, period=period, rule_id=rule_id)

    def get_review_metrics(self, ts_code=None, period=None):
        return self.review_metrics.compute_breakdown(ts_code=ts_code, period=period)

    def run_disclosure_automation(self, date, notify=True):
        return run_disclosure_automation_job(DisclosureAutomationJob(date=date, notify=notify), self)

    def poll_rss(self):
        if self.rss_service is None:
            return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])
        return self.rss_service.poll()

    def _send_feishu_text_parts(self, parts):
        webhook = self.settings.notify.feishu_webhook
        if not webhook:
            return False
        return FeishuNotifier(webhook).send_text_parts(parts)

    def _send_feishu_interactive(self, payload):
        webhook = self.settings.notify.feishu_webhook
        if not webhook:
            return False
        return FeishuNotifier(webhook).send_interactive(payload)

    def _render_disclosure_text(self, date):
        bundle = self.analyze_disclosure_day_bundle(date)
        if bundle.summary.disclosed_count == 0 and bundle.scan.disclosed_count == 0:
            return "", "no_disclosures"
        if not self.settings.notify.feishu_webhook:
            reason = "webhook_not_configured"
        else:
            reason = "ok"
        text = render_formal_disclosure_text(bundle.summary, bundle.scan, self.settings.eval.company_names)
        return text, reason

    def list_notify_logs(self, limit=20):
        return self.notify_store.list_recent(limit)

    def verify_feishu_callback_token(self, token):
        expected = getattr(self.settings.notify, "feishu_verification_token", None)
        return expected is None or token == expected

    def preview_feishu_disclosure_day(self, date):
        text, reason = self._render_disclosure_text(date)
        return FeishuPreview(date=date, text=text, sendable=reason == "ok", reason=reason)

    def notify_feishu_disclosure_day(self, date):
        channel = "feishu_disclosure_day"
        if self.notify_store.already_sent(channel, date):
            return NotifyResult(sent=False, reason="already_sent")
        bundle = self.analyze_disclosure_day_bundle(date)
        if bundle.summary.disclosed_count == 0 and bundle.scan.disclosed_count == 0:
            self.notify_store.record_attempt(channel, date, sent=False, reason="no_disclosures")
            return NotifyResult(sent=False, reason="no_disclosures")
        if not self.settings.notify.feishu_webhook:
            self.notify_store.record_attempt(channel, date, sent=False, reason="webhook_not_configured")
            return NotifyResult(sent=False, reason="webhook_not_configured")
        payload = render_disclosure_interactive_card(
            bundle.summary,
            self.settings.eval.company_names,
            base_url=getattr(self.settings.notify, "public_base_url", None),
        )
        sent = self._send_feishu_interactive(payload)
        reason = "ok" if sent else "send_failed"
        self.notify_store.record_attempt(channel, date, sent=sent, reason=reason)
        return NotifyResult(sent=sent, reason=reason)


app = create_app(RealReportService())
