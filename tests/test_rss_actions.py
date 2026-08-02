import httpx
import pandas as pd

from copilot.rss.actions import run_rss_feishu_reminder, run_tushare_feishu_reminder


def test_run_rss_feishu_reminder_fetches_rss_and_posts_feishu_text():
    rss_xml = """
    <rss><channel>
      <item><title>石大胜华：2025年半年度报告</title><link>https://example.com/report</link></item>
    </channel></rss>
    """
    captured = []

    def handler(request):
        if str(request.url) == "https://example.com/rss.xml":
            return httpx.Response(200, text=rss_xml)
        captured.append(request.read().decode("utf-8"))
        return httpx.Response(200, json={"StatusCode": 0})

    result = run_rss_feishu_reminder(
        feeds=["https://example.com/rss.xml"],
        max_entries=10,
        company_to_ts_code={"石大胜华": "603026.SH"},
        company_names={"603026.SH": "石大胜华"},
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test",
        date="20250821",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result.sent is True
    assert result.reason == "ok"
    assert result.rss.matched_count == 1
    assert "20250821 财报披露提醒" in captured[0]
    assert "603026.SH 石大胜华 20250630" in captured[0]


class FakeTusharePro:
    def disclosure_date(self, ann_date):
        assert ann_date == "20250821"
        return pd.DataFrame([
            {"ts_code": "603026.SH", "ann_date": "20250821", "end_date": "20250630"},
            {"ts_code": "000001.SZ", "ann_date": "20250821", "end_date": "20250630"},
        ])


def test_run_tushare_feishu_reminder_posts_disclosure_calendar_matches():
    captured = []

    def handler(request):
        captured.append(request.read().decode("utf-8"))
        return httpx.Response(200, json={"StatusCode": 0})

    result = run_tushare_feishu_reminder(
        pro_api=FakeTusharePro(),
        coverage_pool=["603026.SH"],
        company_names={"603026.SH": "石大胜华"},
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test",
        date="20250821",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result.sent is True
    assert result.reason == "ok"
    assert result.rss.matched_count == 1
    assert "20250821 财报披露提醒" in captured[0]
    assert "603026.SH 石大胜华 20250630" in captured[0]


def test_run_rss_feishu_reminder_skips_send_without_matches():
    rss_xml = "<rss><channel><item><title>石大胜华：公告摘要</title><link>https://example.com/a</link></item></channel></rss>"
    posted = []

    def handler(request):
        if str(request.url) == "https://example.com/rss.xml":
            return httpx.Response(200, text=rss_xml)
        posted.append(str(request.url))
        return httpx.Response(200, json={"StatusCode": 0})

    result = run_rss_feishu_reminder(
        feeds=["https://example.com/rss.xml"],
        max_entries=10,
        company_to_ts_code={"石大胜华": "603026.SH"},
        company_names={"603026.SH": "石大胜华"},
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test",
        date="20250821",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result.sent is False
    assert result.reason == "no_matches"
    assert posted == []
