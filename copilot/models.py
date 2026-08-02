from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


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


class CompanyIdentity(BaseModel):
    ts_code: str
    name: str | None = None
    provider: str
    name_field: str | None = None
    retrieved_at: str | None = None


class MappingStatus(StrEnum):
    MAPPED = "MAPPED"
    UNMAPPED = "UNMAPPED"
    UNAVAILABLE = "UNAVAILABLE"
    CONFLICT = "CONFLICT"


class ClassificationResult(BaseModel):
    provider: str
    provider_industry: str | None = None
    mapping_status: MappingStatus
    rule_profile_id: str = "generic"
    industry_field: str | None = None
    source_value: str | None = None
    retrieved_at: str | None = None


class FactStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FactEvidence(BaseModel):
    evidence_id: str
    source: str
    field: str
    period: str
    value: float | str


class Fact(BaseModel):
    fact_id: str
    label: str
    value: float | str | None = None
    unit: str | None = None
    period: str
    status: FactStatus
    evidence: FactEvidence | None = None
    reason_code: str | None = None
    reason: str | None = None
    applicability_profile_id: str | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "Fact":
        if self.status == FactStatus.VERIFIED:
            if self.value is None or self.evidence is None:
                raise ValueError("verified fact requires value and evidence")
            if self.evidence.period != self.period:
                raise ValueError("fact and evidence periods must match")
            if self.evidence.value != self.value:
                raise ValueError("fact and evidence values must match")
        elif self.status in {FactStatus.UNAVAILABLE, FactStatus.INVALID}:
            if not self.reason_code or not self.reason:
                raise ValueError("unavailable or invalid fact requires reason")
        elif self.status == FactStatus.NOT_APPLICABLE:
            if not self.applicability_profile_id or self.applicability_profile_id == "generic":
                raise ValueError("not applicable fact requires special profile")
            if not self.reason_code or not self.reason:
                raise ValueError("not applicable fact requires reason")
        return self


class RuleResultStatus(StrEnum):
    HIT = "HIT"
    MISS = "MISS"
    NOT_EVALUATED = "NOT_EVALUATED"
    BLOCKED = "BLOCKED"


class RuleResult(BaseModel):
    rule_id: str
    status: RuleResultStatus
    required_fact_ids: list[str] = Field(default_factory=list)
    related_fact_ids: list[str] = Field(default_factory=list)
    reason_code: str | None = None
    reason: str | None = None


class CardStatus(StrEnum):
    OK = "OK"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


class AgentFactContext(BaseModel):
    ts_code: str
    period: str
    fact_id: str | None = None
    rule_id: str | None = None
    evidence_id: str | None = None
