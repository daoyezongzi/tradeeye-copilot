import json
from typing import Protocol

from copilot.agent.context import SYSTEM_PROMPT, build_preset_context
from copilot.agent.contracts import AgentChatResult, AgentReference
from copilot.agent.exceptions import AgentCardNotFound, AgentLLMError, AgentSessionMismatch
from copilot.agent.references import ReferenceValidator
from copilot.agent.store import AgentSession
from copilot.llm.client import ChatMessage
from copilot.report.builder import CompanyCard


class AgentLLM(Protocol):
    def chat(self, messages: list[ChatMessage], temperature: float = 0.2) -> str | None: ...


class CardProvider(Protocol):
    def get_company_card(self, ts_code: str, period: str) -> CompanyCard | None: ...


def parse_agent_payload(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _parse_references(payload: dict) -> list[dict]:
    raw = payload.get("references")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


class AgentService:
    def __init__(self, store, llm: AgentLLM, provider: CardProvider, max_history_rounds: int = 20):
        self.store = store
        self.llm = llm
        self.provider = provider
        self.max_history_rounds = max_history_rounds

    def answer_question(self, ts_code: str, period: str, question: str, session_id: str | None = None) -> AgentChatResult:
        session = self._resolve_session(ts_code, period, session_id)
        card = self.provider.get_company_card(ts_code, period)
        if card is None:
            raise AgentCardNotFound(f"该报告期尚未生成研判卡: {ts_code} {period}")

        preset = build_preset_context(card)
        history = self.store.list_recent_messages(session.session_id, rounds=self.max_history_rounds)
        messages = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="system", content=f"当前研判卡数据(只读):\n{preset}"),
        ]
        messages.extend(ChatMessage(role=message.role, content=message.content) for message in history)
        messages.append(ChatMessage(role="user", content=question))

        text = self.llm.chat(messages)
        if text is None:
            raise AgentLLMError("LLM 调用失败")

        payload = parse_agent_payload(text) or {}
        answer = payload.get("answer")
        if not isinstance(answer, str) or not answer:
            answer = "抱歉,我无法理解你的问题,请换个问法。"

        validator = ReferenceValidator()
        validator.register(
            fact_ids=[fact.fact_id for fact in card.facts],
            evidence_ids=[evidence.evidence_id for fact in card.facts if fact.evidence is not None for evidence in [fact.evidence]],
        )
        references = validator.filter(_parse_references(payload))

        self.store.append_message(session.session_id, "user", question)
        assistant_message = self.store.append_message(
            session.session_id,
            "assistant",
            answer,
            references=references,
        )
        return AgentChatResult(
            session_id=session.session_id,
            answer=answer,
            references=references,
            message_id=assistant_message.message_id,
        )

    def _resolve_session(self, ts_code: str, period: str, session_id: str | None) -> AgentSession:
        if session_id is None:
            return self.store.create_or_get_session(ts_code, period)
        session = self.store.get_session(session_id)
        if session is None or session.ts_code != ts_code or session.period != period:
            raise AgentSessionMismatch("session 与公司/报告期不匹配")
        return session
