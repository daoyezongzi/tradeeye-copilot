from copilot.models import Finding, Severity
from copilot.report.builder import CompanyCard
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_jobs import SQLiteDisclosureJobStore
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


def test_sqlite_disclosure_job_store_persists_status_across_instances(tmp_path):
    path = tmp_path / "jobs.sqlite"
    first = SQLiteDisclosureJobStore(path, company_names={"603026.SH": "石大胜华"})
    first.init_schema()
    job = first.start("20250825")
    first.apply_progress(
        job.job_id,
        stage="fetch_cashflow",
        processed_count=0,
        total_count=2,
        ts_code="603026.SH",
        period="20250630",
    )
    first.request_cancel(job.job_id)
    first.mark_cancelled(job.job_id, _bundle("20250825"))

    second = SQLiteDisclosureJobStore(path, company_names={"603026.SH": "石大胜华"})
    second.init_schema()
    restored = second.get(job.job_id)

    assert restored.status == "cancelled"
    assert restored.current_name == "石大胜华"
    assert restored.current_stage == "cancelled"
    assert restored.bundle.scan.disclosed_count == 1
    assert second.should_cancel(job.job_id) is True


def test_sqlite_disclosure_job_store_lists_recent_jobs_across_instances(tmp_path):
    path = tmp_path / "jobs.sqlite"
    first = SQLiteDisclosureJobStore(path, company_names={"603026.SH": "石大胜华"})
    first.init_schema()
    older = first.start("20250824")
    newer = first.start("20250825")
    first.mark_failed(older.job_id, "boom")
    first.mark_completed(newer.job_id, _bundle("20250825"))

    second = SQLiteDisclosureJobStore(path, company_names={"603026.SH": "石大胜华"})
    second.init_schema()
    jobs = second.list_recent(limit=2)

    assert [job.job_id for job in jobs] == [newer.job_id, older.job_id]
    assert jobs[0].status == "completed"
    assert jobs[0].bundle.scan.disclosed_count == 1
