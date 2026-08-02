# Final RSS Reminder and Stock Pool Wrap-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the project with a minimal RSS-to-Feishu reminder path, a hidden manual Feishu UI, and an editable stock pool page used by scans and RSS matching.

**Architecture:** Keep deterministic analysis unchanged. Add a SQLite-backed stock pool overlay initialized from `config.yaml`, expose small pool APIs, and have `RealReportService` derive coverage/company maps from that store. Change RSS polling from "analyze matched announcement" to "detect today's announcements and optionally send a Feishu reminder" without Tushare analysis.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLite, pytest, vanilla HTML/CSS/JS, Node `node:test`/`node --check`.

---

## File Structure

- Create: `copilot/service/stock_pool.py` — SQLite-backed editable stock pool repository.
- Modify: `copilot/api/app.py` — stock pool request/response models and routes; RSS notify route.
- Modify: `copilot/api/real_app.py` — wire stock pool store, use dynamic pool for meta/scans/RSS, add RSS notify method.
- Modify: `copilot/rss/service.py` — RSS poll no longer analyzes; it only classifies matched announcements.
- Modify: `copilot/notify/feishu.py` — render RSS disclosure reminder text/card.
- Modify: `web/index.html` — add Stock Pool nav/view; hide manual Feishu top-bar button.
- Modify: `web/app.js` — stock pool view/API/rendering; RSS button displays reminder result.
- Modify: `tests/test_stock_pool.py`, `tests/test_api_stock_pool.py`, `tests/test_rss_service.py`, `tests/test_notify_feishu.py`, `tests/test_frontend_productization.py`.
- Modify: `docs/development-log.md`, `docs/submission-checklist.md`.

---

### Task 1: Editable stock pool backend

- [ ] Write `tests/test_stock_pool.py` with `test_sqlite_stock_pool_initializes_from_config_and_persists_changes` asserting initial entries, add/update, remove, and reload.
- [ ] Run `python -m pytest --basetemp=.pytest_tmp tests/test_stock_pool.py -q`; expect import failure.
- [ ] Create `copilot/service/stock_pool.py` with `StockPoolItem` and `SQLiteStockPoolStore` (`init_schema`, `list_items`, `upsert_item`, `remove_item`, `coverage_pool`, `company_names`, `company_industries`).
- [ ] Run stock pool tests; expect pass.

### Task 2: Stock pool API and dynamic service wiring

- [ ] Write API tests in `tests/test_api_stock_pool.py` covering `GET /api/stock-pool`, `POST /api/stock-pool`, `DELETE /api/stock-pool/{ts_code}`.
- [ ] Run API tests; expect missing routes.
- [ ] Add `StockPoolItemResponse` and `StockPoolUpsertRequest` to `copilot/api/app.py`; add protocol methods and routes.
- [ ] Wire `RealReportService` to initialize `SQLiteStockPoolStore` from settings and use dynamic pool for `get_meta()`, `start_disclosure_day_job` analysis coverage, and RSS company mapping.
- [ ] Run API tests; expect pass.

### Task 3: RSS only sends reminder, no analysis

- [ ] Update `tests/test_rss_service.py`: matched RSS should not call analyzer; result has `matched_count`, `analyzed_count == 0`, and event status `MATCHED`.
- [ ] Add `tests/test_notify_feishu.py::test_render_rss_disclosure_reminder_text_lists_matched_events`.
- [ ] Run focused tests; expect failure.
- [ ] Change `RssPollService.poll()` to classify/match/de-duplicate only, no `analyze_company` call.
- [ ] Add `render_rss_disclosure_reminder_text(date, events, company_names)` and `render_rss_disclosure_reminder_card(date, events, company_names, base_url=None)`.
- [ ] Add `RealReportService.poll_rss_and_notify_feishu(date=None)` returning `{rss, notify}` style payload and sending text/card only when matched events exist and webhook is configured.
- [ ] Add protected or developer API route only if needed by frontend: `POST /api/rss/poll/notify`.
- [ ] Run RSS/notify/API focused tests; expect pass.

### Task 4: Frontend stock pool page and hidden Feishu manual UI

- [ ] Update `tests/test_frontend_productization.py`: require `tab-stock-pool`, `view-stock-pool`, stock pool API wrappers/render functions; require top-bar `preview-feishu` hidden.
- [ ] Run frontend productization test; expect failure.
- [ ] Modify `web/index.html`: add nav button `data-view="stock-pool"`, stock pool section with list/add/remove controls, and `hidden` on `preview-feishu`.
- [ ] Modify `web/app.js`: include `stock-pool` in `VIEWS`, add API wrappers, render/load/add/remove stock pool functions, load pool on boot, update meta/company options after changes, and make RSS button call notify route.
- [ ] Run frontend productization and `node --check`; expect pass.

### Task 5: Docs/log/checklist wrap-up

- [ ] Update `docs/development-log.md` with final state: RSS Feishu reminder only, manual Feishu UI hidden, editable stock pool, scans use dynamic stock pool.
- [ ] Update `docs/submission-checklist.md` to reflect this final scope.
- [ ] Run doc/frontend productization tests that inspect these files if present; otherwise run full verification in Task 6.

### Task 6: Final verification

- [ ] Run `python -m pytest --basetemp=.pytest_tmp -q` and require pass.
- [ ] Run `npm test` and require pass.
- [ ] Run `node --check web/app.js && node --check web/agent-chat.js && node --check web/agent-panel.js` and require pass.
- [ ] Run `git status --short && git diff --stat` and inspect changed files. Do not commit unless explicitly asked.

---

## Self-review

Spec coverage: covers RSS reminder-only behavior, hidden manual Feishu UI, editable stock pool navigation, dynamic scan/RSS pool use, log/checklist updates, and final verification.

Placeholder scan: no TBD/TODO/implement-later placeholders.

Type consistency: stock pool item fields are consistently `ts_code`, `name`, `industry`; RSS reminder functions consistently accept `date`, `events`, `company_names`; frontend route name is consistently `stock-pool`.
