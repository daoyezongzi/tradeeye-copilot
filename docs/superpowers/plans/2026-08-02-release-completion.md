# Release Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `main` to a product-ready state where the user can immediately start manual testing: synced release docs, no stale researcher-review artifacts, and small UX gaps closed.

**Architecture:** Keep backend contracts unchanged. Make frontend changes in the existing vanilla JS modules and static HTML/CSS, with pure helper tests where possible and Python productization tests for static UI invariants. Documentation changes reflect verified repository state without claiming real-environment checks that have not been run.

**Tech Stack:** FastAPI, Python 3.11+, pytest, vanilla JavaScript ES modules, Node `node:test`, static HTML/CSS, SQLite-backed services.

---

## File Structure

- Modify `copilot/config.py`: read generic `LLM_API_KEY` for OpenAI-compatible providers.
- Modify `tests/test_config.py`: verify `LLM_API_KEY` drives `settings.llm.api_key`.
- Modify `.env.example`: expose `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` instead of Ascend-specific key naming.
- Modify `README.md` and `README.en.md`: document generic OpenAI-compatible LLM configuration.
- Modify `docs/submission-checklist.md`: use `LLM_API_KEY` in launch checks.
- Modify `docs/development-log.md`: add current-status note at the top; do not rewrite historical records.
- Delete `artifacts/ui-preview/review-light.png`, `artifacts/ui-preview/review-dark.png`, `artifacts/ui-preview/05-review-light.png`, `artifacts/ui-preview/d7-review.png`: old researcher review screenshots only.
- Modify `web/agent-panel.js`: add reference formatting and disabled guidance helper; keep Agent contract unchanged.
- Modify `web/agent-panel.test.mjs`: cover reference formatter and disabled guidance text.
- Modify `web/app.js`: render Agent references as readable cards, populate company-name datalist, resolve company name/code before navigating, and expose Agent-not-ready guidance.
- Modify `web/index.html`: add datalist for company candidates and update single-ticket label/help text.
- Modify `web/styles.css`: add small evidence metadata styles and company input help styling consistent with existing surfaces.
- Modify `tests/test_frontend_productization.py`: assert company-name input and no researcher review exposure remain true.

### Task 0: Generalize OpenAI-compatible LLM configuration

**Files:**
- Modify: `copilot/config.py`
- Modify: `tests/test_config.py`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `docs/submission-checklist.md`

- [ ] **Step 1: Write failing config tests**

In `tests/test_config.py`, update LLM env tests to use `LLM_API_KEY` instead of `ASCEND_API_KEY`:

```python
def test_load_settings_reads_llm_api_key_from_generic_env(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "database:\n  path: tmp/app.sqlite\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_API_KEY", "generic-key")
    monkeypatch.delenv("ASCEND_API_KEY", raising=False)

    settings = load_settings(config_path, env_path=tmp_path / "missing.env")

    assert settings.llm.api_key == "generic-key"
```

Also change existing LLM tests so `monkeypatch.setenv("ASCEND_API_KEY", ...)` becomes `monkeypatch.setenv("LLM_API_KEY", ...)`, and `monkeypatch.delenv("ASCEND_API_KEY", ...)` becomes `monkeypatch.delenv("LLM_API_KEY", ...)`.

- [ ] **Step 2: Run config tests to verify RED**

Run:

```bash
python -m pytest tests/test_config.py::test_load_settings_reads_llm_api_key_from_generic_env tests/test_config.py::test_load_settings_reads_llm_from_env -q
```

Expected: FAIL because `copilot/config.py` still reads `ASCEND_API_KEY`.

- [ ] **Step 3: Implement generic LLM API key loading**

In `copilot/config.py`, replace:

```python
data.setdefault("llm", {})["api_key"] = os.getenv("ASCEND_API_KEY")
```

with:

```python
data.setdefault("llm", {})["api_key"] = os.getenv("LLM_API_KEY")
```

Do not keep an `ASCEND_API_KEY` fallback; release documentation should use one authoritative generic name.

- [ ] **Step 4: Update example env and docs naming**

Update `.env.example` to:

```env
TUSHARE_TOKEN=
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
FEISHU_WEBHOOK=
AUTOMATION_TRIGGER_TOKEN=
FEISHU_VERIFICATION_TOKEN=
PUBLIC_BASE_URL=
```

In `README.md` and `README.en.md`, replace Ascend-specific API-key naming with `LLM_API_KEY`. Keep wording that the endpoint is OpenAI-compatible and may point to Ascend, DeepSeek, or another compatible provider.

In `docs/submission-checklist.md`, use `LLM_API_KEY` for Agent/LLM readiness checks.

- [ ] **Step 5: Verify config tests pass**

Run:

```bash
python -m pytest tests/test_config.py::test_load_settings_reads_llm_api_key_from_generic_env tests/test_config.py::test_load_settings_reads_llm_from_env -q
```

Expected: PASS.

### Task 1: Sync release documentation

**Files:**
- Modify: `README.en.md`
- Modify: `docs/submission-checklist.md`
- Modify: `docs/development-log.md`

- [ ] **Step 1: Replace stale English README review/Agent wording**

Update `README.en.md` so these sections match `README.md`:

```markdown
- **Quarterly recap** of coverage, disclosed count, hit count, and rule distribution
```

```markdown
| Chatbot prompts block non-technical users | **Zero-prompt main path + optional Agent**: the Web workbench supports one-click scans and in-place refresh; the Agent floating layer answers questions about the current card and asks for analyst confirmation before refetch/rescan actions |
```

```markdown
### Research workbench (Web)
- **Daily briefing** — header, lead-in, severity distribution bar (red / yellow / OK / data issues)
- **Company research cards** — name-first display, code and report period as auxiliary identifiers; expandable with the highest-severity card expanded by default
- **Single-company analysis** — enter a stock code or company name and report period to generate one company card
- **Agent floating layer** — bottom-right robot entry, docked right by default, draggable/snap-back; answers questions about the current card and suggests refetch/rescan actions only after confirmation
- **Evidence drill-down popup** — per finding, showing the original `Evidence` payload
- **Quarterly recap** — coverage pool, disclosed count, hit count, and rule distribution; human-review metrics stay in backend evaluation APIs, not in the analyst main path
- **Diagnostics & developer tools** — collapsed fold with scan status, jobs, automation integration, and notification logs
- **Export** — JSON / CSV menus; deep links `#/day/{date}`, `#/company/{ts_code}/{period}`
```

Update API rows for reviews to mark internal evaluation:

```markdown
| `GET` | `/api/reviews/labels.csv` | Internal evaluation: review labels as CSV |
| `GET` | `/api/reviews/metrics` | Internal evaluation: precision breakdowns |
| `POST` / `GET` | `/api/reviews/labels` | Internal evaluation: upsert / list review labels |
| `DELETE` | `/api/reviews/labels/{ts_code}/{period}/{rule_id}` | Internal evaluation: delete a label |
```

Update Agent section:

```markdown
The Agent is integrated into the analyst frontend as a floating Q&A layer rather than a primary navigation page. The contract (spec: [2026-08-01 agent fact contract design](docs/superpowers/specs/2026-08-01-agent-fact-contract-design.md), [2026-08-02 Agent frontend design](docs/superpowers/specs/2026-08-02-agent-frontend-design.md)):
```

Add bullets:

```markdown
- The Agent suggests only `refetch_company` / `rescan_disclosure_day`; the frontend executes existing analysis APIs only after confirmation, and the Agent itself writes no business data
```

Update testing block:

```bash
python -m pytest --basetemp=.pytest_tmp -q
npm test
node --check web/app.js && node --check web/agent-chat.js && node --check web/agent-panel.js
```

Update test scale text to `236 pytest` and `15 Node frontend tests`.

- [ ] **Step 2: Rewrite submission checklist truthfully**

Replace `docs/submission-checklist.md` with:

```markdown
# Submission Checklist

## Repository state

- [x] Chinese README describes the current product path: disclosure-day analysis, single-company analysis, Agent floating layer, evidence drill-down, Feishu preview/send, and internal-only review APIs.
- [x] English README is synced with the current product path.
- [x] Researcher frontend no longer exposes review navigation, review table, CSV export, review label chips, or precision metrics.
- [x] Old researcher-review screenshots have been removed from `artifacts/ui-preview/`.
- [ ] `python -m pytest --basetemp=.pytest_tmp -q` passes in the local environment.
- [ ] `npm test` passes in the local environment.
- [ ] `node --check web/app.js && node --check web/agent-chat.js && node --check web/agent-panel.js` passes in the local environment.

## Secrets and configuration

- [x] `.env` is not tracked by git.
- [ ] No real API key, token, or webhook URL appears in committed files after final secret scan.
- [ ] `TUSHARE_TOKEN` is configured locally.
- [ ] `LLM_API_KEY` is configured locally if Agent/LLM tone demos are needed.
- [ ] `FEISHU_WEBHOOK` is configured locally if Feishu send demo is needed.
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
```

- [ ] **Step 3: Add development-log current-status note**

At the top of `docs/development-log.md`, add a short note under the title or before the latest dated entry:

```markdown
> Current status note: researcher-facing review pages, review label chips, review CSV export, and precision displays were removed from the Web workbench on 2026-08-02. Older entries that mention the review frontend are historical; current review/eval capability remains backend/internal only.
```

- [ ] **Step 4: Verify documentation markers**

Run:

```bash
python -m pytest tests/test_frontend_productization.py::test_researcher_frontend_does_not_expose_review_ui_or_calls -q
```

Expected: PASS.

---

### Task 2: Remove stale review screenshots

**Files:**
- Delete: `artifacts/ui-preview/review-light.png`
- Delete: `artifacts/ui-preview/review-dark.png`
- Delete: `artifacts/ui-preview/05-review-light.png`
- Delete: `artifacts/ui-preview/d7-review.png`

- [ ] **Step 1: Confirm exact stale screenshot set**

Run:

```bash
git status --short && git ls-files "artifacts/ui-preview/*review*.png"
```

Expected listed tracked files include the four review page screenshots and may also include Feishu preview screenshots. Only delete the four exact review page files.

- [ ] **Step 2: Delete only stale review page screenshots**

Run:

```bash
rm "artifacts/ui-preview/review-light.png" "artifacts/ui-preview/review-dark.png" "artifacts/ui-preview/05-review-light.png" "artifacts/ui-preview/d7-review.png"
```

- [ ] **Step 3: Verify Feishu preview screenshots remain**

Run:

```bash
git ls-files "artifacts/ui-preview/*feishu-preview*.png"
```

Expected: Feishu preview screenshots are still tracked.

---

### Task 3: Improve Agent reference and readiness UX

**Files:**
- Modify: `web/agent-panel.js`
- Modify: `web/agent-panel.test.mjs`
- Modify: `web/app.js`
- Modify: `web/styles.css`

- [ ] **Step 1: Write failing Agent panel helper tests**

Add imports to `web/agent-panel.test.mjs`:

```js
  agentDisabledGuidance,
  formatAgentReference,
```

Add tests:

```js
test("formatAgentReference renders readable fields and raw JSON", () => {
  const formatted = formatAgentReference({
    rule_id: "cashflow_quality",
    source: "cashflow",
    field: "n_cashflow_act",
    period: "20250630",
    value: 12.34,
    evidence_id: "ev-1",
  });

  assert.deepEqual(formatted.rows, [
    { label: "类型或规则", value: "cashflow_quality" },
    { label: "来源", value: "cashflow" },
    { label: "字段", value: "n_cashflow_act" },
    { label: "期间", value: "20250630" },
    { label: "数值", value: "12.34" },
  ]);
  assert.equal(formatted.raw.includes('"evidence_id": "ev-1"'), true);
});

test("formatAgentReference uses missing marker without fabricating values", () => {
  const formatted = formatAgentReference({ title: "事实引用" });

  assert.deepEqual(formatted.rows, [
    { label: "类型或规则", value: "事实引用" },
    { label: "来源", value: "未提供" },
    { label: "字段", value: "未提供" },
    { label: "期间", value: "未提供" },
    { label: "数值", value: "未提供" },
  ]);
});

test("agentDisabledGuidance explains LLM configuration", () => {
  assert.equal(
    agentDisabledGuidance,
    "Agent 问答需要配置外部 LLM API 后启用；当前仍可查看公司卡、依据弹窗和确定性 finding。",
  );
});
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
npm test -- web/agent-panel.test.mjs
```

Expected: FAIL because `formatAgentReference` and `agentDisabledGuidance` are not exported.

- [ ] **Step 3: Implement Agent panel helpers**

In `web/agent-panel.js`, after `formatAgentCard`, add:

```js
export const agentDisabledGuidance = "Agent 问答需要配置外部 LLM API 后启用；当前仍可查看公司卡、依据弹窗和确定性 finding。";

function valueOrMissing(value) {
  if (value === null || value === undefined || value === "") return "未提供";
  return String(value);
}

export function formatAgentReference(reference = {}) {
  return {
    rows: [
      { label: "类型或规则", value: valueOrMissing(reference.rule_id || reference.kind || reference.title) },
      { label: "来源", value: valueOrMissing(reference.source) },
      { label: "字段", value: valueOrMissing(reference.field) },
      { label: "期间", value: valueOrMissing(reference.period) },
      { label: "数值", value: valueOrMissing(reference.value) },
    ],
    raw: JSON.stringify(reference, null, 2),
  };
}
```

- [ ] **Step 4: Verify helper tests pass**

Run:

```bash
npm test -- web/agent-panel.test.mjs
```

Expected: PASS for `web/agent-panel.test.mjs`.

- [ ] **Step 5: Update app reference rendering and disabled guidance**

In `web/app.js`, replace `showAgentReference` with:

```js
async function showAgentReference(reference) {
  const formatter = window.TradeEyeAgentPanel?.formatAgentReference;
  if (!formatter) {
    evidenceContent.textContent = JSON.stringify(reference, null, 2);
    evidenceDialog.showModal();
    return;
  }
  const formatted = formatter(reference);
  const wrap = document.createElement("div");
  wrap.className = "evidence-card";
  const grid = document.createElement("dl");
  grid.className = "evidence-card__grid";
  for (const row of formatted.rows) {
    const item = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = row.label;
    const value = document.createElement("dd");
    value.textContent = row.value;
    item.append(term, value);
    grid.append(item);
  }
  const raw = document.createElement("pre");
  raw.className = "preview-text evidence-card__raw";
  raw.textContent = formatted.raw;
  wrap.append(grid, raw);
  evidenceContent.replaceChildren(wrap);
  evidenceDialog.showModal();
}
```

In `initAgentPanel`, replace:

```js
panel.setDisabled(true, "Agent 未配置 LLM");
```

with:

```js
panel.setDisabled(true, window.TradeEyeAgentPanel.agentDisabledGuidance);
```

- [ ] **Step 6: Add evidence card CSS**

Append to `web/styles.css` near dialog styles:

```css
.evidence-card {
  display: grid;
  gap: var(--space-3);
}

.evidence-card__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--space-2);
  margin: 0;
}

.evidence-card__grid > div {
  padding: var(--space-2);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--radius-sm);
  background: var(--md-sys-color-surface-container-low);
}

.evidence-card dt {
  margin: 0 0 var(--space-1);
  color: var(--md-sys-color-on-surface-muted);
  font-size: 12px;
}

.evidence-card dd {
  margin: 0;
  font-family: var(--mono);
  overflow-wrap: anywhere;
}

.evidence-card__raw {
  margin: 0;
}
```

- [ ] **Step 7: Verify JS syntax**

Run:

```bash
node --check web/app.js && node --check web/agent-panel.js
```

Expected: both syntax checks pass.

---

### Task 4: Add company-name single-ticket input

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Modify: `tests/test_frontend_productization.py`

- [ ] **Step 1: Write failing Python productization test**

Add this test to `tests/test_frontend_productization.py` after `test_company_display_is_name_first_with_code_subtitle`:

```python
def test_single_company_input_supports_company_name_candidates(html, js):
    assert 'list="company-ts-code-options"' in html
    assert 'id="company-ts-code-options"' in html
    assert 'function renderCompanyOptions()' in js
    assert 'function resolveCompanyInput(value)' in js
    assert 'renderCompanyOptions();' in js
    assert 'const resolved = resolveCompanyInput(el("company-ts-code").value);' in js
    assert 'notify("请输入覆盖池内的股票代码或公司名称", true);' in js
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
python -m pytest tests/test_frontend_productization.py::test_single_company_input_supports_company_name_candidates -q
```

Expected: FAIL because datalist and resolver are not implemented.

- [ ] **Step 3: Update company input HTML**

In `web/index.html`, replace the single-ticket input block with:

```html
<div class="field">
  <label for="company-ts-code">股票代码 / 公司名称</label>
  <input id="company-ts-code" type="text" value="603026.SH" placeholder="603026.SH 或 石大胜华" list="company-ts-code-options" />
  <datalist id="company-ts-code-options"></datalist>
  <small class="field__hint">支持覆盖池公司名候选，提交时仍使用股票代码</small>
</div>
```

- [ ] **Step 4: Add company resolver helpers**

In `web/app.js`, after `companySubtitle`, add:

```js
function renderCompanyOptions() {
  const options = el("company-ts-code-options");
  if (!options) return;
  const entries = Object.entries(state.meta.company_names || {}).sort((a, b) => a[1].localeCompare(b[1], "zh-Hans-CN"));
  options.replaceChildren(
    ...entries.map(([tsCode, name]) => {
      const option = document.createElement("option");
      option.value = name;
      option.label = tsCode;
      return option;
    }),
    ...entries.map(([tsCode, name]) => {
      const option = document.createElement("option");
      option.value = tsCode;
      option.label = name;
      return option;
    }),
  );
}

function resolveCompanyInput(value) {
  const normalized = String(value || "").trim();
  if (!normalized) return "";
  const upper = normalized.toUpperCase();
  if (/^\d{6}\.(SZ|SH|BJ)$/.test(upper)) return upper;
  for (const [tsCode, name] of Object.entries(state.meta.company_names || {})) {
    if (name === normalized) return tsCode;
  }
  return "";
}
```

In `loadMeta`, after assigning `state.meta = meta`, add:

```js
renderCompanyOptions();
```

Replace analyze-company click handler with:

```js
el("analyze-company").addEventListener("click", () => {
  const resolved = resolveCompanyInput(el("company-ts-code").value);
  if (!resolved) {
    notify("请输入覆盖池内的股票代码或公司名称", true);
    return;
  }
  const period = el("company-period").value;
  el("company-ts-code").value = resolved;
  navigate(`#/company/${resolved}/${period}`);
});
```

- [ ] **Step 5: Add small field hint CSS**

Append near field styles in `web/styles.css`:

```css
.field__hint {
  display: block;
  margin-top: var(--space-1);
  color: var(--md-sys-color-on-surface-muted);
  font-size: 12px;
}
```

- [ ] **Step 6: Verify company input test passes**

Run:

```bash
python -m pytest tests/test_frontend_productization.py::test_single_company_input_supports_company_name_candidates -q
```

Expected: PASS.

---

### Task 5: Final self-review and light verification

**Files:**
- Inspect: `README.md`, `README.en.md`, `docs/submission-checklist.md`, `docs/development-log.md`, `web/index.html`, `web/app.js`, `web/agent-panel.js`, `web/styles.css`, `tests/test_frontend_productization.py`

- [ ] **Step 1: Run frontend and focused productization tests**

Run:

```bash
npm test
python -m pytest tests/test_frontend_productization.py -q
```

Expected: Node frontend tests pass and productization tests pass.

- [ ] **Step 2: Run JS syntax checks**

Run:

```bash
node --check web/app.js && node --check web/agent-chat.js && node --check web/agent-panel.js
```

Expected: syntax checks pass.

- [ ] **Step 3: Check stale review markers**

Run:

```bash
git grep -n "Review queue\|human-review precision\|Agent question bar is reserved\|Quarterly review page prepared" -- README.en.md docs/submission-checklist.md web/index.html web/app.js
```

Expected: no matches.

- [ ] **Step 4: Check changed files**

Run:

```bash
git status --short && git diff --stat
```

Expected: changes are limited to release docs, planned frontend files/tests, release-completion spec/plan, and the four deleted old review screenshots.

- [ ] **Step 5: Report verified state**

Final report must state the exact commands run and their pass/fail status. Do not claim full Python suite passes unless `python -m pytest --basetemp=.pytest_tmp -q` was actually run in this task.
