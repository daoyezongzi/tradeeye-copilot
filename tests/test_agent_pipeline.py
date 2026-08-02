import pytest

from copilot.agent.contracts import AgentReference
from copilot.agent.exceptions import AgentCardNotFound, AgentLLMError
from copilot.agent.pipeline import AgentService, parse_agent_payload
from copilot.llm.client import ChatMessage
from copilot.models import Context
from copilot.report.builder import build_company_card


class FakeLLM:
    def __init__(self, response: str):
        self.response = response
        self.responses: list[str] = []
        self.calls: list[list[ChatMessage]] = []

    def chat(self, messages, temperature=0.2):
        self.calls.append(list(messages))
        if self.responses:
            return self.responses.pop(0)
        return self.response


class FakeCardProvider:
    def __init__(self, cards=None):
        self.cards = cards or {}

    def get_company_card(self, ts_code, period):
        return self.cards.get((ts_code, period))


class FakeStore:
    def __init__(self):
        self.sessions = {}
        self.messages = []

    def create_or_get_session(self, ts_code, period):
        return self.sessions.setdefault(
            (ts_code, period),
            AgentSessionStub(ts_code=ts_code, period=period),
        )

    def get_session(self, session_id):
        for session in self.sessions.values():
            if session.session_id == session_id:
                return session
        return None

    def append_message(self, session_id, role, content, references=None):
        self.messages.append((session_id, role, content, references))
        return MessageStub(f"message-{len(self.messages)}")

    def list_recent_messages(self, session_id, rounds=20):
        return [m for m in self.messages if m[0] == session_id][-rounds * 2 :]


class MessageStub:
    def __init__(self, message_id):
        self.message_id = message_id


class AgentSessionStub:
    def __init__(self, ts_code, period):
        self.session_id = f"session-{ts_code}-{period}"
        self.ts_code = ts_code
        self.period = period


def make_service(make_snapshot, llm=None, store=None):
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    return (
        AgentService(
            store=store or FakeStore(),
            llm=llm or FakeLLM('{"answer": "ok", "references": [{"fact_id": "revenue"}]}'),
            provider=FakeCardProvider({("000001.SZ", "20250630"): card}),
        ),
        card,
    )


def test_parse_agent_payload_extracts_json_with_surrounding_text():
    payload = parse_agent_payload('prefix\n{"answer": "ok", "references": []}\nsuffix')
    assert payload == {"answer": "ok", "references": []}
    assert parse_agent_payload("not json") is None


def test_single_card_question_returns_answer_with_validated_references(make_snapshot):
    service, card = make_service(make_snapshot)
    result = service.answer_question("000001.SZ", "20250630", "营收多少?")

    assert result.answer == "ok"
    assert result.references == [AgentReference(fact_id="revenue")]
    assert result.session_id == "session-000001.SZ-20250630"
    assert len(service.store.messages) == 2


def test_question_for_missing_card_raises(make_snapshot):
    service, _ = make_service(make_snapshot)
    with pytest.raises(AgentCardNotFound):
        service.answer_question("000002.SZ", "20250630", "营收多少?")


def test_fake_reference_is_dropped(make_snapshot):
    llm = FakeLLM('{"answer": "ok", "references": [{"fact_id": "fake"}, {"fact_id": "revenue"}]}')
    service, _ = make_service(make_snapshot, llm=llm)

    result = service.answer_question("000001.SZ", "20250630", "营收多少?")

    assert result.references == [AgentReference(fact_id="revenue")]


def test_llm_failure_raises_agent_llm_error(make_snapshot):
    llm = FakeLLM(None)
    service, _ = make_service(make_snapshot, llm=llm)

    with pytest.raises(AgentLLMError):
        service.answer_question("000001.SZ", "20250630", "营收多少?")


def test_tool_call_retries_then_answers(make_snapshot):
    from copilot.agent.tools import ToolRegistry

    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    other = build_company_card(Context(ts_code="000002.SZ", current=make_snapshot(ts_code="000002.SZ")), [])
    provider = FakeCardProvider(
        {
            ("000001.SZ", "20250630"): card,
            ("000002.SZ", "20250630"): other,
        }
    )
    store = FakeStore()
    llm = FakeLLM('{"answer": "ok"}')
    llm.responses = [
        '{"tool": "get_company_card", "args": {"ts_code": "000002.SZ", "period": "20250630"}}',
        '{"answer": "另一家营收是 100", "references": [{"fact_id": "revenue"}]}',
    ]

    service = AgentService(
        store=store,
        llm=llm,
        provider=provider,
        tool_registry=ToolRegistry(provider),
    )

    result = service.answer_question("000001.SZ", "20250630", "000002.SZ 营收多少?")

    assert result.answer == "另一家营收是 100"
    assert result.references == [AgentReference(fact_id="revenue")]
    assert len(llm.responses) == 0
