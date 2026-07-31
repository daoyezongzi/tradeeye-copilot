from copilot.models import Finding, Severity
from copilot.report.builder import CompanyCard
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_jobs import DisclosureJobStore
from copilot.service.disclosure_scan import CompanyAnalysisStatus, build_analysis_bundle


def _bundle(date):
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
        coverage_count=2,
        results=[("603026.SH", "20250630", "generic", CompanyAnalysisResult(status=CompanyAnalysisStatus.OK, message="ok", card=card))],
    )


def test_disclosure_job_store_tracks_progress_result_and_cancel():
    store = DisclosureJobStore(company_names={"603026.SH": "石大胜华"})

    job = store.start("20250825")
    assert job.status == "running"
    assert job.current_stage == "queued"

    store.apply_progress(
        job.job_id,
        stage="company_started",
        processed_count=0,
        total_count=2,
        ts_code="603026.SH",
        period="20250630",
    )
    store.set_active(job.job_id)
    store.apply_table_progress("fetch_cashflow", "603026.SH", "20250630")
    progress = store.get(job.job_id)
    assert progress.current_stage == "fetch_cashflow"
    assert progress.current_name == "石大胜华"
    assert progress.total_count == 2

    store.request_cancel(job.job_id)
    assert store.should_cancel(job.job_id) is True
    cancelled = store.mark_cancelled(job.job_id, _bundle("20250825"))
    assert cancelled.status == "cancelled"
    assert cancelled.bundle.scan.disclosed_count == 1
    assert cancelled.processed_count == 1


def test_disclosure_job_store_marks_completed_with_bundle():
    store = DisclosureJobStore(company_names={})
    job = store.start("20250825")

    completed = store.mark_completed(job.job_id, _bundle("20250825"))

    assert completed.status == "completed"
    assert completed.ok_count == 1
    assert completed.data_problem_count == 0
    assert completed.bundle.summary.red_count == 1
