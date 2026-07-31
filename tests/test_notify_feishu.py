import httpx

from copilot.models import Context, Evidence, Finding, Severity
from copilot.notify.feishu import FeishuNotifier, render_daily_summary_text, render_disclosure_interactive_card
from copilot.report.builder import build_company_card, build_daily_summary


def test_render_daily_summary_text(make_snapshot):
    finding = Finding(
        rule_id="cashflow_quality",
        severity=Severity.YELLOW,
        title="现金流质量偏弱",
        detail="经营现金流/净利润 = 40.0%",
        evidence=[Evidence(source="tushare.cashflow", field="operating_cash_flow", period="20250630", value=4.0)],
        score=60.0,
    )
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [finding])
    summary = build_daily_summary("20250821", 42, [card])

    text = render_daily_summary_text(summary)

    assert "20250821 财报研判 · 覆盖池 42 只" in text
    assert "今日披露 1 家" in text
    assert "000001.SZ" in text
    assert "现金流质量偏弱" in text


def test_feishu_notifier_posts_text_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = request.read().decode("utf-8")
        return httpx.Response(200, json={"StatusCode": 0})

    notifier = FeishuNotifier(
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert notifier.send_text("hello") is True
    assert captured["url"] == "https://open.feishu.cn/open-apis/bot/v2/hook/test"
    assert '"msg_type":"text"' in captured["json"].replace(" ", "")
    assert "hello" in captured["json"]


def test_render_disclosure_interactive_card_includes_review_actions(make_snapshot):
    finding = Finding(
        rule_id="cashflow_quality",
        severity=Severity.RED,
        title="现金流质量偏弱",
        detail="经营现金流/净利润 = 27.0%",
        evidence=[],
        score=73.0,
    )
    card = build_company_card(Context(ts_code="603026.SH", current=make_snapshot(ts_code="603026.SH")), [finding])
    summary = build_daily_summary("20250825", 100, [card])

    payload = render_disclosure_interactive_card(summary, {"603026.SH": "石大胜华"}, base_url="https://tradeeye.example.com")

    assert payload["msg_type"] == "interactive"
    assert payload["card"]["header"]["title"]["content"] == "20250825 财报披露研判"
    elements = str(payload["card"]["elements"])
    assert "603026.SH 石大胜华" in elements
    assert "确认异常" in elements
    assert "标记误报" in elements
    assert "https://tradeeye.example.com/#/company/603026.SH/20250630" in elements
