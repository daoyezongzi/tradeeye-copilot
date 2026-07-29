from enum import StrEnum
from pydantic import BaseModel

from copilot.models import Context


class CheckStatus(StrEnum):
    OK = "OK"
    DATA_INCOMPLETE = "DATA_INCOMPLETE"
    RECONCILE_FAILED = "RECONCILE_FAILED"


class CheckResult(BaseModel):
    status: CheckStatus
    messages: list[str]


_REQUIRED_CURRENT_FIELDS = [
    "revenue",
    "net_profit",
    "gross_margin_pct",
    "operating_cash_flow",
]


_NON_NEGATIVE_FIELDS = [
    "revenue",
    "accounts_receivable",
    "inventory",
]


def run_hard_checks(ctx: Context) -> CheckResult:
    messages: list[str] = []

    for field in _REQUIRED_CURRENT_FIELDS:
        if ctx.current.value(field) is None:
            messages.append(f"current.{field} missing")

    if messages:
        return CheckResult(status=CheckStatus.DATA_INCOMPLETE, messages=messages)

    for field in _NON_NEGATIVE_FIELDS:
        value = ctx.current.value(field)
        if value is not None and value < 0:
            messages.append(f"current.{field} is negative")

    if messages:
        return CheckResult(status=CheckStatus.RECONCILE_FAILED, messages=messages)

    return CheckResult(status=CheckStatus.OK, messages=[])
