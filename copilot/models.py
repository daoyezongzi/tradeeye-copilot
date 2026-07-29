from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Severity(StrEnum):
    RED = "RED"
    YELLOW = "YELLOW"
    INFO = "INFO"


class Evidence(BaseModel):
    source: str
    field: str
    period: str
    value: float | str


class Finding(BaseModel):
    rule_id: str
    severity: Severity
    title: str
    detail: str
    evidence: list[Evidence]
    score: float


class PeriodSnapshot(BaseModel):
    ts_code: str
    period: str
    ann_date: str | None = None
    revenue: float | None = None
    net_profit: float | None = None
    deducted_net_profit: float | None = None
    gross_margin_pct: float | None = None
    operating_cash_flow: float | None = None
    accounts_receivable: float | None = None
    inventory: float | None = None

    def value(self, field: str) -> float | None:
        raw = getattr(self, field)
        if raw is None:
            return None
        return float(raw)

    def growth_pct(self, field: str, base: "PeriodSnapshot") -> float | None:
        current_value = self.value(field)
        base_value = base.value(field)
        if current_value is None or base_value in (None, 0):
            return None
        return round((current_value / base_value - 1.0) * 100.0, 10)

    def change_pct_points(self, field: str, base: "PeriodSnapshot") -> float | None:
        current_value = self.value(field)
        base_value = base.value(field)
        if current_value is None or base_value is None:
            return None
        return current_value - base_value


class Context(BaseModel):
    ts_code: str
    current: PeriodSnapshot
    prior_quarter: PeriodSnapshot | None = None
    prior_year: PeriodSnapshot | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def periods(self) -> list[str]:
        values = [self.current.period]
        if self.prior_quarter is not None:
            values.append(self.prior_quarter.period)
        if self.prior_year is not None:
            values.append(self.prior_year.period)
        return values
