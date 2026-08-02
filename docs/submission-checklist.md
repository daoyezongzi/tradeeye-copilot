# Submission Checklist

## Repository state

- [x] Chinese README describes the current product path: disclosure-day analysis, single-company analysis, Agent floating layer, evidence drill-down, Feishu preview/send, and internal-only review APIs.
- [x] English README is synced with the current product path.
- [x] Researcher frontend no longer exposes review navigation, review table, CSV export, review label chips, or precision metrics.
- [x] Old researcher-review screenshots have been removed from `artifacts/ui-preview/`.
- [x] `python -m pytest --basetemp=.pytest_tmp -q` passes in the local environment.
- [x] `npm test` passes in the local environment.
- [x] `node --check web/app.js && node --check web/agent-chat.js && node --check web/agent-panel.js` passes in the local environment.

## Secrets and configuration

- [x] `.env` is not tracked by git.
- [ ] No real API key, token, or webhook URL appears in committed files after final secret scan.
- [ ] `TUSHARE_TOKEN` is configured locally.
- [ ] `LLM_API_KEY` is configured locally if Agent/LLM tone checks are needed.
- [ ] `LLM_BASE_URL` points to the selected OpenAI-compatible endpoint if the default is not used.
- [ ] `LLM_MODEL` matches the selected OpenAI-compatible model if the default is not used.
- [ ] `FEISHU_WEBHOOK` is configured locally if Feishu send testing is needed.
- [ ] `AUTOMATION_TRIGGER_TOKEN` is configured for cron endpoint testing if deployed automation is needed.

## Product smoke checks

- [ ] `uvicorn copilot.api.real_app:app --reload` starts locally.
- [ ] Disclosure-day scan loads cards for a selected date.
- [ ] Company-name or stock-code single-ticket input opens the correct company card.
- [ ] Evidence drill-down opens a readable evidence dialog.
- [ ] Agent button is visible; if LLM is not configured, the panel shows configuration guidance.
- [ ] Feishu preview renders text; send is enabled only when webhook config allows it.

## Benchmark and submission materials

- [ ] `python eval/run_backtest.py` writes `artifacts/benchmark.json`.
- [ ] README benchmark/test numbers match the generated artifact and latest test run.
- [ ] Demo screenshots or video are prepared outside this product-finalization pass.
- [ ] AtomGit/GitHub repository is public or accessible as required.
- [ ] Final upload completed before 2026-08-08 24:00.
