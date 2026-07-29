from copilot.api.app import create_app
from copilot.models import Context, Evidence, Finding, PeriodSnapshot, Severity
from copilot.report.builder import build_company_card, build_daily_summary


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


app = create_app(DemoReportService())
