# Quality Factor Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a first-pass quality-factor layer for company cards and custom comparisons, using status bands instead of pseudo-precise scores.

**Architecture:** Add a small backend factor builder that maps existing deterministic rule results and findings into `QualityFactor` / `QualityOverview`, then expose those fields through existing company cards plus a read-only compare endpoint. Frontend keeps the current card layout, adds a factor-list-first block with a small status radar, and adds a lightweight comparison workspace. Agent panel micro-interactions are scoped to CSS/DOM text only.

**Tech Stack:** Python 3, FastAPI, Pydantic, pytest, vanilla ES modules, Node `node:test`, CSS/SVG.

---

## File Structure

- Create `copilot/quality/factors.py`: factor IDs, status enum, observations, overview, and builder functions.
- Modify `copilot/report/builder.py`: add quality fields to `CompanyCard` and populate them in `build_company_card`.
- Modify `copilot/api/app.py`: add compare request/response models, protocol method, and `POST /api/quality-factors/compare`.
- Modify `copilot/api/real_app.py`: implement compare using cached/persisted cards.
- Create `tests/test_quality_factors.py`: backend mapping and overview tests.
- Create/modify `tests/test_api_quality_factors.py`: compare route tests.
- Modify `web/app.js`: add API method, factor rendering, small radar rendering, comparison workspace rendering.
- Modify `web/styles.css`: add factor list, status radar, compare matrix, and Agent thinking/placeholder styles.
- Modify/add `web/*.test.mjs`: test pure frontend mapping/render helpers where existing test style allows.
- Update this plan and the spec only if implementation reveals a contradiction.

## claudedesign Note

The user requested `claudedesign` for frontend design. The current harness skill list does not include a `claudedesign` skill, and invoking `Skill(skill="claudedesign")` returned `Unknown skill`. Frontend design therefore follows the accepted visual companion mockup (`B · 因子列表优先`) and existing TradeEye tokens/styles instead of that unavailable skill.

### Task 1: Backend Quality Factor Contract

**Files:**
- Create: `copilot/quality/factors.py`
- Create: `copilot/quality/__init__.py`
- Modify: `copilot/report/builder.py`
- Test: `tests/test_quality_factors.py`

- [ ] **Step 1: Write failing tests**

```python
from copilot.models import Context, Evidence, Finding, RuleResult, RuleResultStatus, Severity
from copilot.quality.factors import FactorStatus, build_quality_factors, build_quality_overview


def _finding(rule_id: str, severity: Severity) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        title=rule_id,
        detail="detail",
        evidence=[Evidence(source="tushare.income", field="revenue", period="20250630", value=100.0)],
        score=1.0,
    )


def _rule_result(rule_id: str, status: RuleResultStatus) -> RuleResult:
    return RuleResult(rule_id=rule_id, status=status, required_fact_ids=[])


def test_quality_factors_map_rule_statuses(make_snapshot):
    ctx = Context(ts_code="000001.SZ", current=make_snapshot())
    factors = build_quality_factors(
        ctx,
        rule_results=[
            _rule_result("receivable_revenue_divergence", RuleResultStatus.MISS),
            _rule_result("cashflow_quality", RuleResultStatus.HIT),
            _rule_result("net_profit_revenue_direction", RuleResultStatus.HIT),
            _rule_result("gross_margin_change", RuleResultStatus.NOT_EVALUATED),
        ],
        findings=[
            _finding("cashflow_quality", Severity.YELLOW),
            _finding("net_profit_revenue_direction", Severity.RED),
        ],
    )
    by_id = {factor.factor_id: factor for factor in factors}
    assert by_id["revenue_realization_quality"].status == FactorStatus.NORMAL
    assert by_id["cashflow_quality"].status == FactorStatus.WATCH
    assert by_id["performance_direction_consistency"].status == FactorStatus.ANOMALY
    assert by_id["profitability_stability"].status == FactorStatus.NOT_EVALUATED


def test_quality_overview_counts_and_status(make_snapshot):
    ctx = Context(ts_code="000001.SZ", current=make_snapshot())
    factors = build_quality_factors(
        ctx,
        rule_results=[
            _rule_result("receivable_revenue_divergence", RuleResultStatus.MISS),
            _rule_result("cashflow_quality", RuleResultStatus.HIT),
            _rule_result("net_profit_revenue_direction", RuleResultStatus.HIT),
        ],
        findings=[
            _finding("cashflow_quality", Severity.YELLOW),
            _finding("net_profit_revenue_direction", Severity.RED),
        ],
    )
    overview = build_quality_overview(factors)
    assert overview.status == FactorStatus.ANOMALY
    assert overview.anomaly_count == 1
    assert overview.watch_count == 1
    assert "异常 1 项" in overview.summary
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_quality_factors.py -v`
Expected: FAIL because `copilot.quality.factors` does not exist.

- [ ] **Step 3: Implement minimal factor builder**

Create `copilot/quality/factors.py` with Pydantic models, `FACTOR_SPECS`, `build_quality_factors`, and `build_quality_overview`. Use existing `Finding.severity` when rule status is HIT; use `MISS -> NORMAL`; use `NOT_EVALUATED/BLOCKED -> NOT_EVALUATED`; default missing rule result to `NOT_EVALUATED`.

Modify `CompanyCard` in `copilot/report/builder.py` to include `quality_factors` and `quality_overview`, and populate them in `build_company_card(ctx, findings, rule_results=...)`.

- [ ] **Step 4: Run backend factor tests**

Run: `pytest tests/test_quality_factors.py tests/test_report_builder.py -v`
Expected: PASS.

- [ ] **Step 5: Commit task**

Run:
```bash
git add copilot/quality/__init__.py copilot/quality/factors.py copilot/report/builder.py tests/test_quality_factors.py tests/test_report_builder.py
git commit -m "feat: add quality factor contract"
```

### Task 2: Compare API

**Files:**
- Modify: `copilot/api/app.py`
- Modify: `copilot/api/real_app.py`
- Test: `tests/test_api_quality_factors.py`

- [ ] **Step 1: Write failing API tests**

Create tests that instantiate `create_app` with a fake service exposing `compare_quality_factors(items, mode)` and assert `POST /api/quality-factors/compare` returns `STRICT` for same-period companies and `EXPLORATORY` warning for custom mixed periods.

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_api_quality_factors.py -v`
Expected: FAIL with 404 for missing route.

- [ ] **Step 3: Implement route and real service method**

Add request/response models in `copilot/api/app.py`: `QualityCompareItem`, `QualityFactorCompareRequest`, `QualityFactorCompareResult`. Add protocol method `compare_quality_factors`. Add route `POST /api/quality-factors/compare`.

In `RealReportService.compare_quality_factors`, load each card via `get_company_card`, return item entries for found cards, and mark missing cards with warnings. Compute comparability from mode and period consistency.

- [ ] **Step 4: Run API tests**

Run: `pytest tests/test_api_quality_factors.py tests/test_api_frontend_routes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit task**

Run:
```bash
git add copilot/api/app.py copilot/api/real_app.py tests/test_api_quality_factors.py
git commit -m "feat: expose quality factor comparison API"
```

### Task 3: Frontend Factor Card and Compare View

**Files:**
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Modify/Create: `web/*.test.mjs`

- [ ] **Step 1: Write frontend tests for pure helpers**

Add tests for status labels/classes, overview summary fallback, and comparison warning text using exported or `window`-attached pure helpers.

- [ ] **Step 2: Run tests to verify failure**

Run: `npm test`
Expected: FAIL because helper functions do not exist.

- [ ] **Step 3: Implement card factor rendering**

In `web/app.js`, add `QUALITY_STATUS_META`, `qualityStatusKey`, `renderQualityOverview`, `renderQualityFactor`, and `renderQualityRadar`. In `renderCard`, insert the factor block after `renderFactLine(card.fact_line)` only when `card.quality_factors?.length` exists. Do not show numeric scores.

- [ ] **Step 4: Implement compare API method and workspace surface**

Add `api.compareQualityFactors(items, mode)`. Keep first UI increment small: add a comparison block under the single-company detail when a card is standalone, with buttons/controls for same-company period comparison only if existing DOM supports it without new large forms; otherwise expose renderer and route wiring without overbuilding.

- [ ] **Step 5: Add CSS**

Add styles for `.quality`, `.quality-factor`, `.quality-radar`, `.quality-compare`, and status chips. Use existing severity colors and neutral tokens.

- [ ] **Step 6: Run frontend tests**

Run: `npm test`
Expected: PASS.

- [ ] **Step 7: Commit task**

Run:
```bash
git add web/app.js web/styles.css web/*.test.mjs
git commit -m "feat: show quality factors in company cards"
```

### Task 4: Agent Micro-Interaction Polish

**Files:**
- Modify: `web/agent-panel.js`
- Modify: `web/styles.css`
- Test: existing Node frontend tests, add helper test only if logic changes.

- [ ] **Step 1: Inspect pending message implementation**

Read `web/agent-panel.js` pending/placeholder methods and existing CSS `.agent-*` selectors.

- [ ] **Step 2: Implement thinking animation text and placeholder font polish**

Use an accessible pending bubble with text “正在思考” plus animated dots. Style textarea placeholder with current sans font, muted color, normal letter spacing, and readable size.

- [ ] **Step 3: Verify frontend tests and syntax**

Run: `npm test`
Expected: PASS.

- [ ] **Step 4: Commit task**

Run:
```bash
git add web/agent-panel.js web/styles.css web/*.test.mjs
git commit -m "fix: polish agent pending and input text"
```

### Task 5: Final Verification and Report

**Files:**
- No planned code changes unless verification reveals issues.

- [ ] **Step 1: Run Python tests**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 2: Run frontend tests**

Run: `npm test`
Expected: PASS.

- [ ] **Step 3: Self-review diff**

Run: `git status --short` and `git diff --stat HEAD~4..HEAD` if commits exist. Check for unintended files, `.superpowers`, generated artifacts, or score/total-score language.

- [ ] **Step 4: Report**

Report changed areas, verification commands, limitations, and next recommended iteration.

---

## Self-Review

- Spec coverage: covered factor statuses, rule mapping, CompanyCard fields, compare endpoint, frontend factor list/radar, not doing 0–100 score, not doing industry ranking, and Agent micro-interaction polish.
- Placeholder scan: no TBD/TODO/later placeholders. The only constrained area is frontend compare UI, deliberately scoped to avoid overbuilding beyond existing DOM.
- Type consistency: `FactorStatus`, `QualityFactor`, `QualityOverview`, `quality_factors`, and `quality_overview` names are consistent across backend and frontend.
