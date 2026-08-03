from copilot.models import Finding, Severity
from copilot.report.builder import CompanyCard
from copilot.service.analyzer import CompanyAnalysisResult
from copilot.service.disclosure_jobs import DisclosureJobStore, SQLiteDisclosureJobStore
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


def test_disclosure_job_store_tracks_pause_and_resume_requests():
    store = DisclosureJobStore(company_names={})
    job = store.start("20250825")

    pause_request = store.request_pause(job.job_id)
    assert pause_request.current_stage == "pause_requested"
    assert store.should_pause(job.job_id) is True

    paused = store.mark_paused(job.job_id, _bundle("20250825"))
    assert paused.status == "paused"
    assert paused.bundle.scan.disclosed_count == 1

    resumed = store.request_resume(job.job_id)
    assert resumed.status == "running"
    assert resumed.current_stage == "resume_requested"
    assert store.should_pause(job.job_id) is False



    store = DisclosureJobStore(company_names={})
    job = store.start("20250825")

    completed = store.mark_completed(job.job_id, _bundle("20250825"))

    assert completed.status == "completed"
    assert completed.ok_count == 1
    assert completed.data_problem_count == 0
    assert completed.bundle.summary.red_count == 1

def test_disclosure_job_store_cancels_paused_job_with_partial_bundle():
    store = DisclosureJobStore(company_names={})
    job = store.start("20250825")
    paused = store.mark_paused(job.job_id, _bundle("20250825"))

    cancelled = store.request_cancel(paused.job_id)

    assert cancelled.status == "cancelled"
    assert cancelled.current_stage == "cancelled"
    assert cancelled.bundle.scan.disclosed_count == 1
    assert store.should_pause(job.job_id) is False
    assert store.should_cancel(job.job_id) is True

def test_sqlite_disclosure_job_store_persists_cancelled_paused_job(tmp_path):
    path = tmp_path / "jobs.sqlite"
    store = SQLiteDisclosureJobStore(path)
    job = store.start("20250825")
    store.mark_paused(job.job_id, _bundle("20250825"))

    cancelled = store.request_cancel(job.job_id)
    reloaded = SQLiteDisclosureJobStore(path).get(job.job_id)

    assert cancelled.status == "cancelled"
    assert reloaded.status == "cancelled"
    assert reloaded.current_stage == "cancelled"
    assert reloaded.bundle.scan.disclosed_count == 1


def test_disclosure_job_store_blocks_cross_owner_resume_source():
    store = DisclosureJobStore(company_names={})
    source = store.start("20250825", owner_id="alice")

    try:
        store.start("20250825", resume_from_job_id=source.job_id, owner_id="bob")
    except PermissionError as exc:
        assert source.job_id in str(exc)
    else:
        raise AssertionError("expected PermissionError")


def test_disclosure_job_store_filters_by_owner_and_blocks_cross_owner_get():
    store = DisclosureJobStore(company_names={})
    alice = store.start("20250825", owner_id="alice")
    bob = store.start("20250825", owner_id="bob")

    assert [job.job_id for job in store.list_recent(limit=10, owner_id="alice")] == [alice.job_id]
    assert [job.job_id for job in store.list_recent(limit=10, owner_id="bob")] == [bob.job_id]

    try:
        store.get(alice.job_id, owner_id="bob")
    except PermissionError as exc:
        assert alice.job_id in str(exc)
    else:
        raise AssertionError("expected PermissionError")



def test_disclosure_job_store_prunes_old_finished_jobs():
    store = DisclosureJobStore(company_names={})
    oldest = store.start("20250823")
    middle = store.start("20250824")
    newest = store.start("20250825")
    store.mark_completed(oldest.job_id, _bundle("20250823"))
    store.mark_completed(middle.job_id, _bundle("20250824"))
    store.mark_completed(newest.job_id, _bundle("20250825"))

    removed = store.prune_finished(keep_recent=2)

    assert removed == 1
    assert [job.job_id for job in store.list_recent(limit=5)] == [newest.job_id, middle.job_id]
