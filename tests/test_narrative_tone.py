from copilot.models import Severity
from copilot.narrative.tone import compare_management_tone


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.messages = None

    def chat(self, messages, temperature=0.2):
        self.messages = messages
        return self.response


def test_compare_management_tone_returns_finding_when_weakened():
    llm = FakeLLM('{"weakened": true, "reason": "从订单充足变为需求承压", "evidence": "需求承压"}')

    finding = compare_management_tone(
        llm,
        ts_code="000001.SZ",
        current_period="20250630",
        prior_period="20240630",
        current_text="需求承压，回款放缓。",
        prior_text="订单充足，增长稳健。",
    )

    assert finding is not None
    assert finding.rule_id == "management_tone_weakened"
    assert finding.severity == Severity.YELLOW
    assert "从订单充足变为需求承压" in finding.detail
    assert finding.evidence[0].source == "pdf.management_discussion"


def test_compare_management_tone_returns_none_when_not_weakened():
    llm = FakeLLM('{"weakened": false, "reason": "语气稳定", "evidence": "稳健"}')

    finding = compare_management_tone(
        llm,
        ts_code="000001.SZ",
        current_period="20250630",
        prior_period="20240630",
        current_text="经营稳健。",
        prior_text="经营稳健。",
    )

    assert finding is None


def test_compare_management_tone_returns_none_on_bad_llm_response():
    llm = FakeLLM("not-json")

    finding = compare_management_tone(
        llm,
        ts_code="000001.SZ",
        current_period="20250630",
        prior_period="20240630",
        current_text="需求承压。",
        prior_text="订单充足。",
    )

    assert finding is None
