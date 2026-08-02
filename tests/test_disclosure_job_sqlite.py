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

def test_sqlite_disclosure_job_store_persists_pause_across_instances(tmp_path):
    path = tmp_path / "jobs.sqlite"
    first = SQLiteDisclosureJobStore(path, company_names={"603026.SH": "石大胜华"})
    first.init_schema()
    job = first.start("20250825")
    first.request_pause(job.job_id)
    first.mark_paused(job.job_id, _bundle("20250825"))

    second = SQLiteDisclosureJobStore(path, company_names={"603026.SH": "石大胜华"})
    second.init_schema()
    restored = second.get(job.job_id)

    assert restored.status == "paused"
    assert restored.current_stage == "paused"
    assert restored.bundle.scan.disclosed_count == 1
    assert second.should_pause(job.job_id) is True


    path = tmp_path / "jobs.sqlite"
    first = SQLiteDisclosureJobStore(path, company_names={"603026.SH": "石大胜华"})
    first.init_schema()
    original = first.start("20250825")
    first.mark_cancelled(original.job_id, _bundle("20250825"))
    resumed = first.start("20250825", resume_from_job_id=original.job_id)

    second = SQLiteDisclosureJobStore(path, company_names={"603026.SH": "石大胜华"})
    second.init_schema()
    restored = second.get(resumed.job_id)

    assert restored.resume_from_job_id == original.job_id


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

def test_sqlite_disclosure_job_store_prunes_finished_rows_across_instances(tmp_path):
    path = tmp_path / "jobs.sqlite"
    first = SQLiteDisclosureJobStore(path, company_names={"603026.SH": "石大胜华"})
    first.init_schema()
    oldest = first.start("20250823")
    middle = first.start("20250824")
    newest = first.start("20250825")
    first.mark_completed(oldest.job_id, _bundle("20250823"))
    first.mark_failed(middle.job_id, "boom")
    first.mark_completed(newest.job_id, _bundle("20250825"))

    removed = first.prune_finished(keep_recent=2)

    second = SQLiteDisclosureJobStore(path, company_names={"603026.SH": "石大胜华"})
    second.init_schema()
    jobs = second.list_recent(limit=5)

    assert removed == 1
    assert [job.job_id for job in jobs] == [newest.job_id, middle.job_id]


def test_sqlite_disclosure_job_store_filters_owner_across_instances(tmp_path):
    path = tmp_path / "jobs.sqlite"
    first = SQLiteDisclosureJobStore(path, company_names={"603026.SH": "石大胜华"})
    first.init_schema()
    first.start("20250825", owner_id="bob")
    alice = first.start("20250825", owner_id="alice")
    first.start("20250825", owner_id="bob")

    second = SQLiteDisclosureJobStore(path, company_names={"603026.SH": "石大胜华"})
    second.init_schema()

    assert [job.job_id for job in second.list_recent(limit=1, owner_id="alice")] == [alice.job_id]
    try:
        second.get(alice.job_id, owner_id="bob")
    except PermissionError as exc:
        assert alice.job_id in str(exc)
    else:
        raise AssertionError("expected PermissionError")
