from typing import Protocol

from copilot.models import Context, Evidence, Finding


class Rule(Protocol):
    id: str
    required_fact_ids: tuple[str, ...]

    def applies(self, ctx: Context) -> bool: ...

    def evaluate(self, ctx: Context) -> Finding | None: ...


def pct_gap(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def source_evidence(source: str, field: str, period: str, value: float | str | None) -> Evidence:
    return Evidence(source=source, field=field, period=period, value="missing" if value is None else value)
