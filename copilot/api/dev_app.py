from copilot.api.app import AppMeta, FeishuPreview, NotifyResult, create_app
from copilot.eval.backtest import BacktestCompanyResult, BacktestSummary
from copilot.models import Context, Evidence, Finding, PeriodSnapshot, Severity
from copilot.notify.feishu import render_formal_disclosure_text
from copilot.report.builder import build_company_card, build_quarterly_review
from copilot.scheduler import DisclosureAutomationJob, run_disclosure_automation_job
from copilot.rss.service import RssPollResult
from copilot.service.analyzer import CompanyAnalysisResult, CompanyAnalysisStatus
from copilot.service.disclosure_jobs import DisclosureJobStore
from copilot.service.disclosure_scan import build_analysis_bundle
from copilot.eval.manual_review import ReviewLabel, compute_precision_breakdown
from copilot.service.review_store import StoredReviewLabel

DEMO_DATE = "20250821"
DEMO_PERIOD = "20250630"

COMPANY_NAMES = {
    "000001.SZ": "平安银行",
    "603026.SH": "石大胜华",
    "600151.SH": "航天机电",
    "600032.SH": "浙江新能",
    "603958.SH": "哈森股份",
    "600232.SH": "金鹰股份",
}


def _snapshot(ts_code: str, **overrides) -> PeriodSnapshot:
    base = dict(
        ts_code=ts_code,
        period=DEMO_PERIOD,
        ann_date=DEMO_DATE,
        revenue=128.4,
        net_profit=15.2,
        deducted_net_profit=11.8,
        gross_margin_pct=31.2,
        operating_cash_flow=4.1,
        accounts_receivable=47.0,
        inventory=20.0,
    )
    base.update(overrides)
    return PeriodSnapshot(**base)


def _finding(rule_id: str, severity: Severity, title: str, detail: str, field: str, value: float, score: float) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        title=title,
        detail=detail,
        evidence=[Evidence(source=f"tushare.{field}", field=field, period=DEMO_PERIOD, value=value)],
        score=score,
    )


def _build_demo_results():
    receivable = _finding(
        "receivable_divergence",
        Severity.RED,
        "应收账款增速显著高于营收",
        "应收账款同比 +82.4%，营收同比 +11.2%，差值 71.2 个百分点，超过阈值 30.0",
        "accounts_receivable",
        47.0,
        88.0,
    )
    cashflow = _finding(
        "cashflow_quality",
        Severity.RED,
        "现金流质量偏弱",
        "经营活动现金流净额/净利润 = 27.0%，低于 50.0%",
        "operating_cash_flow",
        4.1,
        73.0,
    )
    inventory = _finding(
        "inventory_divergence",
        Severity.YELLOW,
        "存货增速高于营收",
        "存货同比 +48.6%，营收同比 +11.2%，差值 37.4 个百分点",
        "inventory",
        20.0,
        41.0,
    )
    margin = _finding(
        "gross_margin_change",
        Severity.YELLOW,
        "毛利率环比下滑",
        "毛利率由 37.9% 降至 31.2%，下滑 6.7 个百分点，超过阈值 5.0",
        "gross_margin_pct",
        31.2,
        32.0,
    )

    def card(ts_code, findings):
        return build_company_card(
            Context(ts_code=ts_code, current=_snapshot(ts_code)),
            findings,
            attribution="收入增长主要来自新签订单交付，但回款与产能备货节奏未同步，需追问账期与客户集中度。",
        )

    ok = CompanyAnalysisStatus.OK
    return [
        ("603026.SH", DEMO_PERIOD, "generic", CompanyAnalysisResult(status=ok, message="ok", card=card("603026.SH", [receivable, cashflow]))),
        ("600151.SH", DEMO_PERIOD, "generic", CompanyAnalysisResult(status=ok, message="ok", card=card("600151.SH", [cashflow]))),
        ("600032.SH", DEMO_PERIOD, "generic", CompanyAnalysisResult(status=ok, message="ok", card=card("600032.SH", [inventory, margin]))),
        ("603958.SH", DEMO_PERIOD, "generic", CompanyAnalysisResult(status=ok, message="ok", card=card("603958.SH", [margin]))),
        ("600232.SH", DEMO_PERIOD, "generic", CompanyAnalysisResult(status=ok, message="ok", card=card("600232.SH", []))),
        (
            "000001.SZ",
            DEMO_PERIOD,
            "bank",
            CompanyAnalysisResult(
                status=CompanyAnalysisStatus.DATA_NOT_READY,
                message="Tushare 暂未返回 000001.SZ 20250630 的完整财务快照",
            ),
        ),
    ]


class DemoReportService:
    def __init__(self):
        self.results = _build_demo_results()
        self.bundle = build_analysis_bundle(date=DEMO_DATE, coverage_count=len(COMPANY_NAMES), results=self.results)
        self.summary = self.bundle.summary
        self.cards = {(card.ts_code, card.period): card for card in self.summary.cards}
        self.job_store = DisclosureJobStore(company_names=COMPANY_NAMES)
        self.review_labels = {}
        first_finding = self.summary.cards[0].findings[0]
        self.quarterly = build_quarterly_review(
            BacktestSummary(
                start_date="20250801",
                end_date="20250831",
                coverage_count=len(COMPANY_NAMES),
                disclosed_count=len(self.results),
                ok_count=self.bundle.scan.ok_count,
                data_incomplete_count=self.bundle.scan.data_incomplete_count,
                finding_count=sum(len(card.findings) for card in self.summary.cards),
                finding_distribution={"cashflow_quality": 2, "gross_margin_change": 2, "receivable_divergence": 1, "inventory_divergence": 1},
                company_results=[
                    BacktestCompanyResult(ts_code="603026.SH", period=DEMO_PERIOD, status="OK", findings=[first_finding])
                ],
            ),
            precision_pct=88.9,
        )

    def get_company_card(self, ts_code, period):
        return self.cards.get((ts_code, period))

    def get_daily_summary(self, date):
        if date == self.summary.date:
            return self.summary
        return None

    def get_evidence(self, ts_code, period, rule_id):
        card = self.get_company_card(ts_code, period)
        if card is None:
            return []
        for finding in card.findings:
            if finding.rule_id == rule_id:
                return finding.evidence
        return []

    def get_quarterly_review(self):
        return self.quarterly

    def get_meta(self):
        return AppMeta(coverage_count=len(COMPANY_NAMES), company_names=COMPANY_NAMES, tushare_ready=False, feishu_ready=False)

    def analyze_company(self, ts_code, period):
        card = self.get_company_card(ts_code, period)
        if card is not None:
            return CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=card)
        return CompanyAnalysisResult(
            status=CompanyAnalysisStatus.DATA_NOT_READY,
            message=f"demo service 未包含 {ts_code} {period}",
        )

    def analyze_disclosure_day_bundle(self, date):
        if date == self.summary.date:
            return self.bundle
        return build_analysis_bundle(date=date, coverage_count=len(COMPANY_NAMES), results=[])

    def analyze_disclosure_day(self, date):
        return self.analyze_disclosure_day_bundle(date).summary

    def scan_disclosure_day(self, date):
        return self.analyze_disclosure_day_bundle(date).scan

    def start_disclosure_day_job(self, date):
        return self.job_store.start(date)

    def run_disclosure_day_job(self, job_id):
        job = self.job_store.get(job_id)
        bundle = self.analyze_disclosure_day_bundle(job.date)
        return self.job_store.mark_completed(job.job_id, bundle)

    def list_disclosure_day_jobs(self, limit=20):
        return self.job_store.list_recent(limit)

    def get_disclosure_day_job(self, job_id):
        return self.job_store.get(job_id)

    def cancel_disclosure_day_job(self, job_id):
        return self.job_store.request_cancel(job_id)

    def upsert_review_label(self, label):
        stored = StoredReviewLabel(**label.model_dump(), updated_at=0.0)
        self.review_labels[(stored.ts_code, stored.period, stored.rule_id)] = stored
        return stored

    def list_review_labels(self, ts_code=None, period=None):
        labels = list(self.review_labels.values())
        if ts_code is not None:
            labels = [label for label in labels if label.ts_code == ts_code]
        if period is not None:
            labels = [label for label in labels if label.period == period]
        return labels

    def delete_review_label(self, ts_code, period, rule_id):
        return self.review_labels.pop((ts_code, period, rule_id), None) is not None

    def get_review_metrics(self, ts_code=None, period=None):
        labels = list(self.review_labels.values())
        if ts_code is not None:
            labels = [label for label in labels if label.ts_code == ts_code]
        if period is not None:
            labels = [label for label in labels if label.period == period]
        return compute_precision_breakdown([
            ReviewLabel(
                ts_code=label.ts_code,
                period=label.period,
                rule_id=label.rule_id,
                label=label.label,
                notes=label.notes,
                severity=label.severity,
                industry=label.industry,
            )
            for label in labels
        ])

    def run_disclosure_automation(self, date, notify=True):
        return run_disclosure_automation_job(DisclosureAutomationJob(date=date, notify=notify), self)

    def poll_rss(self):
        return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])

    def list_notify_logs(self, limit=20):
        return []

    def verify_feishu_callback_token(self, token):
        return True

    def verify_automation_trigger_token(self, token):
        return token == "dev-automation-token"

    def preview_feishu_disclosure_day(self, date):
        bundle = self.analyze_disclosure_day_bundle(date)
        if bundle.scan.disclosed_count == 0:
            return FeishuPreview(date=date, text="", sendable=False, reason="no_disclosures")
        text = render_formal_disclosure_text(bundle.summary, bundle.scan, COMPANY_NAMES)
        return FeishuPreview(date=date, text=text, sendable=False, reason="webhook_not_configured")

    def notify_feishu_disclosure_day(self, date):
        if date != self.summary.date:
            return NotifyResult(sent=False, reason="no_disclosures")
        return NotifyResult(sent=False, reason="webhook_not_configured")


app = create_app(DemoReportService())
