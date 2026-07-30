from copilot.models import Context
from copilot.report.builder import build_company_card, build_daily_summary
from copilot.service.report_cache import ReportCache


def test_report_cache_stores_company_cards(make_snapshot):
    cache = ReportCache()
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])

    cache.put_company(card)

    assert cache.get_company("000001.SZ", "20250630") == card
    assert cache.get_company("000001.SZ", "20240630") is None


def test_report_cache_stores_daily_summaries(make_snapshot):
    cache = ReportCache()
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    summary = build_daily_summary("20250821", 42, [card])

    cache.put_daily(summary)

    assert cache.get_daily("20250821") == summary
    assert cache.get_daily("20250822") is None
