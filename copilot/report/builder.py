from pydantic import BaseModel, Field, model_validator

from copilot.eval.backtest import BacktestSummary
from copilot.models import (
    CardStatus,
    ClassificationResult,
    CompanyIdentity,
    Context,
    Fact,
    FactEvidence,
    FactStatus,
    Finding,
    RuleResult,
    Severity,
)


class CompanyCard(BaseModel):
    ts_code: str
    period: str
    fact_line: str
    findings: list[Finding]
    attribution: str | None = None
    market_line: str = "市场数据待接入"
    max_severity: Severity | None = None
    max_score: float = 0.0
    company: CompanyIdentity | None = None
    classification: ClassificationResult | None = None
    card_status: CardStatus = CardStatus.OK
    facts: list[Fact] = Field(default_factory=list)
    rule_results: list[RuleResult] = Field(default_factory=list)
    @model_validator(mode="after")
    def validate_status(self) -> "CompanyCard":
        incomplete = any(fact.status.value in {"UNAVAILABLE", "INVALID"} for fact in self.facts)
        not_applicable = [fact for fact in self.facts if fact.status.value == "NOT_APPLICABLE"]
        for fact in not_applicable:
            if (
                self.classification is None
                or self.classification.mapping_status.value != "MAPPED"
                or self.classification.rule_profile_id != fact.applicability_profile_id
            ):
                raise ValueError("not applicable fact requires matching mapped classification")
        if self.card_status == CardStatus.OK and incomplete:
            raise ValueError("OK card cannot contain unavailable or invalid facts")
        if self.card_status == CardStatus.PARTIAL and not incomplete:
            raise ValueError("PARTIAL card requires unavailable or invalid facts")
        return self


class DailySummary(BaseModel):
    date: str
    coverage_count: int
    disclosed_count: int
    red_count: int
    yellow_count: int
    ok_count: int
    cards: list[CompanyCard]


class RuleDistributionItem(BaseModel):
    rule_id: str
    count: int


class QuarterlyReview(BaseModel):
    period_label: str
    coverage_count: int
    disclosed_count: int
    finding_count: int
    precision_pct: float | None
    top_rules: list[RuleDistributionItem]


_FACT_SPECS = [
    ("revenue", "营业收入", "亿元", "tushare.income", "revenue"),
    ("net_profit", "净利润", "亿元", "tushare.income", "net_profit"),
    ("deducted_net_profit", "扣非净利润", "亿元", "tushare.fina_indicator", "deducted_net_profit"),
    ("gross_margin_pct", "毛利率", "%", "tushare.fina_indicator", "gross_margin_pct"),
    ("operating_cash_flow", "经营活动现金流", "亿元", "tushare.cashflow", "operating_cash_flow"),
]


def build_facts(ctx: Context) -> list[Fact]:
    facts = []
    for fact_id, label, unit, source, field in _FACT_SPECS:
        value = getattr(ctx.current, field)
        if value is None:
            facts.append(
                Fact(
                    fact_id=fact_id,
                    label=label,
                    period=ctx.current.period,
                    status=FactStatus.UNAVAILABLE,
                    reason_code="EMPTY_SOURCE_RESULT",
                    reason=f"工具未返回 {ctx.current.period} 的 {label}",
                )
            )
            continue
        evidence_id = f"{ctx.ts_code}:{ctx.current.period}:{fact_id}"
        facts.append(
            Fact(
                fact_id=fact_id,
                label=label,
                value=float(value),
                unit=unit,
                period=ctx.current.period,
                status=FactStatus.VERIFIED,
                evidence=FactEvidence(
                    evidence_id=evidence_id,
                    source=source,
                    field=field,
                    period=ctx.current.period,
                    value=float(value),
                ),
            )
        )
    return facts


def _num(value: float | None) -> str:
    return "NA" if value is None else f"{value:.1f}"


def _max_severity(findings: list[Finding]) -> Severity | None:
    severities = {finding.severity for finding in findings}
    if Severity.RED in severities:
        return Severity.RED
    if Severity.YELLOW in severities:
        return Severity.YELLOW
    if Severity.INFO in severities:
        return Severity.INFO
    return None


def _finding_sort_key(finding: Finding) -> tuple[int, float, str]:
    severity_rank = {Severity.RED: 0, Severity.YELLOW: 1, Severity.INFO: 2}
    return (severity_rank[finding.severity], -finding.score, finding.rule_id)


def build_company_card(
    ctx: Context,
    findings: list[Finding],
    attribution: str | None = None,
    classification: ClassificationResult | None = None,
    rule_results: list[RuleResult] | None = None,
    company: CompanyIdentity | None = None,
) -> CompanyCard:
    current = ctx.current
    ordered = sorted(findings, key=_finding_sort_key)
    fact_line = (
        f"营收 {_num(current.revenue)} | 净利 {_num(current.net_profit)} | "
        f"扣非净利 {_num(current.deducted_net_profit)} | 毛利率 {_num(current.gross_margin_pct)}% | "
        f"经营现金流 {_num(current.operating_cash_flow)}"
    )
    facts = build_facts(ctx)
    incomplete = any(fact.status in (FactStatus.UNAVAILABLE, FactStatus.INVALID) for fact in facts)
    return CompanyCard(
        ts_code=ctx.ts_code,
        period=current.period,
        fact_line=fact_line,
        findings=ordered,
        attribution=attribution,
        max_severity=_max_severity(ordered),
        max_score=max((finding.score for finding in ordered), default=0.0),
        company=company,
        classification=classification,
        card_status=CardStatus.PARTIAL if incomplete else CardStatus.OK,
        facts=facts,
        rule_results=rule_results or [],
    )


def build_daily_summary(date: str, coverage_count: int, cards: list[CompanyCard], disclosed_count: int | None = None) -> DailySummary:
    severity_rank = {Severity.RED: 0, Severity.YELLOW: 1, Severity.INFO: 2, None: 3}
    ordered_cards = sorted(cards, key=lambda card: (severity_rank[card.max_severity], -card.max_score, card.ts_code))
    red_count = sum(1 for card in cards if card.max_severity == Severity.RED)
    yellow_count = sum(1 for card in cards if card.max_severity == Severity.YELLOW)
    ok_count = sum(1 for card in cards if card.max_severity is None)
    return DailySummary(
        date=date,
        coverage_count=coverage_count,
        disclosed_count=len(cards) if disclosed_count is None else disclosed_count,
        red_count=red_count,
        yellow_count=yellow_count,
        ok_count=ok_count,
        cards=ordered_cards,
    )


def build_quarterly_review(summary: BacktestSummary, precision_pct: float | None) -> QuarterlyReview:
    top_rules = [
        RuleDistributionItem(rule_id=rule_id, count=count)
        for rule_id, count in sorted(summary.finding_distribution.items(), key=lambda item: (-item[1], item[0]))
    ]
    return QuarterlyReview(
        period_label=f"{summary.start_date}-{summary.end_date}",
        coverage_count=summary.coverage_count,
        disclosed_count=summary.disclosed_count,
        finding_count=summary.finding_count,
        precision_pct=precision_pct,
        top_rules=top_rules,
    )
