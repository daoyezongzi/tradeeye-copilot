import re
from typing import Literal

from pydantic import BaseModel, Field, model_serializer, model_validator


_TS_CODE_RE = re.compile(r"^\d{6}\.(SZ|SH|BJ)$")
_PERIOD_RE = re.compile(r"^\d{8}$")
_DATE_RE = re.compile(r"^\d{8}$")


class AgentReference(BaseModel):
    fact_id: str | None = None
    evidence_id: str | None = None

    @model_serializer
    def serialize(self) -> dict:
        return {key: value for key, value in self.__dict__.items() if value is not None}

    @model_validator(mode="after")
    def validate_reference(self) -> "AgentReference":
        if self.fact_id is None and self.evidence_id is None:
            raise ValueError("reference requires fact_id or evidence_id")
        return self


class RefetchCompanyParams(BaseModel):
    ts_code: str
    period: str

    @model_validator(mode="after")
    def validate_params(self) -> "RefetchCompanyParams":
        if not _TS_CODE_RE.match(self.ts_code):
            raise ValueError("ts_code must look like 000001.SZ")
        if not _PERIOD_RE.match(self.period):
            raise ValueError("period must be YYYYMMDD")
        return self


class RescanDisclosureDayParams(BaseModel):
    date: str

    @model_validator(mode="after")
    def validate_params(self) -> "RescanDisclosureDayParams":
        if not _DATE_RE.match(self.date):
            raise ValueError("date must be YYYYMMDD")
        return self


class AgentAction(BaseModel):
    action: Literal["refetch_company", "rescan_disclosure_day"]
    params: dict
    reason: str

    @model_validator(mode="after")
    def validate_action(self) -> "AgentAction":
        if not self.reason.strip():
            raise ValueError("action reason required")
        if self.action == "refetch_company":
            self.params = RefetchCompanyParams(**self.params).model_dump()
        elif self.action == "rescan_disclosure_day":
            self.params = RescanDisclosureDayParams(**self.params).model_dump()
        return self


class AgentChatRequest(BaseModel):
    ts_code: str
    period: str
    question: str
    session_id: str | None = None


class AgentChatResult(BaseModel):
    session_id: str
    answer: str
    references: list[AgentReference] = []
    message_id: str
    actions: list[AgentAction] = Field(default_factory=list)
