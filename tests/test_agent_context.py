from copilot.agent.context import SYSTEM_PROMPT, build_preset_context
from copilot.models import Context
from copilot.report.builder import build_company_card


def test_build_preset_context_includes_card_facts(make_snapshot):
    ctx = Context(ts_code="000001.SZ", current=make_snapshot(revenue=128.4))
    card = build_company_card(ctx, [])

    preset = build_preset_context(card)

    assert '"fact_id": "revenue"' in preset
    assert "128.4" in preset


def test_system_prompt_declares_read_only_and_output_format():
    assert "不得自行计算" in SYSTEM_PROMPT
    assert '"answer"' in SYSTEM_PROMPT
    assert "references" in SYSTEM_PROMPT
