# Navigation Review Frontend Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把研究员前端收口为「披露日研判 / 单票研判」两条主路径，删除复核前端曝光，并把股票展示改成名称优先、代码辅助。

**Architecture:** 只改前端静态页面、前端路由/渲染逻辑和产品化测试；后端 `/api/reviews/*`、eval 数据结构和测试不动。保持现有 TradeEye 视觉风格：继续使用 `.card__name`、`.card__code`、fold、metric、mono 等现有样式，不新增页面级设计体系。

**Tech Stack:** Python pytest (`python -m pytest --basetemp=.pytest_tmp`), native browser JS in `web/app.js`, Node 24 `node --test "web/*.test.mjs"`, static HTML/CSS.

---

## File Structure

- Modify: `tests/test_frontend_productization.py`
  - 更新产品化测试，先锁住导航只剩两个视图、复核 UI/调用从研究员前端消失、名称优先 helper 和 Agent 标题契约。
- Modify: `web/index.html`
  - 删除 `tab-review`、`view-review`、开发者区“复核回写状态”块、复核 CSV 入口。
- Modify: `web/app.js`
  - 删除前端复核 state、API wrapper、渲染/标注/导出函数、事件绑定、boot 调用。
  - 将 `VIEWS` 收口为 `workbench/company`。
  - 增加 `companyTitle()` / `companySubtitle()` 并应用到卡片、OK 名单、数据问题表、CSV、Agent 绑定。
  - `parseHash()` 不再接受 `review` 合法 view，`applyRoute()` 把未知 hash 归一到 `#/workbench`。
- Modify: `web/agent-chat.js`
  - 让 Agent 卡片上下文支持 `title` / `subtitle`，不改变 action 参数仍使用 `ts_code` / `period`。
- Modify: `web/agent-panel.js`
  - Agent 分组标题从 `ts_code · period` 改为名称优先标题 + 代码辅助副标题，保持现有 agent-group 风格。
- Modify: `web/agent-chat.test.mjs`
  - 增加纯逻辑测试，确保 `reduceBindCard()` 保留展示字段。
- Modify: `web/agent-panel.test.mjs`
  - 增加纯 helper 测试，确保 Agent 上下文标题格式为名称优先、代码辅助。
- Modify: `web/styles.css`
  - 删除 `.review-actions` 样式。
  - 增加轻量 `.agent-group__subtitle` 样式，复用 mono/muted 风格。

---

### Task 1: 写导航与复核删除的失败测试

**Files:**
- Modify: `tests/test_frontend_productization.py`

- [ ] **Step 1: Replace the three-view productization test with two-view assertions**

Replace `test_workbench_information_architecture_has_three_views` with:

```python
def test_workbench_information_architecture_has_two_researcher_views(html):
    for view in ["workbench", "company"]:
        assert f'id="view-{view}"' in html
        assert f'id="tab-{view}"' in html
    for removed in ["review", "diagnostics"]:
        assert f'id="view-{removed}"' not in html
        assert f'id="tab-{removed}"' not in html
    assert 'role="tablist"' in html
    assert 'role="tabpanel"' in html
```

- [ ] **Step 2: Replace developer review sync test with no-review-exposure test**

Replace `test_developer_panel_visualizes_automation_feishu_and_review_sync` with:

```python
def test_developer_panel_keeps_operations_without_review_exposure(html, js):
    assert 'id="automation-date" type="date"' in html
    assert 'id="run-automation"' in html
    assert 'id="automation-status"' in html
    assert 'id="refresh-notify-logs"' in html
    assert 'id="notify-log-table"' in html
    assert 'id="review-sync-status"' not in html
    assert "runDisclosureAutomation" in js
    assert "listNotifyLogs" in js
    assert "renderAutomationStatus" in js
    assert "renderNotifyLogs" in js
    assert "renderReviewSyncStatus" not in js
    assert '"/api/automation/disclosure-day"' in js
    assert '"/api/notify/logs?limit="' in js
    assert 'el("run-automation").addEventListener("click", runAutomation)' in js
    assert 'el("refresh-notify-logs").addEventListener("click", loadNotifyLogs)' in js
```

- [ ] **Step 3: Replace review backend UI test with review frontend removal test**

Replace `test_review_state_ui_uses_backend_review_labels` with:

```python
def test_researcher_frontend_does_not_expose_review_ui_or_calls(html, js):
    for marker in [
        'id="view-review"',
        'id="tab-review"',
        'id="review-metrics"',
        'id="review-table"',
        'id="export-review-csv"',
        'id="review-sync-status"',
        'class="review-actions"',
        "renderReviewActions",
        "loadReviewLabels",
        "loadReviewMetrics",
        "renderReviewMetrics",
        "renderReviewSyncStatus",
        "exportReviewCsv",
        "saveReviewLabel",
        "clearReviewLabel",
        "setReviewLabel",
        "reviewLabels",
        '"/api/reviews/labels"',
        '"/api/reviews/metrics"',
        '"/api/reviews/labels.csv"',
    ]:
        assert marker not in html
        assert marker not in js
    template_header = Path("eval/manual_review_template.csv").read_text(encoding="utf-8").splitlines()[0]
    assert template_header == "ts_code,period,rule_id,label,notes,severity,industry"
```

- [ ] **Step 4: Add routing and company-title tests**

Append these tests after `test_company_names_come_from_meta_route`:

```python
def test_navigation_views_exclude_review_route(js):
    assert 'const VIEWS = ["workbench", "company"]' in js
    assert 'review: "复核队列"' not in js
    assert 'if (VIEWS.includes(parts[0])) return { view: parts[0] };' in js
    assert 'navigate("#/workbench")' in js


def test_company_display_is_name_first_with_code_subtitle(js):
    assert "function companyTitle(tsCode)" in js
    assert "function companySubtitle(tsCode, period)" in js
    assert "return displayName(tsCode) || tsCode;" in js
    assert "return `${tsCode} · ${periodLabel(period)}`;" in js
    assert "name.textContent = companyTitle(card.ts_code);" in js
    assert "code.textContent = companySubtitle(card.ts_code, card.period);" in js
    assert "title: companyTitle(card.ts_code)" in js
    assert "subtitle: companySubtitle(card.ts_code, card.period)" in js
```

- [ ] **Step 5: Run focused pytest and verify RED**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp tests/test_frontend_productization.py -q
```

Expected: FAIL because `tab-review` / `view-review` / review functions still exist and `companyTitle()` / `companySubtitle()` are not implemented.

---

### Task 2: 删除 HTML 中研究员复核入口

**Files:**
- Modify: `web/index.html`

- [ ] **Step 1: Remove review tab button**

Delete exactly this line from `web/index.html`:

```html
<button role="tab" id="tab-review" data-view="review" aria-selected="false">复核队列</button>
```

- [ ] **Step 2: Remove developer review sync block**

Delete this whole block from the developer fold:

```html
<div class="fold__block">
  <h3>复核回写状态</h3>
  <p>读取后端复核标签，确认飞书 callback / 前端标注已落库</p>
  <div id="review-sync-status" class="empty">尚未加载复核回写状态</div>
</div>
```

- [ ] **Step 3: Remove review view section**

Delete this whole section:

```html
<!-- ---------- 复核 ---------- -->
<section id="view-review" class="view" role="tabpanel" aria-labelledby="tab-review" hidden>
  <div>
    <div class="section-head">
      <h2>复核状态</h2>
      <p>标注结果保存在后端复核表，可导出为人工复核 CSV</p>
    </div>
    <div class="metric-grid" id="review-metrics"></div>
    <div class="button-row" style="margin-top: var(--space-4)">
      <button id="export-review-csv">导出复核 CSV</button>
    </div>
  </div>
  <div>
    <div class="section-head">
      <h2>标注明细</h2>
      <p>列结构与 eval/manual_review_template.csv 对齐</p>
    </div>
    <div id="review-table"></div>
  </div>
</section>
```

- [ ] **Step 4: Run focused pytest and verify still RED for JS**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp tests/test_frontend_productization.py::test_workbench_information_architecture_has_two_researcher_views tests/test_frontend_productization.py::test_developer_panel_keeps_operations_without_review_exposure tests/test_frontend_productization.py::test_researcher_frontend_does_not_expose_review_ui_or_calls -q
```

Expected: FAIL because `web/app.js` still contains review state/functions/calls.

---

### Task 3: 删除 app.js 的复核前端逻辑并收口路由

**Files:**
- Modify: `web/app.js`

- [ ] **Step 1: Remove review DOM refs and state**

Delete:

```js
const reviewSyncStatus = el("review-sync-status");
const reviewMetrics = el("review-metrics");
const reviewTable = el("review-table");
```

Delete:

```js
const REVIEW_EXPORT_COLUMNS = ["ts_code", "period", "rule_id", "label", "notes", "severity", "industry"];
```

Delete the `reviewLabels` property from `state`.

- [ ] **Step 2: Remove review API wrappers**

Delete these methods from `api`:

```js
async listReviewLabels() {
  return requestJson("/api/reviews/labels");
},

async saveReviewLabel(label) {
  return requestJson("/api/reviews/labels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(label),
  });
},

async deleteReviewLabel(tsCode, period, ruleId) {
  return requestJson(`/api/reviews/labels/${tsCode}/${period}/${ruleId}`, { method: "DELETE" });
},

async getReviewMetrics() {
  return requestJson("/api/reviews/metrics");
},
```

- [ ] **Step 3: Remove review action renderer**

Delete the entire `renderReviewActions(card)` function.

In `renderCard(card, options = {})`, change:

```js
foot.append(permalink, renderReviewActions(card));
```

to:

```js
foot.append(permalink);
```

- [ ] **Step 4: Remove review sync/render/label/export functions**

Delete these entire functions from `web/app.js`:

```js
renderReviewSyncStatus
reviewKey
reviewLabelText
loadReviewLabels
saveReviewLabel
clearReviewLabel
setReviewLabel
loadReviewMetrics
renderReviewMetrics
renderReview
exportReviewCsv
```

- [ ] **Step 5: Remove review event binding and boot calls**

Delete:

```js
el("export-review-csv").addEventListener("click", exportReviewCsv);
```

Delete these lines from `boot()`:

```js
renderReview();
loadReviewLabels().catch((error) => {
  setStatus({ error: error.message });
  notify(error.message, true);
});
loadReviewMetrics();
```

- [ ] **Step 6: Change legal views and titles**

Replace:

```js
const VIEWS = ["workbench", "company", "review"];
const VIEW_TITLES = {
  workbench: "披露日研判",
  company: "单票研判",
  review: "复核队列",
};
```

with:

```js
const VIEWS = ["workbench", "company"];
const VIEW_TITLES = {
  workbench: "披露日研判",
  company: "单票研判",
};
```

- [ ] **Step 7: Normalize unknown hashes including #/review**

In `applyRoute()`, after `activateView(route.view);`, add:

```js
if (!route.date && !route.tsCode && window.location.hash !== `#/${route.view}`) {
  navigate("#/workbench");
  return;
}
```

This keeps `#/day/...` and `#/company/...` stable, while `#/review` and other unknown views normalize to `#/workbench`.

- [ ] **Step 8: Run focused pytest and verify navigation/review tests pass or expose next missing work**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp tests/test_frontend_productization.py::test_workbench_information_architecture_has_two_researcher_views tests/test_frontend_productization.py::test_developer_panel_keeps_operations_without_review_exposure tests/test_frontend_productization.py::test_researcher_frontend_does_not_expose_review_ui_or_calls tests/test_frontend_productization.py::test_navigation_views_exclude_review_route -q
```

Expected: PASS for these tests.

- [ ] **Step 9: Commit Task 1-3 changes**

Run:

```bash
git add tests/test_frontend_productization.py web/index.html web/app.js
git commit -m "$(cat <<'EOF'
refactor: remove researcher review frontend

Remove review navigation, review summaries, label chips, and review API calls from the researcher-facing frontend while leaving backend review capabilities untouched.

Co-Authored-By: Claude GPT-5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: 股票名称优先展示与 Agent 上下文展示

**Files:**
- Modify: `web/app.js`
- Modify: `web/agent-chat.js`
- Modify: `web/agent-panel.js`
- Modify: `web/agent-chat.test.mjs`
- Modify: `web/agent-panel.test.mjs`
- Modify: `web/styles.css`

- [ ] **Step 1: Add failing Agent chat display test**

In `web/agent-chat.test.mjs`, add:

```js
test("bind card keeps name-first display fields for panel context", () => {
  const state = reduceBindCard(createChatState(), {
    ts_code: "603026.SH",
    period: "20250630",
    title: "石大胜华",
    subtitle: "603026.SH · 2025 半年报",
  });

  assert.equal(state.currentCard.title, "石大胜华");
  assert.equal(state.currentCard.subtitle, "603026.SH · 2025 半年报");
  assert.equal(state.currentKey, "603026.SH:20250630");
});
```

- [ ] **Step 2: Add failing Agent panel format test**

In `web/agent-panel.test.mjs`, import `formatAgentCard` and add:

```js
test("formatAgentCard renders name first and code subtitle", () => {
  assert.deepEqual(
    formatAgentCard({ title: "石大胜华", subtitle: "603026.SH · 2025 半年报", ts_code: "603026.SH", period: "20250630" }),
    { title: "石大胜华", subtitle: "603026.SH · 2025 半年报" },
  );
  assert.deepEqual(
    formatAgentCard({ ts_code: "603026.SH", period: "20250630" }),
    { title: "603026.SH", subtitle: "20250630" },
  );
});
```

- [ ] **Step 3: Run Node tests and verify RED**

Run:

```bash
npm test -- web/agent-chat.test.mjs web/agent-panel.test.mjs
```

Expected: FAIL because `formatAgentCard` is not exported yet.

- [ ] **Step 4: Add app.js company display helpers**

After `displayName(tsCode)`, add:

```js
function companyTitle(tsCode) {
  return displayName(tsCode) || tsCode;
}

function companySubtitle(tsCode, period) {
  return `${tsCode} · ${periodLabel(period)}`;
}

function agentCardContext(card) {
  return {
    ts_code: card.ts_code,
    period: card.period,
    severity: severityKey(card),
    title: companyTitle(card.ts_code),
    subtitle: companySubtitle(card.ts_code, card.period),
  };
}
```

- [ ] **Step 5: Apply name-first helpers in card rendering**

In `renderCard(card, options = {})`, change:

```js
name.textContent = displayName(card.ts_code) || card.ts_code;
code.textContent = `${card.ts_code} · ${card.period}`;
node.addEventListener("click", () => state.agent?.bindCard({ ts_code: card.ts_code, period: card.period, severity: key }));
```

to:

```js
name.textContent = companyTitle(card.ts_code);
code.textContent = companySubtitle(card.ts_code, card.period);
node.addEventListener("click", () => state.agent?.bindCard(agentCardContext(card)));
```

- [ ] **Step 6: Apply name-first helper to OK list and data tables**

In the OK brief list, change:

```js
name.textContent = displayName(card.ts_code) || card.ts_code;
```

to:

```js
name.textContent = companyTitle(card.ts_code);
```

In `renderDataProblemGroup(events)`, change:

```js
const name = displayName(event.ts_code);
return `<tr><td class="mono">${escapeHtml(event.ts_code)}</td><td>${escapeHtml(name)}</td><td class="mono">${escapeHtml(event.period)}</td><td>${escapeHtml(event.industry || "unknown")}</td><td>${escapeHtml(event.status)}</td><td>${escapeHtml(event.message)}</td></tr>`;
```

to:

```js
const name = companyTitle(event.ts_code);
return `<tr><td>${escapeHtml(name)}</td><td class="mono">${escapeHtml(event.ts_code)}</td><td class="mono">${escapeHtml(periodLabel(event.period))}</td><td>${escapeHtml(event.industry || "unknown")}</td><td>${escapeHtml(event.status)}</td><td>${escapeHtml(event.message)}</td></tr>`;
```

and change the table header from:

```html
<thead><tr><th>代码</th><th>名称</th><th>报告期</th><th>行业</th><th>状态</th><th>原因</th></tr></thead>
```

to:

```html
<thead><tr><th>名称</th><th>代码</th><th>报告期</th><th>行业</th><th>状态</th><th>原因</th></tr></thead>
```

- [ ] **Step 7: Apply name-first helper to exports and loadCompany Agent bind**

In `exportBundleCsv()`, change:

```js
displayName(event.ts_code),
```

to:

```js
companyTitle(event.ts_code),
```

In `loadCompany()`, change:

```js
state.agent?.bindCard({ ts_code: result.card.ts_code, period: result.card.period, severity: severityKey(result.card) });
```

to:

```js
state.agent?.bindCard(agentCardContext(result.card));
```

- [ ] **Step 8: Add Agent panel format helper and use it**

In `web/agent-panel.js`, replace the private `formatCard(card)` function with:

```js
export function formatAgentCard(card) {
  return {
    title: card.title || card.ts_code || "未知公司",
    subtitle: card.subtitle || card.period || "",
  };
}
```

Then update `startGroup(card)`:

```js
const formatted = formatAgentCard(card);
groupTitle.textContent = formatted.title;
if (formatted.subtitle) {
  const groupSubtitle = document.createElement("span");
  groupSubtitle.className = "agent-group__subtitle";
  groupSubtitle.textContent = formatted.subtitle;
  headNode.append(groupSubtitle);
}
```

Append the `badge` after subtitle:

```js
headNode.append(badge);
```

Update `setContext(card)` from:

```js
context.textContent = `当前：${formatCard(card)}`;
```

to:

```js
const formatted = formatAgentCard(card);
context.textContent = formatted.subtitle ? `当前：${formatted.title} / ${formatted.subtitle}` : `当前：${formatted.title}`;
```

- [ ] **Step 9: Add agent group subtitle style**

In `web/styles.css`, after `.agent-group__title`, add:

```css
.agent-group__subtitle {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--md-sys-color-on-surface-muted);
}
```

Delete the `.review-actions` style block.

- [ ] **Step 10: Run focused tests and verify GREEN**

Run:

```bash
npm test -- web/agent-chat.test.mjs web/agent-panel.test.mjs
python -m pytest --basetemp=.pytest_tmp tests/test_frontend_productization.py::test_company_display_is_name_first_with_code_subtitle tests/test_frontend_productization.py::test_rendering_escapes_untrusted_values -q
```

Expected: PASS.

- [ ] **Step 11: Commit Task 4 changes**

Run:

```bash
git add tests/test_frontend_productization.py web/app.js web/agent-chat.js web/agent-panel.js web/agent-chat.test.mjs web/agent-panel.test.mjs web/styles.css
git commit -m "$(cat <<'EOF'
feat: show company names before stock codes

Use company names as the primary display label in researcher-facing cards and Agent context while preserving ts_code and period as stable identifiers.

Co-Authored-By: Claude GPT-5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: 最终自审与验证

**Files:**
- Read/verify only unless failures require fixes.

- [ ] **Step 1: Run frontend productization tests**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp tests/test_frontend_productization.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full pytest**

Run:

```bash
python -m pytest --basetemp=.pytest_tmp -q
```

Expected: PASS.

- [ ] **Step 3: Run Node frontend tests**

Run:

```bash
npm test
```

Expected: PASS.

- [ ] **Step 4: Syntax-check changed JavaScript files**

Run:

```bash
node --check web/app.js && node --check web/agent-chat.js && node --check web/agent-panel.js
```

Expected: no output and exit code 0.

- [ ] **Step 5: Final grep self-review**

Run:

```bash
python - <<'PY'
from pathlib import Path
html = Path('web/index.html').read_text(encoding='utf-8')
js = Path('web/app.js').read_text(encoding='utf-8')
css = Path('web/styles.css').read_text(encoding='utf-8')
for marker in ['tab-review', 'view-review', 'review-table', 'review-metrics', 'export-review-csv', 'review-sync-status', 'reviewLabels', 'renderReviewActions', 'loadReviewLabels', 'loadReviewMetrics', 'renderReviewSyncStatus', 'review-actions']:
    assert marker not in html
    assert marker not in js
    assert marker not in css
assert 'const VIEWS = ["workbench", "company"]' in js
assert 'function companyTitle(tsCode)' in js
assert 'function companySubtitle(tsCode, period)' in js
print('navigation review cleanup self-review passed')
PY
```

Expected: prints `navigation review cleanup self-review passed`.

- [ ] **Step 6: Check git status**

Run:

```bash
git status --short
```

Expected: clean working tree.

- [ ] **Step 7: Report completion with verification evidence**

Report concise summary in Chinese:

```text
已完成前端导航改造：左侧只剩「披露日研判 / 单票研判」，研究员前端复核队列/指标/表格/CSV/标注 chip 已删除；股票展示改为名称优先、代码和报告期辅助；Agent 上下文同步名称优先。

验证：
- python -m pytest --basetemp=.pytest_tmp -q: <结果>
- npm test: <结果>
- node --check web/app.js && node --check web/agent-chat.js && node --check web/agent-panel.js: 通过
- 自审 grep: 通过
```
