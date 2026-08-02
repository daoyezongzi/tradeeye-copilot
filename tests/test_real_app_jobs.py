from copilot.api.real_app import RealReportService
from copilot.models import Finding, Severity
from copilot.report.builder import CompanyCard
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_jobs import DisclosureJobStore
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureProgressEvent, build_analysis_bundle


class JobAnalyzer:
    def __init__(self):
        self.calls = []

    def analyze_disclosure_day_bundle(self, date, progress_callback=None, should_cancel=None, should_pause=None, skip_ts_codes=None):
        self.calls.append((date, progress_callback is not None, should_cancel is not None, should_pause is not None, frozenset(skip_ts_codes or set())))
        cards = {
            "603026.SH": CompanyCard(
                ts_code="603026.SH",
                period="20250630",
                fact_line="fact",
                findings=[Finding(rule_id="x", severity=Severity.RED, title="异常", detail="证据", evidence=[], score=99.0)],
                max_severity=Severity.RED,
                max_score=99.0,
            ),
            "600151.SH": CompanyCard(
                ts_code="600151.SH",
                period="20250630",
                fact_line="fact",
                findings=[],
                max_severity=None,
                max_score=0.0,
            ),
            "000001.SZ": CompanyCard(
                ts_code="000001.SZ",
                period="20250630",
                fact_line="数据问题：missing",
                findings=[],
                max_severity=None,
                max_score=0.0,
                card_status="BLOCKED",
            ),
        }
        statuses = {
            "603026.SH": CompanyAnalysisStatus.OK,
            "600151.SH": CompanyAnalysisStatus.OK,
            "000001.SZ": CompanyAnalysisStatus.DATA_NOT_READY,
        }
        results = []
        for ts_code, card in cards.items():
            if ts_code in (skip_ts_codes or set()):
                continue
            if progress_callback is not None:
                progress_callback(
                    DisclosureProgressEvent(
                        stage="company_started",
                        processed_count=len(results),
                        total_count=len(cards) - len(skip_ts_codes or set()),
                        ts_code=ts_code,
                        period="20250630",
                    )
                )
            results.append((ts_code, "20250630", "generic", CompanyAnalysisResult(status=statuses[ts_code], message="ok", card=card)))
        return build_analysis_bundle(date=date, coverage_count=3, results=results)


class JobCache:
    def __init__(self):
        self.company_codes = []
        self.daily_dates = []

    def put_company(self, card):
        self.company_codes.append(card.ts_code)

    def put_daily(self, summary):
        self.daily_dates.append(summary.date)


class JobSettings:
    class Eval:
        coverage_pool = ["603026.SH"]
        company_names = {"603026.SH": "石大胜华"}

    eval = Eval()


class JobReportService(RealReportService):
    def __init__(self):
        self.settings = JobSettings()
        self.analyzer = JobAnalyzer()
        self.cache = JobCache()
        self.job_store = DisclosureJobStore(company_names=self.settings.eval.company_names)


def test_real_report_service_starts_job_then_runs_to_completion():
    service = JobReportService()

    started = service.start_disclosure_day_job("20250825")
    assert started.status == "running"
    assert service.analyzer.calls == []

    service.run_disclosure_day_job(started.job_id)
    finished = service.get_disclosure_day_job(started.job_id)

    assert finished.status == "completed"
    assert finished.bundle.scan.ok_count == 2
    blocked = next(card for card in finished.bundle.summary.cards if card.ts_code == "000001.SZ")
    assert blocked.card_status.value == "BLOCKED"
    assert finished.current_name == "000001.SZ"
    assert service.analyzer.calls == [("20250825", True, True, True, frozenset())]
    assert service.cache.company_codes == ["603026.SH", "000001.SZ", "600151.SH"]
    assert service.cache.daily_dates == ["20250825"]

def test_real_report_service_resumes_from_cancelled_job_without_reprocessing_completed_companies():
    service = JobReportService()
    original = service.job_store.start("20250825")
    partial = build_analysis_bundle(
        date="20250825",
        coverage_count=2,
        results=[
            (
                "603026.SH",
                "20250630",
                "generic",
                CompanyAnalysisResult(
                    status=CompanyAnalysisStatus.OK,
                    message="ok",
                    card=CompanyCard(
                        ts_code="603026.SH",
                        period="20250630",
                        fact_line="fact",
                        findings=[Finding(rule_id="x", severity=Severity.RED, title="异常", detail="证据", evidence=[], score=99.0)],
                        max_severity=Severity.RED,
                        max_score=99.0,
                    ),
                ),
            )
        ],
    )
    service.job_store.mark_cancelled(original.job_id, partial)

    resumed = service.start_disclosure_day_job("20250825", resume_from_job_id=original.job_id)
    service.run_disclosure_day_job(resumed.job_id)
    finished = service.get_disclosure_day_job(resumed.job_id)

    assert service.analyzer.calls == [("20250825", True, True, True, frozenset({"603026.SH"}))]
    assert finished.status == "completed"
    assert finished.bundle.scan.disclosed_count == 3
    assert [event.ts_code for event in finished.bundle.scan.events] == ["603026.SH", "600151.SH", "000001.SZ"]
    assert {card.ts_code for card in finished.bundle.summary.cards} == {"603026.SH", "600151.SH", "000001.SZ"}


    service = JobReportService()
    job = service.job_store.start("20250825")

    cancelled = service.cancel_disclosure_day_job(job.job_id)

    assert cancelled.current_stage == "cancel_requested"
    assert service.job_store.should_cancel(job.job_id) is True
