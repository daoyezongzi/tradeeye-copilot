from pydantic import BaseModel
import httpx

from copilot.datasource.calendar import TushareDisclosureCalendarClient
from copilot.notify.feishu import FeishuNotifier, render_rss_disclosure_reminder_text
from copilot.rss.announcements import AnnouncementEvent
from copilot.rss.service import RssPollResult, RssPollService


class RssFeishuReminderResult(BaseModel):
    rss: RssPollResult
    sent: bool = False
    reason: str


class _NoopAnalyzer:
    def analyze_company(self, ts_code: str, period: str):
        raise AssertionError("RSS reminder must not analyze companies")


def run_tushare_feishu_reminder(
    pro_api,
    coverage_pool: list[str],
    company_names: dict[str, str],
    webhook_url: str | None,
    date: str,
    http_client: httpx.Client | None = None,
) -> RssFeishuReminderResult:
    client = http_client or httpx.Client(timeout=10)
    events = TushareDisclosureCalendarClient(pro_api).fetch_events(date, set(coverage_pool))
    announcement_events = [
        AnnouncementEvent(
            ts_code=event.ts_code,
            title=f"{company_names.get(event.ts_code, event.ts_code)}：{event.period} 财报披露",
            link="",
            period=event.period,
            status="MATCHED",
        )
        for event in events
    ]
    rss = RssPollResult(
        seen_count=len(events),
        matched_count=len(announcement_events),
        analyzed_count=0,
        pending_count=0,
        events=announcement_events,
    )
    if rss.matched_count == 0:
        return RssFeishuReminderResult(rss=rss, sent=False, reason="no_matches")
    if not webhook_url:
        return RssFeishuReminderResult(rss=rss, sent=False, reason="webhook_not_configured")
    text = render_rss_disclosure_reminder_text(date, rss.events, company_names)
    sent = FeishuNotifier(webhook_url, http_client=client).send_text(text)
    return RssFeishuReminderResult(rss=rss, sent=sent, reason="ok" if sent else "send_failed")


def run_rss_feishu_reminder(
    feeds: list[str],
    max_entries: int,
    company_to_ts_code: dict[str, str],
    company_names: dict[str, str],
    webhook_url: str | None,
    date: str,
    http_client: httpx.Client | None = None,
) -> RssFeishuReminderResult:
    client = http_client or httpx.Client(timeout=10)
    rss = RssPollService(
        feeds=feeds,
        max_entries=max_entries,
        company_to_ts_code=company_to_ts_code,
        analyzer=_NoopAnalyzer(),
        http_client=client,
    ).poll()
    if rss.matched_count == 0:
        return RssFeishuReminderResult(rss=rss, sent=False, reason="no_matches")
    if not webhook_url:
        return RssFeishuReminderResult(rss=rss, sent=False, reason="webhook_not_configured")
    text = render_rss_disclosure_reminder_text(date, rss.events, company_names)
    sent = FeishuNotifier(webhook_url, http_client=client).send_text(text)
    return RssFeishuReminderResult(rss=rss, sent=sent, reason="ok" if sent else "send_failed")
