from dataclasses import dataclass

from copilot.models import Context, Finding, Severity
from copilot.rules.base import source_evidence


@dataclass(frozen=True)
class NonRecurringProfitShareRule:
    threshold_pct: float
    id: str = "non_recurring_profit_share"
    required_fact_ids: tuple[str, ...] = ("net_profit", "deducted_net_profit")

    def applies(self, ctx: Context) -> bool:
        return ctx.current.net_profit not in (None, 0) and ctx.current.deducted_net_profit is not None

    def evaluate(self, ctx: Context) -> Finding | None:
        if not self.applies(ctx):
            return None
        share = (ctx.current.net_profit - ctx.current.deducted_net_profit) / ctx.current.net_profit * 100.0
        if share <= self.threshold_pct:
            return None
        return Finding(
            rule_id=self.id,
            severity=Severity.YELLOW,
            title="非经常性损益占比偏高",
            detail=f"非经常性损益贡献 {share:.1f}%，超过阈值 {self.threshold_pct:.1f}%",
            evidence=[
                source_evidence("tushare.income", "net_profit", ctx.current.period, ctx.current.net_profit),
                source_evidence("tushare.fina_indicator", "deducted_net_profit", ctx.current.period, ctx.current.deducted_net_profit),
            ],
            score=round(share, 1),
        )
