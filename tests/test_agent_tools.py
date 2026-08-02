import pytest

from copilot.agent.exceptions import AgentToolError
from copilot.agent.tools import ToolRegistry, collect_references


class FakeProvider:
    def __init__(self):
        self.cards = {}
        self.daily = {}
        self.scan = {}

    def get_company_card(self, ts_code, period):
        return self.cards.get((ts_code, period))

    def get_daily_summary(self, date):
        return self.daily.get(date)

    def get_disclosure_scan(self, date):
        return self.scan.get(date)


def test_unknown_tool_is_rejected():
    registry = ToolRegistry(FakeProvider())

    with pytest.raises(AgentToolError):
        registry.execute("delete_all", {})


def test_invalid_args_are_rejected():
    registry = ToolRegistry(FakeProvider())

    with pytest.raises(AgentToolError):
        registry.execute("get_company_card", {"ts_code": "000001.SZ"})


def test_get_company_card_returns_serializable_payload(make_snapshot):
    provider = FakeProvider()
    from copilot.models import Context
    from copilot.report.builder import build_company_card

    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    provider.cards[("000001.SZ", "20250630")] = card
    registry = ToolRegistry(provider)

    payload = registry.execute("get_company_card", {"ts_code": "000001.SZ", "period": "20250630"})

    assert payload["ts_code"] == "000001.SZ"
    assert any(fact["fact_id"] == "revenue" for fact in payload["facts"])


def test_collect_references_walks_nested_payload():
    fact_ids, evidence_ids = collect_references(
        {"facts": [{"fact_id": "revenue", "evidence": {"evidence_id": "e1"}}]}
    )

    assert fact_ids == ["revenue"]
    assert evidence_ids == ["e1"]


def test_registry_names_are_whitelisted():
    registry = ToolRegistry(FakeProvider())
    assert set(registry.names()) == {
        "get_company_card",
        "get_daily_summary",
        "get_disclosure_scan",
    }
