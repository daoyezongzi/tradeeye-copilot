from pydantic import BaseModel, model_serializer, model_validator


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
