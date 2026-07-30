from copilot.api.app import NotifyResult, create_app
from copilot.eval.backtest import BacktestCompanyResult, BacktestSummary
from copilot.models import Context, Evidence, Finding, PeriodSnapshot, Severity
from copilot.report.builder import build_company_card, build_daily_summary, build_quarterly_review
from copilot.rss.service import RssPollResult
from copilot.service.analyzer import CompanyAnalysisResult, CompanyAnalysisStatus
from copilot.service.disclosure_scan import DisclosureScanEvent, build_scan_result


class DemoReportService:
    def __init__(self):
        snapshot = PeriodSnapshot(
            ts_code="000001.SZ",
            period="20250630",
            ann_date="20250821",
            revenue=128.4,
            net_profit=15.2,
            deducted_net_profit=11.8,
            gross_margin_pct=31.2,
            operating_cash_flow=4.1,
            accounts_receivable=47.0,
            inventory=20.0,
        )
        finding = Finding(
            rule_id="cashflow_quality",
            severity=Severity.YELLOW,
            title="现金流质量偏弱",
            detail="经营活动现金流净额/净利润 = 27.0%，低于 50.0%",
            evidence=[Evidence(source="tushare.cashflow", field="operating_cash_flow", period="20250630", value=4.1)],
            score=23.0,
        )
        self.card = build_company_card(Context(ts_code="000001.SZ", current=snapshot), [finding], attribution="增长主要来自收入改善，但现金回款未同步。")
        self.summary = build_daily_summary("20250821", 42, [self.card])
        self.quarterly = build_quarterly_review(
            BacktestSummary(
                start_date="20250801",
                end_date="20250831",
                coverage_count=42,
                disclosed_count=1,
                ok_count=1,
                data_incomplete_count=0,
                finding_count=1,
                finding_distribution={"cashflow_quality": 1},
                company_results=[BacktestCompanyResult(ts_code="000001.SZ", period="20250630", status="OK", findings=[finding])],
            ),
            precision_pct=88.9,
        )

    def get_company_card(self, ts_code, period):
        if ts_code == self.card.ts_code and period == self.card.period:
            return self.card
        return None

    def get_daily_summary(self, date):
        if date == self.summary.date:
            return self.summary
        return None

    def get_evidence(self, ts_code, period, rule_id):
        for finding in self.card.findings:
            if finding.rule_id == rule_id:
                return finding.evidence
        return []

    def get_quarterly_review(self):
        return self.quarterly

    def analyze_company(self, ts_code, period):
        if ts_code == self.card.ts_code and period == self.card.period:
            return CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=self.card)
        return CompanyAnalysisResult(status=CompanyAnalysisStatus.DATA_NOT_READY, message="demo service only contains 000001.SZ 20250630")

    def analyze_disclosure_day(self, date):
        if date == self.summary.date:
            return self.summary
        return build_daily_summary(date, 42, [])

    def scan_disclosure_day(self, date):
        events = []
        if date == self.summary.date:
            events.append(
                DisclosureScanEvent(
                    ts_code=self.card.ts_code,
                    period=self.card.period,
                    status=CompanyAnalysisStatus.OK,
                    message="ok",
                    has_card=True,
                    industry="generic",
                )
            )
        return build_scan_result(date=date, coverage_count=42, events=events)

    def poll_rss(self):
        return RssPollResult(seen_count=0, matched_count=0, analyzed_count=0, pending_count=0, events=[])

    def notify_feishu_disclosure_day(self, date):
        if date != self.summary.date:
            return NotifyResult(sent=False, reason="no_disclosures")
        return NotifyResult(sent=False, reason="webhook_not_configured")


app = create_app(DemoReportService())
