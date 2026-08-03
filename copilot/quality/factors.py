from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from copilot.models import Context, Finding, RuleResult, RuleResultStatus, Severity


class FactorStatus(StrEnum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    ANOMALY = "ANOMALY"
    NOT_EVALUATED = "NOT_EVALUATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FactorObservation(BaseModel):
    label: str
    value: float | str | None
    unit: str | None = None
    period: str


class QualityFactor(BaseModel):
    factor_id: str
    label: str
    status: FactorStatus
    summary: str
    rule_ids: list[str]
    fact_ids: list[str]
    observations: list[FactorObservation] = Field(default_factory=list)
    reason_code: str | None = None
    reason: str | None = None


class QualityOverview(BaseModel):
    status: FactorStatus
    normal_count: int
    watch_count: int
    anomaly_count: int
    not_evaluated_count: int
    not_applicable_count: int
    summary: str


FACTOR_SPECS: tuple[dict[str, Any], ...] = (
    {
        "factor_id": "revenue_realization_quality",
        "label": "收入兑现质量",
        "rule_id": "receivable_revenue_divergence",
        "fact_ids": ["accounts_receivable", "revenue"],
        "normal": "应收账款增速未明显快于营业收入。",
        "watch": "应收账款增长快于营业收入，需要关注回款质量。",
        "anomaly": "应收账款增长明显快于营业收入，可能意味着回款压力或收入确认质量下降。",
        "not_evaluated": "缺少应收账款、营业收入或去年同期数据，无法判断收入兑现质量。",
        "observation": "应收/营收同比差",
    },
    {
        "factor_id": "inventory_match_quality",
        "label": "存货匹配质量",
        "rule_id": "inventory_revenue_divergence",
        "fact_ids": ["inventory", "revenue"],
        "normal": "存货增速未明显快于营业收入。",
        "watch": "存货增长快于营业收入，需要关注备货与销售匹配度。",
        "anomaly": "存货增长明显快于营业收入，可能意味着库存积压或需求走弱。",
        "not_evaluated": "缺少存货、营业收入或去年同期数据，无法判断存货匹配质量。",
        "observation": "存货/营收同比差",
    },
    {
        "factor_id": "cashflow_quality",
        "label": "现金质量",
        "rule_id": "cashflow_quality",
        "fact_ids": ["operating_cash_flow", "net_profit"],
        "normal": "经营现金流对净利润有基本支撑。",
        "watch": "经营现金流对净利润支撑不足，需要关注利润含金量。",
        "anomaly": "经营现金流对净利润支撑明显不足。",
        "not_evaluated": "缺少经营现金流或净利润数据，无法判断现金质量。",
        "observation": "经营现金流/净利润",
    },
    {
        "factor_id": "profitability_stability",
        "label": "盈利稳定性",
        "rule_id": "gross_margin_change",
        "fact_ids": ["gross_margin_pct"],
        "normal": "毛利率未出现超过阈值的同比异动。",
        "watch": "毛利率出现明显同比异动，需要关注价格、成本或产品结构变化。",
        "anomaly": "毛利率出现严重异动。",
        "not_evaluated": "缺少毛利率或去年同期数据，无法判断盈利稳定性。",
        "observation": "毛利率同比变动",
    },
    {
        "factor_id": "performance_direction_consistency",
        "label": "业绩方向一致性",
        "rule_id": "net_profit_revenue_direction",
        "fact_ids": ["revenue", "net_profit"],
        "normal": "营业收入与净利润增长方向一致。",
        "watch": "营业收入与净利润增长方向存在差异。",
        "anomaly": "营业收入与净利润增长方向背离，需要解释收入质量或费用/减值变化。",
        "not_evaluated": "缺少营业收入、净利润或去年同期数据，无法判断业绩方向一致性。",
        "observation": "营收/净利润同比",
    },
    {
        "factor_id": "profit_sustainability",
        "label": "利润可持续性",
        "rule_id": "non_recurring_profit_share",
        "fact_ids": ["net_profit", "deducted_net_profit"],
        "normal": "非经常性损益未对净利润形成过高贡献。",
        "watch": "非经常性损益占比偏高，需要关注利润可持续性。",
        "anomaly": "非经常性损益对净利润贡献明显偏高。",
        "not_evaluated": "缺少净利润或扣非净利润数据，无法判断利润可持续性。",
        "observation": "非经常性损益/净利润",
    },
)


_RULE_TO_SPEC = {spec["rule_id"]: spec for spec in FACTOR_SPECS}
_STATUS_RANK = {
    FactorStatus.ANOMALY: 0,
    FactorStatus.WATCH: 1,
    FactorStatus.NOT_EVALUATED: 2,
    FactorStatus.NOT_APPLICABLE: 3,
    FactorStatus.NORMAL: 4,
}


def _growth_gap(ctx: Context, left: str, right: str) -> float | None:
    if ctx.prior_year is None:
        return None
    left_yoy = ctx.current.growth_pct(left, ctx.prior_year)
    right_yoy = ctx.current.growth_pct(right, ctx.prior_year)
    if left_yoy is None or right_yoy is None:
        return None
    return round(left_yoy - right_yoy, 1)


def _observation_value(ctx: Context, rule_id: str) -> tuple[float | str | None, str | None]:
    if rule_id == "receivable_revenue_divergence":
        return _growth_gap(ctx, "accounts_receivable", "revenue"), "pct"
    if rule_id == "inventory_revenue_divergence":
        return _growth_gap(ctx, "inventory", "revenue"), "pct"
    if rule_id == "cashflow_quality":
        if ctx.current.net_profit in (None, 0) or ctx.current.operating_cash_flow is None:
            return None, "%"
        return round(ctx.current.operating_cash_flow / ctx.current.net_profit * 100.0, 1), "%"
    if rule_id == "gross_margin_change":
        if ctx.prior_year is None:
            return None, "pct"
        change = ctx.current.change_pct_points("gross_margin_pct", ctx.prior_year)
        return None if change is None else round(change, 1), "pct"
    if rule_id == "net_profit_revenue_direction":
        if ctx.prior_year is None:
            return None, None
        revenue_yoy = ctx.current.growth_pct("revenue", ctx.prior_year)
        net_profit_yoy = ctx.current.growth_pct("net_profit", ctx.prior_year)
        if revenue_yoy is None or net_profit_yoy is None:
            return None, None
        return f"营收 {revenue_yoy:+.1f}% / 净利 {net_profit_yoy:+.1f}%", None
    if rule_id == "non_recurring_profit_share":
        if ctx.current.net_profit in (None, 0) or ctx.current.deducted_net_profit is None:
            return None, "%"
        share = (ctx.current.net_profit - ctx.current.deducted_net_profit) / ctx.current.net_profit * 100.0
        return round(share, 1), "%"
    return None, None


def _factor_status(rule_result: RuleResult | None, finding: Finding | None) -> FactorStatus:
    if rule_result is None or rule_result.status in {RuleResultStatus.NOT_EVALUATED, RuleResultStatus.BLOCKED}:
        return FactorStatus.NOT_EVALUATED
    if rule_result.status == RuleResultStatus.MISS:
        return FactorStatus.NORMAL
    if finding is not None and finding.severity == Severity.RED:
        return FactorStatus.ANOMALY
    if finding is not None and finding.severity == Severity.YELLOW:
        return FactorStatus.WATCH
    return FactorStatus.WATCH


def build_quality_factors(ctx: Context, rule_results: list[RuleResult], findings: list[Finding]) -> list[QualityFactor]:
    result_by_rule = {result.rule_id: result for result in rule_results}
    finding_by_rule = {finding.rule_id: finding for finding in findings}
    factors: list[QualityFactor] = []
    for spec in FACTOR_SPECS:
        rule_id = spec["rule_id"]
        status = _factor_status(result_by_rule.get(rule_id), finding_by_rule.get(rule_id))
        value, unit = _observation_value(ctx, rule_id)
        observations = [
            FactorObservation(
                label=spec["observation"],
                value=value,
                unit=unit,
                period=ctx.current.period,
            )
        ]
        reason_code = None
        reason = None
        summary_key = status.value.lower()
        if status == FactorStatus.NOT_EVALUATED:
            reason_code = result_by_rule.get(rule_id).reason_code if result_by_rule.get(rule_id) else "RULE_NOT_EVALUATED"
            reason = result_by_rule.get(rule_id).reason if result_by_rule.get(rule_id) else spec["not_evaluated"]
            summary_key = "not_evaluated"
        factors.append(
            QualityFactor(
                factor_id=spec["factor_id"],
                label=spec["label"],
                status=status,
                summary=spec.get(summary_key, spec["not_evaluated"]),
                rule_ids=[rule_id],
                fact_ids=list(spec["fact_ids"]),
                observations=observations,
                reason_code=reason_code,
                reason=reason,
            )
        )
    return factors


def build_quality_overview(factors: list[QualityFactor]) -> QualityOverview:
    normal_count = sum(1 for factor in factors if factor.status == FactorStatus.NORMAL)
    watch_count = sum(1 for factor in factors if factor.status == FactorStatus.WATCH)
    anomaly_count = sum(1 for factor in factors if factor.status == FactorStatus.ANOMALY)
    not_evaluated_count = sum(1 for factor in factors if factor.status == FactorStatus.NOT_EVALUATED)
    not_applicable_count = sum(1 for factor in factors if factor.status == FactorStatus.NOT_APPLICABLE)
    if anomaly_count:
        status = FactorStatus.ANOMALY
    elif watch_count:
        status = FactorStatus.WATCH
    elif not_evaluated_count or not_applicable_count:
        status = FactorStatus.NOT_EVALUATED
    else:
        status = FactorStatus.NORMAL
    parts = [f"异常 {anomaly_count} 项", f"关注 {watch_count} 项", f"正常 {normal_count} 项"]
    if not_evaluated_count:
        parts.append(f"不可计算 {not_evaluated_count} 项")
    if not_applicable_count:
        parts.append(f"不适用 {not_applicable_count} 项")
    return QualityOverview(
        status=status,
        normal_count=normal_count,
        watch_count=watch_count,
        anomaly_count=anomaly_count,
        not_evaluated_count=not_evaluated_count,
        not_applicable_count=not_applicable_count,
        summary=" / ".join(parts),
    )


def order_factors(factors: list[QualityFactor]) -> list[QualityFactor]:
    return sorted(factors, key=lambda factor: (_STATUS_RANK[factor.status], factor.factor_id))
