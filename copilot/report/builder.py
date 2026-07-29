from pydantic import BaseModel

from copilot.models import Context, Finding, Severity


class CompanyCard(BaseModel):
    ts_code: str
    period: str
    fact_line: str
    findings: list[Finding]
    attribution: str | None = None
    market_line: str = "市场数据待接入"
    max_severity: Severity | None = None
    max_score: float = 0.0


class DailySummary(BaseModel):
    date: str
    coverage_count: int
    disclosed_count: int
    red_count: int
    yellow_count: int
    ok_count: int
    cards: list[CompanyCard]


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


def build_company_card(ctx: Context, findings: list[Finding], attribution: str | None = None) -> CompanyCard:
    current = ctx.current
    ordered = sorted(findings, key=_finding_sort_key)
    fact_line = (
        f"营收 {_num(current.revenue)} | 净利 {_num(current.net_profit)} | "
        f"扣非净利 {_num(current.deducted_net_profit)} | 毛利率 {_num(current.gross_margin_pct)}% | "
        f"经营现金流 {_num(current.operating_cash_flow)}"
    )
    return CompanyCard(
        ts_code=ctx.ts_code,
        period=current.period,
        fact_line=fact_line,
        findings=ordered,
        attribution=attribution,
        max_severity=_max_severity(ordered),
        max_score=max((finding.score for finding in ordered), default=0.0),
    )


def build_daily_summary(date: str, coverage_count: int, cards: list[CompanyCard]) -> DailySummary:
    severity_rank = {Severity.RED: 0, Severity.YELLOW: 1, Severity.INFO: 2, None: 3}
    ordered_cards = sorted(cards, key=lambda card: (severity_rank[card.max_severity], -card.max_score, card.ts_code))
    red_count = sum(1 for card in cards if card.max_severity == Severity.RED)
    yellow_count = sum(1 for card in cards if card.max_severity == Severity.YELLOW)
    ok_count = sum(1 for card in cards if card.max_severity is None)
    return DailySummary(
        date=date,
        coverage_count=coverage_count,
        disclosed_count=len(cards),
        red_count=red_count,
        yellow_count=yellow_count,
        ok_count=ok_count,
        cards=ordered_cards,
    )
