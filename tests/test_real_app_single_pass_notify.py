from copilot.api.app import NotifyResult
from copilot.api.real_app import RealReportService
from copilot.models import Finding, Severity
from copilot.report.builder import CompanyCard
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_scan import CompanyAnalysisStatus, build_analysis_bundle


class FakeNotifier:
    def __init__(self):
        self.sent_text = None
        self.sent_parts = None

    def send_text(self, text):
        self.sent_text = text
        return True

    def send_text_parts(self, parts):
        self.sent_parts = parts
        return True


class FakeAnalyzer:
    def __init__(self):
        self.bundle_calls = 0

    def analyze_disclosure_day_bundle(self, date):
        self.bundle_calls += 1
        card = CompanyCard(
            ts_code="603026.SH",
            period="20250630",
            fact_line="fact",
            findings=[Finding(rule_id="x", severity=Severity.RED, title="异常", detail="证据", evidence=[], score=99.0)],
            max_severity=Severity.RED,
            max_score=99.0,
        )
        return build_analysis_bundle(
            date=date,
            coverage_count=1,
            results=[("603026.SH", "20250630", "generic", CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=card))],
        )


class FakeCache:
    def __init__(self):
        self.companies = []
        self.daily = None

    def put_company(self, card):
        self.companies.append(card.ts_code)

    def put_daily(self, summary):
        self.daily = summary.date


class FakeSettings:
    class Notify:
        feishu_webhook = "https://example.test/webhook"

    class Eval:
        company_names = {"603026.SH": "石大胜华"}
        coverage_pool = ["603026.SH"]
        start_date = "20250801"
        end_date = "20250831"

    notify = Notify()
    eval = Eval()


class BundleNotifyService(RealReportService):
    def __init__(self):
        self.settings = FakeSettings()
        self.analyzer = FakeAnalyzer()
        self.notifier = FakeNotifier()
        self.cache = FakeCache()

    def _send_feishu_text(self, text):
        return self.notifier.send_text(text)

    def _send_feishu_text_parts(self, parts):
        return self.notifier.send_text_parts(parts)


def test_notify_feishu_uses_one_bundle_call():
    service = BundleNotifyService()

    result = service.notify_feishu_disclosure_day("20250825")

    assert result == NotifyResult(sent=True, reason="ok")
    assert service.analyzer.bundle_calls == 1
    assert "603026.SH 石大胜华" in service.notifier.sent_parts[0]
    assert service.cache.companies == ["603026.SH"]
    assert service.cache.daily == "20250825"
