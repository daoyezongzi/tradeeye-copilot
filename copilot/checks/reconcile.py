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


_GENERIC_REQUIRED_CURRENT_FIELDS = [
    "revenue",
    "net_profit",
    "gross_margin_pct",
    "operating_cash_flow",
]

_BANK_REQUIRED_CURRENT_FIELDS = [
    "revenue",
    "net_profit",
    "operating_cash_flow",
]

_GENERIC_NON_NEGATIVE_FIELDS = [
    "revenue",
    "accounts_receivable",
    "inventory",
]

_BANK_NON_NEGATIVE_FIELDS = ["revenue"]


def _industry(ctx: Context) -> str:
    return str(ctx.metadata.get("industry") or "generic")


def _required_current_fields(ctx: Context) -> list[str]:
    if _industry(ctx) == "bank":
        return _BANK_REQUIRED_CURRENT_FIELDS
    return _GENERIC_REQUIRED_CURRENT_FIELDS


def _non_negative_fields(ctx: Context) -> list[str]:
    if _industry(ctx) == "bank":
        return _BANK_NON_NEGATIVE_FIELDS
    return _GENERIC_NON_NEGATIVE_FIELDS


def run_hard_checks(ctx: Context) -> CheckResult:
    messages: list[str] = []

    for field in _required_current_fields(ctx):
        if ctx.current.value(field) is None:
            messages.append(f"current.{field} missing")

    if messages:
        return CheckResult(status=CheckStatus.DATA_INCOMPLETE, messages=messages)

    for field in _non_negative_fields(ctx):
        value = ctx.current.value(field)
        if value is not None and value < 0:
            messages.append(f"current.{field} is negative")

    if messages:
        return CheckResult(status=CheckStatus.RECONCILE_FAILED, messages=messages)

    return CheckResult(status=CheckStatus.OK, messages=[])
