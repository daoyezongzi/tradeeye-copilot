from copilot.config import RuleThresholds
from copilot.models import Context, Finding, Severity
from copilot.rules.base import Rule
from copilot.rules.caliber import NonRecurringProfitShareRule
from copilot.rules.divergence import (
    CashflowQualityRule,
    GrossMarginChangeRule,
    InventoryRevenueDivergenceRule,
    NetProfitRevenueDirectionRule,
    ReceivableRevenueDivergenceRule,
)


def build_rules(thresholds: RuleThresholds) -> list[Rule]:
    return [
        ReceivableRevenueDivergenceRule(threshold_pct=thresholds.receivable_revenue_gap_pct),
        InventoryRevenueDivergenceRule(threshold_pct=thresholds.inventory_revenue_gap_pct),
        CashflowQualityRule(threshold_pct=thresholds.ocf_to_net_profit_pct),
        GrossMarginChangeRule(threshold_pct=thresholds.gross_margin_change_pct),
        NetProfitRevenueDirectionRule(),
        NonRecurringProfitShareRule(threshold_pct=thresholds.non_recurring_profit_share_pct),
    ]


def run_rules(ctx: Context, rules: list[Rule]) -> list[Finding]:
    severity_rank = {Severity.RED: 0, Severity.YELLOW: 1, Severity.INFO: 2}
    findings = [finding for rule in rules if (finding := rule.evaluate(ctx)) is not None]
    return sorted(findings, key=lambda finding: (severity_rank[finding.severity], -finding.score, finding.rule_id))
