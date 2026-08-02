from copilot.config import RuleThresholds
from copilot.models import Context, Fact, FactStatus, Finding, RuleResult, RuleResultStatus, Severity
from copilot.report.builder import build_facts
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


def evaluate_rule_results(ctx: Context, rules: list[Rule], facts: list[Fact] | None = None) -> list[RuleResult]:
    fact_map = {fact.fact_id: fact for fact in (facts or build_facts(ctx))}
    results = []
    for rule in rules:
        missing = [
            fact_id
            for fact_id in rule.required_fact_ids
            if fact_map.get(fact_id) is None or fact_map[fact_id].status != FactStatus.VERIFIED
        ]
        if missing:
            results.append(
                RuleResult(
                    rule_id=rule.id,
                    status=RuleResultStatus.NOT_EVALUATED,
                    required_fact_ids=list(rule.required_fact_ids),
                    related_fact_ids=missing,
                    reason_code="REQUIRED_FACT_UNAVAILABLE",
                    reason="；".join(missing),
                )
            )
            continue
        finding = rule.evaluate(ctx)
        results.append(
            RuleResult(
                rule_id=rule.id,
                status=RuleResultStatus.HIT if finding is not None else RuleResultStatus.MISS,
                required_fact_ids=list(rule.required_fact_ids),
            )
        )
    return results
