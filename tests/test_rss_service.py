import httpx

from copilot.models import Context
from copilot.report.builder import build_company_card
from copilot.rss.service import RssPollService
from copilot.service.analyzer import CompanyAnalysisResult, CompanyAnalysisStatus


class FakeAnalyzer:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def analyze_company(self, ts_code, period):
        self.calls.append((ts_code, period))
        return self.result


def test_rss_poll_service_matches_announcements_without_analyzing(make_snapshot):
    xml = """
    <rss><channel>
      <item><title>平安银行：2025年半年度报告</title><link>https://example.com/a</link></item>
    </channel></rss>
    """
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    analyzer = FakeAnalyzer(CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=card))

    def handler(request):
        return httpx.Response(200, text=xml)

    service = RssPollService(
        feeds=["https://example.com/rss.xml"],
        max_entries=10,
        company_to_ts_code={"平安银行": "000001.SZ"},
        analyzer=analyzer,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = service.poll()

    assert result.seen_count == 1
    assert result.matched_count == 1
    assert result.analyzed_count == 0
    assert result.pending_count == 0
    assert result.events[0].status == "MATCHED"
    assert analyzer.calls == []


def test_rss_poll_service_does_not_mark_pending_when_tushare_not_ready_because_it_does_not_fetch():
    xml = """
    <rss><channel>
      <item><title>平安银行：2025年半年度报告</title><link>https://example.com/a</link></item>
    </channel></rss>
    """
    analyzer = FakeAnalyzer(CompanyAnalysisResult(status=CompanyAnalysisStatus.DATA_NOT_READY, message="not ready"))

    def handler(request):
        return httpx.Response(200, text=xml)

    service = RssPollService(
        feeds=["https://example.com/rss.xml"],
        max_entries=10,
        company_to_ts_code={"平安银行": "000001.SZ"},
        analyzer=analyzer,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = service.poll()

    assert result.analyzed_count == 0
    assert result.pending_count == 0
    assert result.events[0].status == "MATCHED"
    assert analyzer.calls == []
