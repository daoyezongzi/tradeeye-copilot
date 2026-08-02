from dataclasses import dataclass

from copilot.models import Context, Finding, Severity
from copilot.rules.base import pct_gap, source_evidence


def _fmt_pct(value: float) -> str:
    return f"{value:+.1f}%"


def _fmt_pct_plain(value: float) -> str:
    return f"{value:.1f}%"


@dataclass(frozen=True)
class ReceivableRevenueDivergenceRule:
    threshold_pct: float
    id: str = "receivable_revenue_divergence"
    required_fact_ids: tuple[str, ...] = ("revenue",)

    def applies(self, ctx: Context) -> bool:
        return ctx.prior_year is not None

    def evaluate(self, ctx: Context) -> Finding | None:
        if not self.applies(ctx):
            return None
        receivable_yoy = ctx.current.growth_pct("accounts_receivable", ctx.prior_year)
        revenue_yoy = ctx.current.growth_pct("revenue", ctx.prior_year)
        gap = pct_gap(receivable_yoy, revenue_yoy)
        if gap is None or gap <= self.threshold_pct:
            return None
        return Finding(
            rule_id=self.id,
            severity=Severity.RED,
            title="应收账款增速背离",
            detail=f"应收账款 {_fmt_pct(receivable_yoy)} vs 营收 {_fmt_pct(revenue_yoy)}，背离 {gap:.1f}pct",
            evidence=[
                source_evidence("tushare.balancesheet", "accounts_receivable", ctx.current.period, ctx.current.accounts_receivable),
                source_evidence("tushare.balancesheet", "accounts_receivable", ctx.prior_year.period, ctx.prior_year.accounts_receivable),
                source_evidence("tushare.income", "revenue", ctx.current.period, ctx.current.revenue),
                source_evidence("tushare.income", "revenue", ctx.prior_year.period, ctx.prior_year.revenue),
            ],
            score=round(gap, 1),
        )


@dataclass(frozen=True)
class InventoryRevenueDivergenceRule:
    threshold_pct: float
    id: str = "inventory_revenue_divergence"
    required_fact_ids: tuple[str, ...] = ("revenue",)

    def applies(self, ctx: Context) -> bool:
        return ctx.prior_year is not None

    def evaluate(self, ctx: Context) -> Finding | None:
        if not self.applies(ctx):
            return None
        inventory_yoy = ctx.current.growth_pct("inventory", ctx.prior_year)
        revenue_yoy = ctx.current.growth_pct("revenue", ctx.prior_year)
        gap = pct_gap(inventory_yoy, revenue_yoy)
        if gap is None or gap <= self.threshold_pct:
            return None
        return Finding(
            rule_id=self.id,
            severity=Severity.RED,
            title="存货增速背离",
            detail=f"存货 {_fmt_pct(inventory_yoy)} vs 营收 {_fmt_pct(revenue_yoy)}，背离 {gap:.1f}pct",
            evidence=[
                source_evidence("tushare.balancesheet", "inventory", ctx.current.period, ctx.current.inventory),
                source_evidence("tushare.balancesheet", "inventory", ctx.prior_year.period, ctx.prior_year.inventory),
                source_evidence("tushare.income", "revenue", ctx.current.period, ctx.current.revenue),
                source_evidence("tushare.income", "revenue", ctx.prior_year.period, ctx.prior_year.revenue),
            ],
            score=round(gap, 1),
        )


@dataclass(frozen=True)
class CashflowQualityRule:
    threshold_pct: float
    id: str = "cashflow_quality"
    required_fact_ids: tuple[str, ...] = ("operating_cash_flow", "net_profit")

    def applies(self, ctx: Context) -> bool:
        return ctx.current.net_profit not in (None, 0) and ctx.current.operating_cash_flow is not None

    def evaluate(self, ctx: Context) -> Finding | None:
        if not self.applies(ctx):
            return None
        ratio = ctx.current.operating_cash_flow / ctx.current.net_profit * 100.0
        if ratio >= self.threshold_pct:
            return None
        score = self.threshold_pct - ratio
        return Finding(
            rule_id=self.id,
            severity=Severity.YELLOW,
            title="现金流质量偏弱",
            detail=f"经营活动现金流净额/净利润 = {_fmt_pct_plain(ratio)}，低于 {_fmt_pct_plain(self.threshold_pct)}",
            evidence=[
                source_evidence("tushare.cashflow", "operating_cash_flow", ctx.current.period, ctx.current.operating_cash_flow),
                source_evidence("tushare.income", "net_profit", ctx.current.period, ctx.current.net_profit),
            ],
            score=round(score, 1),
        )


@dataclass(frozen=True)
class GrossMarginChangeRule:
    threshold_pct: float
    id: str = "gross_margin_change"
    required_fact_ids: tuple[str, ...] = ("gross_margin_pct",)

    def applies(self, ctx: Context) -> bool:
        return ctx.prior_year is not None

    def evaluate(self, ctx: Context) -> Finding | None:
        if not self.applies(ctx):
            return None
        change = ctx.current.change_pct_points("gross_margin_pct", ctx.prior_year)
        if change is None or abs(change) <= self.threshold_pct:
            return None
        return Finding(
            rule_id=self.id,
            severity=Severity.YELLOW,
            title="毛利率异动",
            detail=f"毛利率同比变动 {change:+.1f}pct，超过阈值 {self.threshold_pct:.1f}pct",
            evidence=[
                source_evidence("tushare.fina_indicator", "gross_margin_pct", ctx.current.period, ctx.current.gross_margin_pct),
                source_evidence("tushare.fina_indicator", "gross_margin_pct", ctx.prior_year.period, ctx.prior_year.gross_margin_pct),
            ],
            score=round(abs(change), 1),
        )


@dataclass(frozen=True)
class NetProfitRevenueDirectionRule:
    id: str = "net_profit_revenue_direction"
    required_fact_ids: tuple[str, ...] = ("revenue", "net_profit")

    def applies(self, ctx: Context) -> bool:
        return ctx.prior_year is not None

    def evaluate(self, ctx: Context) -> Finding | None:
        if not self.applies(ctx):
            return None
        revenue_yoy = ctx.current.growth_pct("revenue", ctx.prior_year)
        net_profit_yoy = ctx.current.growth_pct("net_profit", ctx.prior_year)
        if revenue_yoy is None or net_profit_yoy is None:
            return None
        if revenue_yoy == 0 or net_profit_yoy == 0 or revenue_yoy * net_profit_yoy > 0:
            return None
        score = abs(revenue_yoy - net_profit_yoy)
        return Finding(
            rule_id=self.id,
            severity=Severity.RED,
            title="利润与营收方向背离",
            detail=f"营收 {_fmt_pct(revenue_yoy)}，净利润 {_fmt_pct(net_profit_yoy)}，方向背离",
            evidence=[
                source_evidence("tushare.income", "revenue", ctx.current.period, ctx.current.revenue),
                source_evidence("tushare.income", "revenue", ctx.prior_year.period, ctx.prior_year.revenue),
                source_evidence("tushare.income", "net_profit", ctx.current.period, ctx.current.net_profit),
                source_evidence("tushare.income", "net_profit", ctx.prior_year.period, ctx.prior_year.net_profit),
            ],
            score=round(score, 1),
        )
