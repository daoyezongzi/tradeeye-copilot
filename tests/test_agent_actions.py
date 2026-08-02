from copilot.agent.pipeline import AgentService
from copilot.llm.client import ChatMessage
from copilot.models import Context
from copilot.report.builder import build_company_card


class FakeLLM:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[list[ChatMessage]] = []

    def chat(self, messages, temperature=0.2):
        self.calls.append(list(messages))
        return self.response


class FakeCardProvider:
    def __init__(self, card):
        self.card = card

    def get_company_card(self, ts_code, period):
        return self.card


class FakeStore:
    def __init__(self):
        self.messages = []
        self.session = type(
            "Session",
            (),
            {"session_id": "session-1", "ts_code": "000001.SZ", "period": "20250630"},
        )()

    def create_or_get_session(self, ts_code, period):
        self.session.ts_code = ts_code
        self.session.period = period
        return self.session

    def get_session(self, session_id):
        return self.session if session_id == self.session.session_id else None

    def list_recent_messages(self, session_id, rounds=20):
        return []

    def append_message(self, session_id, role, content, references=None):
        self.messages.append((session_id, role, content, references or []))
        return type("Message", (), {"message_id": f"message-{len(self.messages)}"})()


def make_card(make_snapshot):
    return build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])


def make_service(make_snapshot, response):
    return AgentService(
        store=FakeStore(),
        llm=FakeLLM(response),
        provider=FakeCardProvider(make_card(make_snapshot)),
    )


def test_agent_chat_returns_valid_actions(make_snapshot):
    service = make_service(
        make_snapshot,
        '{"answer":"建议重抽。","references":[],"actions":[{"action":"refetch_company","params":{"ts_code":"000001.SZ","period":"20250630"},"reason":"研究员要求重新抓取"},{"action":"rescan_disclosure_day","params":{"date":"20250821"},"reason":"研究员要求重扫披露日"}]}',
    )

    result = service.answer_question("000001.SZ", "20250630", "再抓一遍数据")

    assert [action.action for action in result.actions] == ["refetch_company", "rescan_disclosure_day"]
    assert result.actions[0].params == {"ts_code": "000001.SZ", "period": "20250630"}
    assert result.actions[0].reason == "研究员要求重新抓取"
    assert result.actions[1].params == {"date": "20250821"}


def test_agent_chat_drops_unknown_or_invalid_actions(make_snapshot):
    service = make_service(
        make_snapshot,
        '{"answer":"已回答。","references":[],"actions":[{"action":"write_review_label","params":{"label":"TP"},"reason":"不允许"},{"action":"refetch_company","params":{"ts_code":"000001.SZ"},"reason":"缺 period"},{"action":"rescan_disclosure_day","params":{"date":"2025-08-21"},"reason":"日期格式错误"}]}',
    )

    result = service.answer_question("000001.SZ", "20250630", "帮我处理")

    assert result.actions == []
    assert result.answer == "已回答。"


def test_agent_chat_caps_actions_at_two(make_snapshot):
    service = make_service(
        make_snapshot,
        '{"answer":"三个动作只保留两个。","references":[],"actions":[{"action":"refetch_company","params":{"ts_code":"000001.SZ","period":"20250630"},"reason":"第一"},{"action":"rescan_disclosure_day","params":{"date":"20250821"},"reason":"第二"},{"action":"refetch_company","params":{"ts_code":"000002.SZ","period":"20250630"},"reason":"第三"}]}',
    )

    result = service.answer_question("000001.SZ", "20250630", "多给几个动作")

    assert len(result.actions) == 2
    assert [action.reason for action in result.actions] == ["第一", "第二"]


def test_agent_prompt_mentions_actions(make_snapshot):
    service = make_service(
        make_snapshot,
        '{"answer":"不需要重抓。","references":[],"actions":[]}',
    )

    service.answer_question("000001.SZ", "20250630", "有什么异常？")

    system_prompt = service.llm.calls[0][0].content
    assert "actions" in system_prompt
    assert "refetch_company" in system_prompt
    assert "rescan_disclosure_day" in system_prompt
