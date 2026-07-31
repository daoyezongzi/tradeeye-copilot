from copilot.api.real_app import RealReportService
from copilot.models import Finding, Severity
from copilot.report.builder import CompanyCard
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_jobs import DisclosureJobStore
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureProgressEvent, build_analysis_bundle


class JobAnalyzer:
    def __init__(self):
        self.calls = []

    def analyze_disclosure_day_bundle(self, date, progress_callback=None, should_cancel=None):
        self.calls.append((date, progress_callback is not None, should_cancel is not None))
        card = CompanyCard(
            ts_code="603026.SH",
            period="20250630",
            fact_line="fact",
            findings=[Finding(rule_id="x", severity=Severity.RED, title="异常", detail="证据", evidence=[], score=99.0)],
            max_severity=Severity.RED,
            max_score=99.0,
        )
        if progress_callback is not None:
            progress_callback(
                DisclosureProgressEvent(
                    stage="company_started",
                    processed_count=0,
                    total_count=1,
                    ts_code="603026.SH",
                    period="20250630",
                )
            )
        return build_analysis_bundle(
            date=date,
            coverage_count=1,
            results=[("603026.SH", "20250630", "generic", CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=card))],
        )


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
    assert finished.bundle.scan.ok_count == 1
    assert finished.current_name == "石大胜华"
    assert service.analyzer.calls == [("20250825", True, True)]
    assert service.cache.company_codes == ["603026.SH"]
    assert service.cache.daily_dates == ["20250825"]


def test_real_report_service_cancel_marks_running_job_cancel_requested():
    service = JobReportService()
    job = service.job_store.start("20250825")

    cancelled = service.cancel_disclosure_day_job(job.job_id)

    assert cancelled.current_stage == "cancel_requested"
    assert service.job_store.should_cancel(job.job_id) is True
