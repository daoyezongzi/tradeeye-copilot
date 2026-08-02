# Scan Card Completeness and Pause Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure every disclosure scan event produces an Agent-usable company card, and provide explicit scan controls for start, pause/continue, and stop.

**Architecture:** Keep the single-pass disclosure job architecture. Convert data-not-ready / data-incomplete / error results into blocked `CompanyCard` objects so summaries, cache, and Agent all share the same per-event card contract. Add pause/resume state to the job store and expose dedicated API/front-end controls without changing destructive stop semantics.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLite job persistence, pytest, vanilla JavaScript, Node syntax/productization tests.

---

## File Structure

- Modify `copilot/report/builder.py`: add `build_blocked_company_card()` for data-problem scan events.
- Modify `copilot/service/analyzer.py`: return blocked cards for `DATA_NOT_READY`, `DATA_INCOMPLETE`, and `ERROR` instead of `card=None`.
- Modify `copilot/service/disclosure_scan.py`: preserve `has_card=True` when blocked cards are produced.
- Modify `copilot/agent/context.py`: include `card_status` and `fact_line` in Agent preset context.
- Modify `copilot/service/disclosure_jobs.py`: add pause/resume request state and paused status transitions.
- Modify `copilot/api/app.py`: add `/pause` and `/resume` job routes.
- Modify `copilot/api/real_app.py`: expose `pause_disclosure_day_job()` and `resume_disclosure_day_job()`.
- Modify `web/index.html`: replace one scan button with start/pause/resume/stop controls.
- Modify `web/app.js`: implement scan control state machine and call new pause/resume routes.
- Modify `tests/test_disclosure_analysis_bundle.py`, `tests/test_real_app_jobs.py`, `tests/test_disclosure_jobs.py`, `tests/test_api_disclosure_jobs.py`, `tests/test_frontend_productization.py`: cover new behavior.

---

### Task 1: Create blocked cards for every scan event

**Files:**
- Modify: `copilot/report/builder.py`
- Modify: `copilot/service/analyzer.py`
- Modify: `copilot/agent/context.py`
- Test: `tests/test_disclosure_analysis_bundle.py`

- [ ] **Step 1: Write failing tests for data-problem cards**

In `tests/test_disclosure_analysis_bundle.py`, update `test_build_analysis_bundle_derives_summary_and_scan_from_one_result_set` expected cards:

```python
assert [card.ts_code for card in bundle.summary.cards] == ["603026.SH", "000001.SZ"]
assert bundle.summary.cards[1].card_status.value == "BLOCKED"
assert bundle.summary.cards[1].fact_line == "数据问题：missing"
assert bundle.scan.events[1].has_card is True
```

Add this test:

```python
def test_analyzer_returns_blocked_card_when_current_snapshot_not_ready():
    fundamentals = BundleFundamentals()
    service = AnalyzerService(
        fundamentals=fundamentals,
        store=BundleStore(),
        coverage_pool=["000001.SZ"],
        calendar=BundleCalendar(),
        company_industries={"000001.SZ": "bank"},
    )

    result = service.analyze_company("000001.SZ", "20250630")

    assert result.status == CompanyAnalysisStatus.DATA_NOT_READY
    assert result.card is not None
    assert result.card.ts_code == "000001.SZ"
    assert result.card.period == "20250630"
    assert result.card.card_status.value == "BLOCKED"
    assert result.card.fact_line.startswith("数据问题：Tushare 暂未返回")
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp tests/test_disclosure_analysis_bundle.py::test_build_analysis_bundle_derives_summary_and_scan_from_one_result_set tests/test_disclosure_analysis_bundle.py::test_analyzer_returns_blocked_card_when_current_snapshot_not_ready -q
```

Expected: FAIL because data-problem results still have `card=None`.

- [ ] **Step 3: Add blocked card builder**

In `copilot/report/builder.py`, add after `build_company_card`:

```python
def build_blocked_company_card(ts_code: str, period: str, message: str, company: CompanyIdentity | None = None) -> CompanyCard:
    return CompanyCard(
        ts_code=ts_code,
        period=period,
        fact_line=f"数据问题：{message}",
        findings=[],
        max_severity=None,
        max_score=0.0,
        company=company,
        card_status=CardStatus.BLOCKED,
        facts=[],
        rule_results=[],
    )
```

- [ ] **Step 4: Use blocked cards in analyzer**

In `copilot/service/analyzer.py`, import `build_blocked_company_card`:

```python
from copilot.report.builder import CompanyCard, DailySummary, build_blocked_company_card, build_company_card, build_facts
```

For `_current_ready` failure, return:

```python
message = f"Tushare 暂未返回 {ts_code} {period} 的完整财务快照"
return CompanyAnalysisResult(
    status=CompanyAnalysisStatus.DATA_NOT_READY,
    message=message,
    card=build_blocked_company_card(ts_code, period, message),
)
```

For hard-check failure, return:

```python
message = "；".join(check.messages)
return CompanyAnalysisResult(
    status=CompanyAnalysisStatus.DATA_INCOMPLETE,
    message=message,
    card=build_blocked_company_card(ts_code, period, message),
)
```

For broad exception, return:

```python
message = str(exc)
return CompanyAnalysisResult(
    status=CompanyAnalysisStatus.ERROR,
    message=message,
    card=build_blocked_company_card(ts_code, period, message),
)
```

- [ ] **Step 5: Include card status in Agent context**

In `copilot/agent/context.py`, add to payload:

```python
"card_status": card.card_status,
"fact_line": card.fact_line,
```

- [ ] **Step 6: Verify blocked card tests pass**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp tests/test_disclosure_analysis_bundle.py::test_build_analysis_bundle_derives_summary_and_scan_from_one_result_set tests/test_disclosure_analysis_bundle.py::test_analyzer_returns_blocked_card_when_current_snapshot_not_ready -q
```

Expected: PASS.

---

### Task 2: Cache blocked scan cards for Agent use

**Files:**
- Modify: `copilot/api/real_app.py`
- Test: `tests/test_real_app_jobs.py`

- [ ] **Step 1: Add regression test for blocked cards cached after job restore**

In `tests/test_real_app_jobs.py`, add a data-problem card to `JobAnalyzer` cards:

```python
"000001.SZ": CompanyCard(
    ts_code="000001.SZ",
    period="20250630",
    fact_line="数据问题：missing",
    findings=[],
    max_severity=None,
    max_score=0.0,
    card_status="BLOCKED",
),
```

Change expected cache codes:

```python
assert service.cache.company_codes == ["603026.SH", "600151.SH", "000001.SZ"]
```

Add:

```python
assert finished.bundle.summary.cards[-1].card_status.value == "BLOCKED"
```

- [ ] **Step 2: Run regression test**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp tests/test_real_app_jobs.py::test_real_report_service_starts_job_then_runs_to_completion -q
```

Expected: PASS after Task 1 if cache already puts every summary card; FAIL indicates `_cache_bundle()` still filters data-problem cards.

---

### Task 3: Add pause/resume job state

**Files:**
- Modify: `copilot/service/disclosure_jobs.py`
- Modify: `copilot/service/analyzer.py`
- Modify: `copilot/api/real_app.py`
- Test: `tests/test_disclosure_jobs.py`
- Test: `tests/test_real_app_jobs.py`

- [ ] **Step 1: Write failing job store pause tests**

Add to `tests/test_disclosure_jobs.py`:

```python
def test_disclosure_job_store_tracks_pause_and_resume_requests():
    store = DisclosureJobStore(company_names={})
    job = store.start("20250825")

    paused_request = store.request_pause(job.job_id)
    assert paused_request.current_stage == "pause_requested"
    assert store.should_pause(job.job_id) is True

    paused = store.mark_paused(job.job_id, _bundle("20250825"))
    assert paused.status == "paused"
    assert paused.bundle.scan.disclosed_count == 1

    resumed = store.request_resume(job.job_id)
    assert resumed.status == "running"
    assert resumed.current_stage == "resume_requested"
    assert store.should_pause(job.job_id) is False
```

- [ ] **Step 2: Run job store pause RED**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp tests/test_disclosure_jobs.py::test_disclosure_job_store_tracks_pause_and_resume_requests -q
```

Expected: FAIL because pause methods are missing.

- [ ] **Step 3: Implement pause/resume in job store**

In `DisclosureJobStore.__init__`, add:

```python
self._pause_requested: set[str] = set()
```

Add methods:

```python
def request_pause(self, job_id: str, owner_id: str | None = None) -> DisclosureJobStatus:
    status = self.get(job_id, owner_id=owner_id)
    self._pause_requested.add(job_id)
    if status.status == "running":
        status.current_stage = "pause_requested"
        status.logs.append("pause requested")
    return self.get(job_id, owner_id=owner_id)

def request_resume(self, job_id: str, owner_id: str | None = None) -> DisclosureJobStatus:
    status = self.get(job_id, owner_id=owner_id)
    self._pause_requested.discard(job_id)
    if status.status == "paused":
        status.status = "running"
        status.current_stage = "resume_requested"
        status.logs.append("resume requested")
    return self.get(job_id, owner_id=owner_id)

def should_pause(self, job_id: str) -> bool:
    return job_id in self._pause_requested

def mark_paused(self, job_id: str, bundle: DisclosureAnalysisBundle) -> DisclosureJobStatus:
    status = self._jobs[job_id]
    status.status = "paused"
    status.current_stage = "paused"
    self._apply_bundle_counts(status, bundle)
    status.bundle = bundle
    return self.get(job_id)
```

Update `prune_finished` status set to include `paused` only if paused jobs should be pruned after keep_recent; keep paused jobs by not adding it to finished set.

In `SQLiteDisclosureJobStore`, persist `_pause_requested` by adding a `pause_requested` column is too large for this pass. Instead store it in `payload.current_stage` and set membership on `_load` when status/current_stage indicates pause. Update `_persist` payload after request methods. Add overrides for `request_pause`, `request_resume`, `mark_paused` mirroring cancel persistence.

- [ ] **Step 4: Run job store pause tests GREEN**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp tests/test_disclosure_jobs.py::test_disclosure_job_store_tracks_pause_and_resume_requests -q
```

Expected: PASS.

- [ ] **Step 5: Make analyzer stop safely on pause**

In `AnalyzerService.analyze_disclosure_day_bundle`, add optional `should_pause=None` parameter. At top of each event loop before cancellation, check:

```python
if should_pause is not None and should_pause():
    if progress_callback is not None:
        progress_callback(DisclosureProgressEvent(stage="paused", processed_count=len(results), total_count=total_count))
    break
```

Keep cancellation check first if both stop and pause are requested, so stop wins.

In `RealReportService.run_disclosure_day_job`, pass:

```python
should_pause=lambda: self.job_store.should_pause(job_id),
```

After analysis returns, before cancel handling, add:

```python
if self.job_store.should_pause(job_id):
    return self.job_store.mark_paused(job_id, bundle)
```

- [ ] **Step 6: Add real service pause/resume methods**

In `copilot/api/real_app.py`, add:

```python
def pause_disclosure_day_job(self, job_id, owner_id=None):
    return self.job_store.request_pause(job_id, owner_id=owner_id)

def resume_disclosure_day_job(self, job_id, owner_id=None):
    job = self.job_store.request_resume(job_id, owner_id=owner_id)
    return job
```

Resume execution will be triggered by creating a new resume job from the paused job in the frontend/API, not by restarting the same background task. This keeps the existing `resume_from_job_id` mechanism as the single resume path.

---

### Task 4: Add pause/resume API routes

**Files:**
- Modify: `copilot/api/app.py`
- Modify: `tests/test_api_disclosure_jobs.py`

- [ ] **Step 1: Write failing API route tests**

In `FakeJobService`, add lists:

```python
self.paused_jobs = []
self.pause_owner_ids = []
self.resumed_jobs = []
self.resume_owner_ids = []
```

Add methods:

```python
def _job_payload(job_id, status="running", current_stage="queued"):
    return {
        "job_id": job_id,
        "date": "20250825",
        "status": status,
        "processed_count": 1,
        "total_count": 2,
        "ok_count": 1,
        "data_problem_count": 0,
        "current_ts_code": "603026.SH",
        "current_name": "石大胜华",
        "current_period": "20250630",
        "current_stage": current_stage,
        "elapsed_seconds": 1.2,
        "logs": [],
        "bundle": None,
    }

def pause_disclosure_day_job(self, job_id, owner_id=None):
    self.pause_owner_ids.append(owner_id)
    self.paused_jobs.append(job_id)
    return _job_payload(job_id, current_stage="pause_requested")

def resume_disclosure_day_job(self, job_id, owner_id=None):
    self.resume_owner_ids.append(owner_id)
    self.resumed_jobs.append(job_id)
    return _job_payload(job_id, current_stage="resume_requested")
```

Add test:

```python
def test_disclosure_day_job_routes_pause_and_resume_with_owner_header():
    service = FakeJobService()
    client = TestClient(create_app(service))
    headers = {"X-TradeEye-Owner": "alice"}

    paused = client.post("/api/disclosure-day/jobs/job-1/pause", headers=headers)
    resumed = client.post("/api/disclosure-day/jobs/job-1/resume", headers=headers)

    assert paused.status_code == 200
    assert paused.json()["current_stage"] == "pause_requested"
    assert resumed.status_code == 200
    assert resumed.json()["current_stage"] == "resume_requested"
    assert service.paused_jobs == ["job-1"]
    assert service.resumed_jobs == ["job-1"]
    assert service.pause_owner_ids == ["alice"]
    assert service.resume_owner_ids == ["alice"]
```

- [ ] **Step 2: Run API route RED**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp tests/test_api_disclosure_jobs.py::test_disclosure_day_job_routes_pause_and_resume_with_owner_header -q
```

Expected: FAIL because routes are missing.

- [ ] **Step 3: Add API routes**

In `copilot/api/app.py`, after cancel route:

```python
@app.post("/api/disclosure-day/jobs/{job_id}/pause", response_model=DisclosureJobStatus)
def pause_disclosure_day_job(job_id: str, x_tradeeye_owner: str | None = Header(default=None)):
    return report_service.pause_disclosure_day_job(job_id, owner_id=x_tradeeye_owner)

@app.post("/api/disclosure-day/jobs/{job_id}/resume", response_model=DisclosureJobStatus)
def resume_disclosure_day_job(job_id: str, x_tradeeye_owner: str | None = Header(default=None)):
    return report_service.resume_disclosure_day_job(job_id, owner_id=x_tradeeye_owner)
```

- [ ] **Step 4: Verify API route tests pass**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp tests/test_api_disclosure_jobs.py::test_disclosure_day_job_routes_pause_and_resume_with_owner_header -q
```

Expected: PASS.

---

### Task 5: Add frontend scan pause/continue/stop controls

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `tests/test_frontend_productization.py`

- [ ] **Step 1: Write failing frontend productization tests**

In `tests/test_frontend_productization.py`, replace the old single-button assumptions in `test_disclosure_scan_uses_cancellable_job_polling` with:

```python
assert 'id="start-disclosure-scan"' in html
assert 'id="pause-disclosure-scan"' in html
assert 'id="resume-disclosure-scan"' in html
assert 'id="stop-disclosure-scan"' in html
assert 'function setScanControls(next)' in js
assert 'pauseDisclosureDayJob(jobId)' in js
assert 'resumeDisclosureDayJob(jobId)' in js
assert 'pauseDisclosureScan' in js
assert 'resumePausedDisclosureScan' in js
assert 'stopDisclosureScan' in js
assert '"/api/disclosure-day/jobs/"' in js
assert '"/pause"' in js
assert '"/resume"' in js
```

Remove assertion that `stop-disclosure-scan` is absent.

- [ ] **Step 2: Run frontend RED**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp tests/test_frontend_productization.py::test_disclosure_scan_uses_cancellable_job_polling -q
```

Expected: FAIL because pause/resume controls do not exist.

- [ ] **Step 3: Update HTML controls**

In `web/index.html`, near the existing start scan button, keep `id="start-disclosure-scan"` and add:

```html
<button id="pause-disclosure-scan" class="outlined" hidden>暂停扫描</button>
<button id="resume-disclosure-scan" class="outlined" hidden>继续扫描</button>
<button id="stop-disclosure-scan" class="outlined" hidden>停止扫描</button>
```

- [ ] **Step 4: Add API wrappers**

In `web/app.js` API object, add:

```js
pauseDisclosureDayJob: (jobId) => apiFetch(`/api/disclosure-day/jobs/${jobId}/pause`, { method: "POST" }),
resumeDisclosureDayJob: (jobId) => apiFetch(`/api/disclosure-day/jobs/${jobId}/resume`, { method: "POST" }),
```

- [ ] **Step 5: Replace scan state UI function**

Replace `setScanState(next)` with `setScanControls(next)`:

```js
const pauseScanButton = el("pause-disclosure-scan");
const resumeScanButton = el("resume-disclosure-scan");
const stopScanButton = el("stop-disclosure-scan");

function setScanControls(next) {
  scanButton.dataset.state = next;
  const running = next === "scanning";
  const paused = next === "paused";
  const stopping = next === "cancelling";
  scanButton.hidden = running || paused || stopping;
  pauseScanButton.hidden = !running;
  resumeScanButton.hidden = !paused;
  stopScanButton.hidden = !(running || paused || stopping);
  pauseScanButton.disabled = stopping;
  resumeScanButton.disabled = stopping;
  stopScanButton.disabled = stopping;
  stopScanButton.textContent = stopping ? "停止中…" : "停止扫描";
}
```

Replace all `setScanState(...)` calls with `setScanControls(...)`.

- [ ] **Step 6: Add pause/resume handlers**

In `web/app.js`, add:

```js
async function pauseDisclosureScan() {
  if (!state.activeJobId) return;
  const job = await api.pauseDisclosureDayJob(state.activeJobId);
  renderJobProgress(job);
}

async function resumePausedDisclosureScan() {
  if (!state.activeJobId) return;
  const pausedJob = await api.resumeDisclosureDayJob(state.activeJobId);
  await resumeDisclosureJob(pausedJob);
}
```

In `pollDisclosureJob`, handle paused:

```js
if (job.status === "paused") {
  clearInterval(state.jobPollTimer);
  state.jobPollTimer = null;
  setScanControls("paused");
  renderJobProgress(job);
  notify("扫描已暂停");
  return;
}
```

Bind buttons:

```js
pauseScanButton.addEventListener("click", () => pauseDisclosureScan().catch((error) => notify(error.message, true)));
resumeScanButton.addEventListener("click", () => resumePausedDisclosureScan().catch((error) => notify(error.message, true)));
stopScanButton.addEventListener("click", () => stopDisclosureScan().catch((error) => { setStatus({ error: error.message }); notify(error.message, true); }));
```

- [ ] **Step 7: Verify frontend productization test passes**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp tests/test_frontend_productization.py::test_disclosure_scan_uses_cancellable_job_polling -q
```

Expected: PASS.

---

### Task 6: Final verification

**Files:**
- Inspect all modified files.

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp tests/test_disclosure_analysis_bundle.py tests/test_disclosure_jobs.py tests/test_real_app_jobs.py tests/test_api_disclosure_jobs.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend tests**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp tests/test_frontend_productization.py -q
npm test
node --check web/app.js && node --check web/agent-chat.js && node --check web/agent-panel.js
```

Expected: PASS.

- [ ] **Step 3: Run full pytest**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp -q
```

Expected: PASS.

- [ ] **Step 4: Inspect diff**

Run:

```bash
git status --short && git diff --stat
```

Expected: existing release-completion changes plus this scan-card/pause-control work. Do not commit or push unless the user asks.
