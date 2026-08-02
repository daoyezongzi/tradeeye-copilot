from fastapi.testclient import TestClient

from copilot.agent.contracts import AgentChatResult, AgentReference
from copilot.agent.exceptions import AgentCardNotFound
from copilot.api.app import create_app
from copilot.models import Context
from copilot.report.builder import build_company_card


class FakeFullService:
    def get_company_card(self, ts_code, period):
        return None

    def get_daily_summary(self, date):
        return None

    def get_evidence(self, ts_code, period, rule_id):
        return []

    def get_quarterly_review(self):
        return None

    def get_meta(self):
        return None

    def analyze_company(self, ts_code, period):
        return None

    def analyze_disclosure_day(self, date):
        return None

    def scan_disclosure_day(self, date):
        return None

    def analyze_disclosure_day_bundle(self, date):
        return None

    def start_disclosure_day_job(self, date, resume_from_job_id=None, owner_id=None):
        return None

    def run_disclosure_day_job(self, job_id):
        return None

    def list_disclosure_day_jobs(self, limit=20, owner_id=None):
        return []

    def get_disclosure_day_job(self, job_id, owner_id=None):
        return None

    def cancel_disclosure_day_job(self, job_id, owner_id=None):
        return None

    def prune_disclosure_day_jobs(self, keep_recent=20):
        return 0

    def run_disclosure_automation(self, date, notify=True):
        return None

    def poll_rss(self):
        return None

    def preview_feishu_disclosure_day(self, date):
        return None

    def notify_feishu_disclosure_day(self, date):
        return None

    def list_notify_logs(self, limit=20):
        return []

    def upsert_review_label(self, label):
        return None

    def list_review_labels(self, ts_code=None, period=None):
        return []

    def delete_review_label(self, ts_code, period, rule_id):
        return False

    def get_review_metrics(self, ts_code=None, period=None):
        return None

    def verify_feishu_callback_token(self, token):
        return True

    def verify_automation_trigger_token(self, token):
        return True


class FakeAgentService:
    def __init__(self, make_snapshot):
        self.card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])

    def answer_question(self, ts_code, period, question, session_id=None):
        if self.card is None:
            raise AgentCardNotFound("该报告期尚未生成研判卡")
        return AgentChatResult(
            session_id="s1",
            answer="营收 100 亿元。",
            references=[AgentReference(fact_id="revenue")],
            message_id="m1",
        )


def test_agent_chat_route_returns_structured_answer(make_snapshot):
    client = TestClient(create_app(FakeFullService(), agent_service=FakeAgentService(make_snapshot)))

    response = client.post(
        "/api/agent/chat",
        json={"ts_code": "000001.SZ", "period": "20250630", "question": "营收多少?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "s1"
    assert payload["answer"] == "营收 100 亿元。"
    assert payload["references"] == [{"fact_id": "revenue"}]
    assert "message_id" in payload


def test_agent_chat_route_returns_503_without_agent_service(make_snapshot):
    client = TestClient(create_app(FakeFullService()))

    response = client.post(
        "/api/agent/chat",
        json={"ts_code": "000001.SZ", "period": "20250630", "question": "营收多少?"},
    )

    assert response.status_code == 503


def test_agent_chat_route_returns_400_for_missing_card(make_snapshot):
    class MissingCardService(FakeAgentService):
        def __init__(self, make_snapshot):
            self.card = None

    client = TestClient(create_app(FakeFullService(), agent_service=MissingCardService(make_snapshot)))

    response = client.post(
        "/api/agent/chat",
        json={"ts_code": "000001.SZ", "period": "20250630", "question": "营收多少?"},
    )

    assert response.status_code == 400


def test_agent_chat_response_includes_actions(make_snapshot):
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])

    class FakeAgent:
        def answer_question(self, ts_code, period, question, session_id=None):
            return AgentChatResult(
                session_id="session-1",
                answer="建议重抽。",
                references=[],
                message_id="message-1",
                actions=[
                    {"action": "refetch_company", "params": {"ts_code": ts_code, "period": period}, "reason": "研究员要求"}
                ],
            )

    service = FakeFullService()
    service.get_company_card = lambda ts_code, period: card
    client = TestClient(create_app(service, agent_service=FakeAgent()))

    response = client.post(
        "/api/agent/chat",
        json={"ts_code": "000001.SZ", "period": "20250630", "question": "再抓一遍"},
    )

    assert response.status_code == 200
    assert response.json()["actions"] == [
        {
            "action": "refetch_company",
            "params": {"ts_code": "000001.SZ", "period": "20250630"},
            "reason": "研究员要求",
        }
    ]
