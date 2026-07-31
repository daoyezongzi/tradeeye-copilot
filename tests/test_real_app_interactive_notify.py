from copilot.api.real_app import RealReportService
from copilot.models import Finding, Severity
from copilot.report.builder import CompanyCard, DailySummary
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureScanEvent, build_scan_result


class FakeNotifyLogStore:
    def __init__(self):
        self.sent_keys = set()
        self.attempts = []

    def already_sent(self, channel, dedupe_key):
        return (channel, dedupe_key) in self.sent_keys

    def record_attempt(self, channel, dedupe_key, sent, reason):
        self.attempts.append((channel, dedupe_key, sent, reason))
        if sent:
            self.sent_keys.add((channel, dedupe_key))


class InteractiveNotifyService(RealReportService):
    def __init__(self):
        self.sent_payloads = []
        self.notify_store = FakeNotifyLogStore()
        card = CompanyCard(
            ts_code="603026.SH",
            period="20250630",
            fact_line="fact",
            findings=[Finding(rule_id="cashflow_quality", severity=Severity.RED, title="异常", detail="证据", evidence=[], score=99.0)],
            max_severity=Severity.RED,
            max_score=99.0,
        )
        self.bundle = type(
            "Bundle",
            (),
            {
                "summary": DailySummary(date="20250825", coverage_count=1, disclosed_count=1, red_count=1, yellow_count=0, ok_count=0, cards=[card]),
                "scan": build_scan_result(
                    date="20250825",
                    coverage_count=1,
                    events=[DisclosureScanEvent(ts_code="603026.SH", period="20250630", status=CompanyAnalysisStatus.OK, message="ok", has_card=True, industry="generic")],
                ),
            },
        )()
        self.settings = type(
            "Settings",
            (),
            {
                "notify": type("Notify", (), {"feishu_webhook": "https://open.feishu.cn/hook/test", "public_base_url": "https://tradeeye.example.com"})(),
                "eval": type("Eval", (), {"company_names": {"603026.SH": "石大胜华"}})(),
            },
        )()

    def analyze_disclosure_day_bundle(self, date):
        return self.bundle

    def _send_feishu_interactive(self, payload):
        self.sent_payloads.append(payload)
        return True


def test_real_report_service_sends_interactive_feishu_card():
    service = InteractiveNotifyService()

    result = service.notify_feishu_disclosure_day("20250825")

    assert result.sent is True
    assert result.reason == "ok"
    assert service.sent_payloads[0]["msg_type"] == "interactive"
    assert service.sent_payloads[0]["card"]["header"]["title"]["content"] == "20250825 财报披露研判"
    assert "https://tradeeye.example.com/#/company/603026.SH/20250630" in str(service.sent_payloads[0]["card"]["elements"])


def test_real_report_service_skips_duplicate_successful_feishu_send():
    service = InteractiveNotifyService()

    first = service.notify_feishu_disclosure_day("20250825")
    second = service.notify_feishu_disclosure_day("20250825")

    assert first.sent is True
    assert second.sent is False
    assert second.reason == "already_sent"
    assert len(service.sent_payloads) == 1
