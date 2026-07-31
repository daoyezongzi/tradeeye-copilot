# Submission Checklist

## Code

- [ ] `pytest -q` passes
- [ ] `.env` is not tracked
- [ ] No real API key, token, or webhook URL appears in committed files
- [ ] `uvicorn copilot.api.real_app:app --reload` starts locally
- [ ] Evidence drill-down works in the dashboard

## Benchmark

- [ ] `python eval/run_backtest.py` writes `artifacts/benchmark.json`
- [ ] Manual review CSV is filled for all benchmark findings
- [ ] README benchmark numbers match the generated artifact
- [ ] PPT benchmark page uses the same numbers

## Ascend

- [ ] `ASCEND_API_KEY` configured locally
- [ ] `llm.base_url` points to Ascend MaaS / ModelArts-compatible endpoint
- [ ] One test request succeeds before recording
- [ ] LLM timeout does not block report card generation

## Demo

- [ ] 5-minute script rehearsed
- [ ] Company card demo prepared
- [ ] Evidence popup demo prepared
- [ ] Quarterly review page prepared
- [ ] Feishu webhook optional demo prepared

## Submission

- [ ] README includes architecture, setup, screenshots, benchmark, and compliance boundary
- [ ] AtomGit repository is public or accessible as required
- [ ] Demo video link works
- [ ] Final upload completed before 2026-08-08 24:00
