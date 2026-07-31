# 扫描入口与信息架构收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把重复的披露日扫描入口合并为一个主按钮，把扫描诊断与开发者工具从顶级 tab 降为工作台折叠区，并清理已无调用的 API wrapper。

**Architecture:** 纯前端改动。折叠区用 `web/index.html` 中静态声明的原生 `<details>` 包住现有容器，容器 id 全部不变，因此 `renderDiagnostics()`、`loadQuarterly()`、`setStatus()` 等 render 函数一行不改。顶栏扫描按钮改为单节点三态（`idle` / `scanning` / `cancelling`），把当前分散在三处的 disabled 重置收敛到一个 `setScanState()`。导出菜单是唯一需要 JS 的新组件，放进新文件 `web/components.js`。

**Tech Stack:** 原生 HTML / CSS / ES2020（无构建步骤、无框架）；pytest 做前端契约的字符串断言；Playwright headless 做交互与溢出验证。

**Spec:** `docs/superpowers/specs/2026-07-31-scan-entry-consolidation-design.md`

---

## 执行前须知

**后端那条线已收工且全绿。** 后端已补齐 job history 接口（`GET /api/disclosure-day/jobs`）、复核状态存储与 API（`/api/reviews/labels`）、飞书 interactive card 与 callback（`/api/notify/feishu/callback`）。这些改动尚未 commit 但测试通过，与本计划**零文件重叠**。

实测基线：

```bash
python -m pytest -q --basetemp=.pytest_tmp
# 152 passed

python -m pytest tests/test_frontend_contracts.py tests/test_frontend_diagnostics.py tests/test_frontend_productization.py -q --basetemp=.pytest_tmp
# 17 passed
```

各 Task 的验证步骤只跑前端三个文件（快，且失败信号精准）；Task 7 之后跑一次全量确认没有连带影响。

**注意：后端的落地让 Spec 2/3/4 的前置依赖全部就绪。** 但本计划范围不变——只做 Spec 1。Spec 2 现在可以立即开始 brainstorm，因为它等的 `list_recent()` 与列表路由都已存在。

**只允许改这些文件：**

- `web/index.html`
- `web/app.js`
- `web/styles.css`
- `web/components.js`（新建）
- `tests/test_frontend_contracts.py`
- `tests/test_frontend_diagnostics.py`
- `tests/test_frontend_productization.py`

**不要碰** `copilot/` 下任何文件。新的 `web/components.js` 会被 `app.mount("/", StaticFiles(directory="web", html=True))`（`copilot/api/app.py:237`）自动伺服，无需后端改动。

**关于 TDD：** 本项目的前端测试是对 `web/*` 源文件做字符串断言（见现有 `tests/test_frontend_*.py`），不是浏览器行为测试。沿用这一既有模式：先改断言让它失败，再改源文件让它通过。真正的行为验证放在 Task 7 的 Playwright 步骤。

---

## File Structure

| 文件 | 职责 | 本次改动 |
| --- | --- | --- |
| `web/index.html` | 静态声明所有视图、区块、dialog | 侧栏减一个 tab；顶栏重排为四控件；新增两个 `<details>` 折叠区；删除 `#view-diagnostics` 整段；引入 `components.js` |
| `web/app.js` | 路由、渲染、状态、事件绑定 | `VIEWS` 减项；`parseHash` 加 diagnostics 分支；新增 `setScanState()`；合并扫描按钮事件；删三个死 wrapper；导出改用菜单组件 |
| `web/components.js`（新建） | 可复用 UI 原语 | 只放 `createMenuButton()` |
| `web/styles.css` | 视觉体系 | 新增 `.fold*`、`.app-bar__sep`、`.menu*` 三组样式 |

`web/app.js` 当前 1212 行。本次净减：删 23 行 wrapper、删两个旧事件处理器，新增 `setScanState()` 与一处菜单装配，整体略微收缩。

---

## Task 1: 侧栏降为三视图

**Files:**
- Modify: `tests/test_frontend_productization.py:22-27`
- Modify: `web/index.html:23-28`（nav）
- Modify: `web/app.js:317-323`（`VIEWS` / `VIEW_TITLES`）

- [ ] **Step 1: 改断言使其失败**

在 `tests/test_frontend_productization.py` 中，把现有的 `test_workbench_information_architecture_has_four_views` 整个函数替换为：

```python
def test_workbench_information_architecture_has_three_views(html):
    for view in ["workbench", "company", "review"]:
        assert f'id="view-{view}"' in html
        assert f'id="tab-{view}"' in html
    assert 'role="tablist"' in html
    assert 'role="tabpanel"' in html
    # 扫描诊断已降为工作台折叠区，不再是顶级视图
    assert 'id="view-diagnostics"' not in html
    assert 'id="tab-diagnostics"' not in html
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_frontend_productization.py::test_workbench_information_architecture_has_three_views -q --basetemp=.pytest_tmp`

Expected: FAIL，`assert 'id="view-diagnostics"' not in html` 断言失败（该元素目前仍在 HTML 中）。

- [ ] **Step 3: 删掉侧栏的诊断 tab**

`web/index.html` 第 23-28 行，删除 `tab-diagnostics` 那一行。改动后为：

```html
        <nav class="nav" role="tablist" aria-label="工作台视图">
          <button role="tab" id="tab-workbench" data-view="workbench" aria-selected="true">披露日研判</button>
          <button role="tab" id="tab-company" data-view="company" aria-selected="false">单票研判</button>
          <button role="tab" id="tab-review" data-view="review" aria-selected="false">复核队列</button>
        </nav>
```

- [ ] **Step 4: 删掉诊断视图整段**

`web/index.html` 第 162-193 行，删除从 `<!-- ---------- 诊断 ---------- -->` 注释到 `</section>` 的整段（即 `<section id="view-diagnostics" ...>` 及其全部内容）。

这段里的四个容器（`#diagnostic-status`、`#poll-rss`、`#quarterly-review`、`#operation-status`）会在 Task 2 以相同 id 重新出现在折叠区内。**Task 1 与 Task 2 之间测试是红的，这是预期的**；两个 Task 合起来才回到绿。

- [ ] **Step 5: 收缩 `VIEWS` 与 `VIEW_TITLES`**

`web/app.js` 第 317-323 行替换为：

```js
const VIEWS = ["workbench", "company", "review"];
const VIEW_TITLES = {
  workbench: "披露日研判",
  company: "单票研判",
  review: "复核队列",
};
```

`activateView()` 按 `VIEWS` 循环取 `el(`view-${name}`)`，数组收缩后不会再去找已删除的元素，无需改动该函数。

- [ ] **Step 6: 不提交，继续 Task 2**

此时 HTML 里已没有 `#diagnostic-status` 等容器，`web/app.js:18-20` 的 `el()` 会拿到 `null`。Task 2 补回折叠区后才是可运行状态。不要在这里 commit。

---

## Task 2: 新增两个折叠区

**Files:**
- Modify: `tests/test_frontend_productization.py`（新增一个测试函数）
- Modify: `web/index.html`（在 `#card-groups` 之后、`.colophon` 之前插入）

- [ ] **Step 1: 写失败的测试**

在 `tests/test_frontend_productization.py` 中，紧跟 `test_workbench_information_architecture_has_three_views` 之后新增：

```python
def test_advanced_sections_are_collapsed_disclosures(html, css):
    # 高级诊断与开发者工具各成一个原生 details：键盘可达、Ctrl+F 能搜到收起区内文字
    assert '<details id="adv-diagnostics"' in html
    assert '<details id="adv-developer"' in html
    # 默认收起：details 上不带 open 属性
    assert "open" not in html.split('<details id="adv-diagnostics"')[1].split(">")[0]
    assert "open" not in html.split('<details id="adv-developer"')[1].split(">")[0]
    # 容器 id 全部不变，因此 renderDiagnostics / loadQuarterly / setStatus 无需改动
    for container in ["diagnostic-status", "quarterly-review", "operation-status", "poll-rss"]:
        assert f'id="{container}"' in html
    assert ".fold {" in css
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_frontend_productization.py::test_advanced_sections_are_collapsed_disclosures -q --basetemp=.pytest_tmp`

Expected: FAIL，`assert '<details id="adv-diagnostics"' in html` 失败。

- [ ] **Step 3: 插入两个折叠区**

`web/index.html` 中，在工作台 section 内 `<div id="card-groups" class="card-groups"></div>` 所属的 `</div>` 之后、`<div class="colophon">` 之前，插入：

```html
          <details id="adv-diagnostics" class="fold">
            <summary>
              <span class="fold__title">高级诊断</span>
              <span class="fold__hint">每家覆盖池公司为什么出卡或未出卡</span>
            </summary>
            <div class="fold__body">
              <div id="diagnostic-status"></div>
            </div>
          </details>

          <details id="adv-developer" class="fold">
            <summary>
              <span class="fold__title">开发者</span>
              <span class="fold__hint">系统内部状态，与当日研判结论无关</span>
            </summary>
            <div class="fold__body">
              <div class="fold__block">
                <h3>RSS 触发</h3>
                <p>RSS 仅作为触发提示，财务数据仍走 Tushare</p>
                <button id="poll-rss" class="outlined">轮询 RSS</button>
              </div>
              <div class="fold__block">
                <h3>披露季复盘</h3>
                <div class="metric-grid" id="quarterly-review"></div>
              </div>
              <div class="fold__block">
                <h3>操作日志</h3>
                <p>最近一次接口调用的原始返回</p>
                <pre id="operation-status" class="log"></pre>
              </div>
            </div>
          </details>
```

- [ ] **Step 4: 加折叠区样式**

`web/styles.css` 末尾的 `/* ---------- 对话框 ---------- */` 之前插入：

```css
/* ---------- 折叠区：高级诊断 / 开发者 ---------- */

/* 用原生 <details>：键盘可达、Ctrl+F 能搜到收起区内文字、不必自己维护 aria-expanded */
.fold {
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--radius-lg);
  background: var(--md-sys-color-surface);
  box-shadow: var(--shadow-1);
}

.fold > summary {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
  flex-wrap: wrap;
  padding: var(--space-3) var(--space-5);
  border-radius: var(--radius-lg);
  cursor: pointer;
  /* display:flex 已经吃掉默认三角，Safari 还要单独收 ::-webkit-details-marker */
  list-style: none;
}

.fold > summary::-webkit-details-marker {
  display: none;
}

/* 自绘展开标记：陶土橙已是导语竖线与焦点环的用色，这里属同类极小面积强调 */
.fold > summary::before {
  content: "▸";
  color: var(--clay);
  font-size: 11px;
  transition: transform var(--ease);
}

.fold[open] > summary::before {
  transform: rotate(90deg);
}

.fold > summary:hover {
  background: var(--md-sys-color-surface-container-low);
}

.fold__title {
  font-family: var(--serif);
  font-size: 17px;
  font-weight: 600;
}

.fold__hint {
  font-size: 13px;
  color: var(--md-sys-color-on-surface-muted);
}

.fold__body {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  padding: var(--space-4) var(--space-5) var(--space-5);
  border-top: 1px solid var(--md-sys-color-outline-variant);
}

.fold__block > h3 {
  margin: 0 0 var(--space-1);
  font-family: var(--serif);
  font-size: 15px;
  font-weight: 600;
}

.fold__block > p {
  margin: 0 0 var(--space-3);
  font-size: 13px;
  color: var(--md-sys-color-on-surface-muted);
}
```

- [ ] **Step 5: 跑测试确认通过**

Run: `python -m pytest tests/test_frontend_productization.py -q --basetemp=.pytest_tmp`

Expected: `test_workbench_information_architecture_has_three_views` 与 `test_advanced_sections_are_collapsed_disclosures` 均 PASS。同文件的 `test_exports_cover_csv_and_json` 与 `test_disclosure_scan_uses_cancellable_job_polling` 仍会 PASS（Task 3、4 才动它们）。

- [ ] **Step 6: 提交**

```bash
git add web/index.html web/styles.css web/app.js tests/test_frontend_productization.py
git commit -m "feat: demote diagnostics and developer tools to folds"
```

---

## Task 3: 扫描入口合并为单按钮三态

**Files:**
- Modify: `tests/test_frontend_productization.py`（`test_disclosure_scan_uses_cancellable_job_polling`）
- Modify: `web/index.html:40-49`（顶栏）
- Modify: `web/app.js:32`（元素引用）、`:956-1016`（job 生命周期）、`:1128-1159`（事件绑定）
- Modify: `web/styles.css`（`.app-bar__sep`）

- [ ] **Step 1: 改断言使其失败**

`tests/test_frontend_productization.py` 中把 `test_disclosure_scan_uses_cancellable_job_polling` 整个函数替换为：

```python
def test_disclosure_scan_uses_cancellable_job_polling(html, js):
    # 扫描按钮是单节点三态，空闲态不再常驻一个永远灰着的停止按钮
    assert 'id="start-disclosure-scan"' in html
    assert 'id="stop-disclosure-scan"' not in html
    assert 'id="analyze-disclosure-day"' not in html
    assert 'id="scan-disclosure-day"' not in html
    # 三处 disabled 重置收敛到一个函数
    assert "function setScanState(state)" in js
    assert '"scanning"' in js
    assert '"cancelling"' in js
    assert "/api/disclosure-day/jobs" in js
    assert "startDisclosureDayJob(date)" in js
    assert "getDisclosureDayJob(jobId)" in js
    assert "cancelDisclosureDayJob(jobId)" in js
    assert "pollDisclosureJob" in js
    assert "renderJobProgress" in js
    assert "current_ts_code" in js
    assert "current_stage" in js
    assert "stopDisclosureScan" in js
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_frontend_productization.py::test_disclosure_scan_uses_cancellable_job_polling -q --basetemp=.pytest_tmp`

Expected: FAIL，`assert 'id="start-disclosure-scan"' in html` 失败。

- [ ] **Step 3: 重排顶栏**

`web/index.html` 第 40-49 行的 `<div class="app-bar__status">` 整块替换为：

```html
        <div class="app-bar__status">
          <!-- 日期选择器：控件值为 YYYY-MM-DD，调用接口前转成 YYYYMMDD -->
          <input id="disclosure-date" type="date" value="2025-08-21" aria-label="披露日期" />
          <!-- 单节点双态：空闲「开始扫描」，扫描中原地变「停止扫描」 -->
          <button id="start-disclosure-scan" data-state="idle">开始扫描</button>
          <!-- 竖线左侧是产出数据，右侧是分发数据 -->
          <span class="app-bar__sep" aria-hidden="true"></span>
          <div id="export-menu-mount"></div>
          <button id="preview-feishu" class="tonal">预览飞书摘要</button>
        </div>
```

`#export-menu-mount` 是占位节点，Task 4 会用 `createMenuButton()` 把它替换成真正的菜单。

- [ ] **Step 4: 加分隔线样式**

`web/styles.css` 中 `.app-bar__status { ... }` 规则（约第 305-310 行）之后插入：

```css
/* 顶栏分组竖线：左侧「产出数据」，右侧「分发数据」 */
.app-bar__sep {
  width: 1px;
  align-self: stretch;
  margin: var(--space-1) 0;
  background: var(--md-sys-color-outline-variant);
}
```

- [ ] **Step 5: 换掉按钮引用并加入 `setScanState()`**

`web/app.js` 第 32 行：

```js
const stopDisclosureScanButton = el("stop-disclosure-scan");
```

替换为：

```js
const scanButton = el("start-disclosure-scan");
```

然后在 `createProgress()` 定义之后、`const scanProgress = ...` 之前（约第 257 行）插入：

```js
/* 扫描按钮单节点三态。用两个节点互相 hide 的话，disabled 状态要在多处同步——
   之前正是漏在这里：两个 catch 分支和 finishDisclosureJob 各自手动重置了一遍。 */
function setScanState(state) {
  scanButton.dataset.state = state;
  const scanning = state === "scanning" || state === "cancelling";
  scanButton.textContent = scanning ? "停止扫描" : "开始扫描";
  scanButton.classList.toggle("outlined", scanning);
  // cancelling 期间禁用，避免重复发取消请求
  scanButton.disabled = state === "cancelling";
}
```

- [ ] **Step 6: 把三处 disabled 重置换成 `setScanState()`**

`web/app.js` 第 956-1016 行，四个函数各改一处。

`finishDisclosureJob()` 中：

```js
  stopDisclosureScanButton.disabled = true;
```

改为：

```js
  setScanState("idle");
```

`stopDisclosureScan()` 中：

```js
  stopDisclosureScanButton.disabled = true;
```

改为：

```js
  setScanState("cancelling");
```

`loadDisclosureDay()` 中，`scanProgress.start(...)` 之后那行：

```js
  stopDisclosureScanButton.disabled = false;
```

改为：

```js
  setScanState("scanning");
```

`loadDisclosureDay()` 中轮询失败分支与外层 catch 各有一处 `stopDisclosureScanButton.disabled = true;`，两处都改为：

```js
      setScanState("idle");
```

改完后 `stopDisclosureScanButton` 这个标识符在整个文件中应为零出现。用 `grep -n stopDisclosureScanButton web/app.js` 确认，预期无输出。

- [ ] **Step 7: 合并事件绑定**

`web/app.js` 中删除这两个处理器（原第 1128-1145 行）：

```js
el("analyze-disclosure-day").addEventListener("click", () => {
  const date = selectedDate();
  if (!date) {
    notify("请先选择披露日期", true);
    return;
  }
  navigate(`#/day/${date}`);
});

el("scan-disclosure-day").addEventListener("click", async () => {
  const date = selectedDate();
  if (!date) {
    notify("请先选择披露日期", true);
    return;
  }
  await loadDisclosureDay(date);
  navigate("#/diagnostics");
});
```

以及原第 1154-1159 行的：

```js
stopDisclosureScanButton.addEventListener("click", () => {
  stopDisclosureScan().catch((error) => {
    setStatus({ error: error.message });
    notify(error.message, true);
  });
});
```

在原 `el("analyze-disclosure-day")` 所在位置插入合并后的单一处理器：

```js
/* 同一个按钮按当前状态分派：空闲时开扫，扫描中发取消 */
scanButton.addEventListener("click", () => {
  if (scanButton.dataset.state === "idle") {
    const date = selectedDate();
    if (!date) {
      notify("请先选择披露日期", true);
      return;
    }
    navigate(`#/day/${date}`);
    return;
  }
  stopDisclosureScan().catch((error) => {
    setStatus({ error: error.message });
    notify(error.message, true);
  });
});
```

- [ ] **Step 8: 跑测试确认通过**

Run: `python -m pytest tests/test_frontend_productization.py -q --basetemp=.pytest_tmp`

Expected: 全部 PASS。

- [ ] **Step 9: 提交**

```bash
git add web/index.html web/app.js web/styles.css tests/test_frontend_productization.py
git commit -m "feat: merge disclosure scan entries into one stateful button"
```

---

## Task 4: 导出菜单组件

**Files:**
- Modify: `tests/test_frontend_productization.py`（`test_exports_cover_csv_and_json`）
- Create: `web/components.js`
- Modify: `web/index.html`（script 标签）
- Modify: `web/app.js`（原第 1175-1176 行导出绑定）
- Modify: `web/styles.css`（`.menu*`）

- [ ] **Step 1: 改断言使其失败**

`tests/test_frontend_productization.py` 中把 `test_exports_cover_csv_and_json` 整个函数替换为：

```python
def test_exports_cover_csv_and_json(html, js):
    # 导出项收进顶栏「导出 ▾」菜单后改由 JS 创建，id 保持不变但不再出现在 HTML 里
    assert 'id="export-menu-csv"' not in html
    assert 'id="export-menu-json"' not in html
    assert 'id="export-menu-mount"' in html
    assert '<script src="/components.js"></script>' in html
    assert "export-menu-csv" in js
    assert "export-menu-json" in js
    assert "createMenuButton" in js
    assert "exportBundleCsv" in js
    assert "exportBundleJson" in js
    assert "function csvCell(value)" in js
    # CSV 注入/断行需要转义
    assert 'text.replace(/"/g, \'""\')' in js


def test_menu_component_is_keyboard_accessible():
    components = Path("web/components.js").read_text(encoding="utf-8")

    assert "function createMenuButton(" in components
    assert 'aria-haspopup", "menu"' in components
    assert 'aria-expanded' in components
    assert '"Escape"' in components
    assert '"ArrowDown"' in components
    assert '"ArrowUp"' in components
    # 点菜单外部要能关闭
    assert "wrap.contains(event.target)" in components
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_frontend_productization.py::test_exports_cover_csv_and_json tests/test_frontend_productization.py::test_menu_component_is_keyboard_accessible -q --basetemp=.pytest_tmp`

Expected: 两个都 FAIL——前者因 `id="export-menu-csv"` 仍在 HTML 中，后者因 `web/components.js` 不存在（`FileNotFoundError`）。

- [ ] **Step 3: 新建 `web/components.js`**

```js
"use strict";

/*
 * 可复用 UI 原语。
 *
 * 折叠区用原生 <details> 直接写在 index.html 里，不需要 JS，因此不在这里。
 * 菜单需要 JS：菜单项由数据驱动，且要处理点外部关闭、Esc 关闭、方向键移动
 * 和 aria-expanded 同步。
 */

/* 顶栏「导出 ▾」。只负责壳与交互，具体动作由调用方通过 onSelect 传入。
   mount 是 HTML 里的占位节点，会被整体替换掉。 */
function createMenuButton({ mount, label, items }) {
  const wrap = document.createElement("div");
  wrap.className = "menu";

  const trigger = document.createElement("button");
  trigger.className = "outlined menu__trigger";
  trigger.textContent = `${label} ▾`;
  trigger.setAttribute("aria-haspopup", "menu");
  trigger.setAttribute("aria-expanded", "false");

  const list = document.createElement("div");
  list.className = "menu__list";
  list.setAttribute("role", "menu");
  list.hidden = true;

  const entries = items.map((item) => {
    const node = document.createElement("button");
    node.className = "menu__item";
    node.id = item.id;
    node.textContent = item.label;
    node.setAttribute("role", "menuitem");
    node.addEventListener("click", () => {
      close();
      item.onSelect();
    });
    list.append(node);
    return node;
  });

  function isOpen() {
    return !list.hidden;
  }

  function open() {
    list.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    entries[0].focus();
  }

  function close() {
    list.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
  }

  trigger.addEventListener("click", () => {
    if (isOpen()) close();
    else open();
  });

  /* Esc 关闭并把焦点还给触发按钮；方向键在项间循环 */
  wrap.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isOpen()) {
      event.preventDefault();
      close();
      trigger.focus();
      return;
    }
    if (!isOpen()) return;
    const index = entries.indexOf(document.activeElement);
    if (index < 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      entries[(index + 1) % entries.length].focus();
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      entries[(index - 1 + entries.length) % entries.length].focus();
    }
  });

  /* 点菜单外部关闭。触发按钮自身的点击也会冒泡到这里，
     但它在 wrap 内，所以不会被这条误关。 */
  document.addEventListener("click", (event) => {
    if (isOpen() && !wrap.contains(event.target)) close();
  });

  wrap.append(trigger, list);
  mount.replaceWith(wrap);
  return { open, close };
}
```

- [ ] **Step 4: 在 index.html 引入 components.js**

`web/index.html` 倒数第三行：

```html
  <script src="/app.js"></script>
```

替换为：

```html
  <script src="/components.js"></script>
  <script src="/app.js"></script>
```

`components.js` 必须在 `app.js` 之前：两者都是普通脚本（非 module），`createMenuButton` 作为全局函数声明供 `app.js` 调用。

- [ ] **Step 5: 加菜单样式**

`web/styles.css` 中 Task 3 加的 `.app-bar__sep` 规则之后插入：

```css
.menu {
  position: relative;
}

.menu__list {
  position: absolute;
  top: calc(100% + var(--space-1));
  right: 0;
  z-index: 10;
  min-width: 168px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-1);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--radius);
  background: var(--md-sys-color-surface);
  box-shadow: var(--shadow-3);
}

/* 菜单项要无底色、左对齐，且不继承默认按钮的深墨底 */
.menu__item {
  height: 32px;
  padding: 0 var(--space-3);
  border: 0;
  border-radius: var(--radius-sm);
  background: none;
  color: var(--md-sys-color-on-surface);
  font-size: 13px;
  font-weight: 400;
  text-align: left;
}

.menu__item:hover {
  background: var(--md-sys-color-surface-container-high);
}
```

- [ ] **Step 6: 换掉导出按钮绑定**

`web/app.js` 中删除原第 1175-1176 行：

```js
el("export-menu-json").addEventListener("click", exportBundleJson);
el("export-menu-csv").addEventListener("click", exportBundleCsv);
```

在同一位置插入：

```js
/* 导出 JSON / CSV 是同类动作，收进一个下拉；id 沿用原值 */
createMenuButton({
  mount: el("export-menu-mount"),
  label: "导出",
  items: [
    { id: "export-menu-json", label: "导出 JSON", onSelect: exportBundleJson },
    { id: "export-menu-csv", label: "导出 CSV", onSelect: exportBundleCsv },
  ],
});
```

- [ ] **Step 7: 跑测试确认通过**

Run: `python -m pytest tests/test_frontend_productization.py -q --basetemp=.pytest_tmp`

Expected: 全部 PASS。

- [ ] **Step 8: 提交**

```bash
git add web/components.js web/index.html web/app.js web/styles.css tests/test_frontend_productization.py
git commit -m "feat: group exports into a topbar menu"
```

---

## Task 5: 诊断深链接

**Files:**
- Modify: `tests/test_frontend_diagnostics.py`（整个文件重写）
- Modify: `web/app.js:334-361`（`parseHash` / `applyRoute`）

- [ ] **Step 1: 重写测试文件**

`tests/test_frontend_diagnostics.py` 全文替换为：

```python
from pathlib import Path


def test_frontend_keeps_disclosure_diagnostics_in_advanced_fold():
    html = Path("web/index.html").read_text(encoding="utf-8")
    js = Path("web/app.js").read_text(encoding="utf-8")

    # 诊断从顶级 tab 降为工作台折叠区，能力保留：容器与渲染函数都还在
    assert '<details id="adv-diagnostics"' in html
    assert 'id="diagnostic-status"' in html
    assert "renderDiagnostics" in js
    # 诊断数据随扫描 job 的 bundle 一起回来，不再单独调扫描接口
    assert "scanDisclosureDay(date)" not in js
    assert "/api/scan/disclosure-day" not in js


def test_old_diagnostics_hash_still_resolves():
    js = Path("web/app.js").read_text(encoding="utf-8")

    # 旧的 #/diagnostics 链接不失效：落到工作台并展开折叠区
    assert 'parts[0] === "diagnostics"' in js
    assert "expandDiagnostics" in js
    assert 'el("adv-diagnostics").open = true' in js
    assert "scrollIntoView" in js
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_frontend_diagnostics.py -q --basetemp=.pytest_tmp`

Expected: `test_frontend_keeps_disclosure_diagnostics_in_advanced_fold` FAIL（`scanDisclosureDay(date)` 仍在 `app.js` 中，Task 6 才删）；`test_old_diagnostics_hash_still_resolves` FAIL（`expandDiagnostics` 还不存在）。

- [ ] **Step 3: `parseHash` 加 diagnostics 分支**

`web/app.js` 第 334-343 行的 `parseHash()` 替换为：

```js
function parseHash() {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const parts = raw.split("/").filter(Boolean);
  if (parts[0] === "day" && parts[1]) return { view: "workbench", date: parts[1] };
  if (parts[0] === "company" && parts[1] && parts[2]) {
    return { view: "company", tsCode: parts[1], period: parts[2] };
  }
  /* 扫描诊断已降为工作台折叠区，旧链接落到工作台并展开该区 */
  if (parts[0] === "diagnostics") return { view: "workbench", expandDiagnostics: true };
  if (VIEWS.includes(parts[0])) return { view: parts[0] };
  return { view: "workbench" };
}
```

- [ ] **Step 4: `applyRoute` 处理展开**

`web/app.js` 第 345-361 行的 `applyRoute()` 替换为：

```js
async function applyRoute() {
  const route = parseHash();
  activateView(route.view);

  if (route.expandDiagnostics) {
    el("adv-diagnostics").open = true;
    el("adv-diagnostics").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (route.date) {
    el("disclosure-date").value = toInputDate(route.date);
    if (!state.bundle || state.bundle.date !== route.date) {
      await loadDisclosureDay(route.date);
    }
    return;
  }
  if (route.tsCode) {
    el("company-ts-code").value = route.tsCode;
    ensurePeriodOption(route.period);
    await loadCompany(route.tsCode, route.period);
  }
}
```

- [ ] **Step 5: 跑测试确认部分通过**

Run: `python -m pytest tests/test_frontend_diagnostics.py -q --basetemp=.pytest_tmp`

Expected: `test_old_diagnostics_hash_still_resolves` PASS；`test_frontend_keeps_disclosure_diagnostics_in_advanced_fold` 仍 FAIL（等 Task 6 删 wrapper）。不要在这里 commit。

---

## Task 6: 清理死 wrapper

**Files:**
- Modify: `tests/test_frontend_contracts.py`（两个函数）
- Modify: `web/app.js:146-168`（三个 wrapper）

- [ ] **Step 1: 改断言使其失败**

`tests/test_frontend_contracts.py` 全文替换为：

```python
from pathlib import Path


def test_frontend_defines_api_wrapper_methods():
    content = Path("web/app.js").read_text(encoding="utf-8")

    assert "analyzeCompany(tsCode, period)" in content
    # 披露日扫描走 job 三件套；一次性的旧 wrapper 已无调用点，已清理
    assert "startDisclosureDayJob(date)" in content
    assert "getDisclosureDayJob(jobId)" in content
    assert "cancelDisclosureDayJob(jobId)" in content
    assert "analyzeDisclosureDay(date)" not in content
    assert "scanDisclosureDay(date)" not in content
    assert "disclosureDayBundle(date)" not in content
    assert "sendFeishuDisclosureDay(date)" in content
    assert "pollRss()" in content
    assert "/api/analyze/company" in content
    assert "/api/disclosure-day/jobs" in content
    assert "/api/notify/feishu/disclosure-day/" in content
    assert "/api/rss/poll" in content
    assert "if (!response.ok)" in content
    assert "catch (error)" in content


def test_frontend_has_minimal_real_data_controls():
    content = Path("web/index.html").read_text(encoding="utf-8")

    assert "company-ts-code" in content
    assert "company-period" in content
    assert "analyze-company" in content
    assert "disclosure-date" in content
    # 两个重复的扫描入口已合并为一个
    assert "start-disclosure-scan" in content
    assert "send-feishu" in content
    # RSS 与操作日志移入开发者折叠区，未删除
    assert "poll-rss" in content
    assert "operation-status" in content
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_frontend_contracts.py -q --basetemp=.pytest_tmp`

Expected: `test_frontend_defines_api_wrapper_methods` FAIL，`assert "analyzeDisclosureDay(date)" not in content` 断言失败。

- [ ] **Step 3: 删掉三个无调用 wrapper**

`web/app.js` 第 146-168 行，从 `api` 对象中删除这三个方法：

```js
  async analyzeDisclosureDay(date) {
    return requestJson("/api/analyze/disclosure-day", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date }),
    });
  },

  async scanDisclosureDay(date) {
    return requestJson("/api/scan/disclosure-day", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date }),
    });
  },

  async disclosureDayBundle(date) {
    return requestJson("/api/disclosure-day/bundle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date }),
    });
  },
```

删除后 `api` 对象中 `analyzeCompany` 的下一个方法应为 `startDisclosureDayJob`。

后端路由 `/api/analyze/disclosure-day`、`/api/scan/disclosure-day`、`/api/disclosure-day/bundle` **保留不动**——它们有后端测试覆盖，也可能被 CLI 使用。

- [ ] **Step 4: 跑全部前端测试**

Run: `python -m pytest tests/test_frontend_contracts.py tests/test_frontend_diagnostics.py tests/test_frontend_productization.py -q --basetemp=.pytest_tmp`

Expected: 全部 PASS。Task 5 遗留的那条断言此时也应转绿。

- [ ] **Step 5: 确认无残留引用**

Run: `grep -n "stopDisclosureScanButton\|scan-disclosure-day\|analyze-disclosure-day\|view-diagnostics\|tab-diagnostics" web/app.js web/index.html`

Expected: 无输出。

- [ ] **Step 6: 提交**

```bash
git add web/app.js tests/test_frontend_contracts.py tests/test_frontend_diagnostics.py
git commit -m "refactor: drop unused disclosure day api wrappers"
```

---

## Task 7: 浏览器行为验证

pytest 只做字符串断言，无法证明页面真的能跑。这一步用 Playwright headless 验证实际行为。harness 建在仓库外，跑完删除。

**Files:**
- 无仓库内文件改动（除非发现 bug 需要修）

- [ ] **Step 1: 确认 Playwright 可用**

Run: `python -c "import playwright; print('ok')"`

若报 `ModuleNotFoundError`，先装：

```bash
python -m pip install playwright && python -m playwright install chromium
```

- [ ] **Step 2: 起本地服务**

在仓库根目录另开一个后台进程：

```bash
python -m uvicorn copilot.api.dev_app:app --host 127.0.0.1 --port 8099
```

用 demo app（`dev_app`）而非 `real_app`：它不需要 Tushare token，且 job store 是内存态，验证 UI 结构足够。

- [ ] **Step 3: 写 harness**

写到仓库外，例如 `/tmp/te-verify/check.py`：

```python
import json
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8099"
problems = []
logs = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.on("console", lambda m: logs.append(f"console.{m.type}: {m.text}"))
    page.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))

    page.goto(BASE, wait_until="networkidle")

    # 1. 无 console / pageerror
    if logs:
        problems.append(f"console/pageerror 非空: {logs}")

    # 2. 侧栏三个 tab
    tabs = page.locator('.nav button[role="tab"]').count()
    if tabs != 3:
        problems.append(f"侧栏 tab 数应为 3，实际 {tabs}")

    # 3. 折叠区默认收起
    for fold in ["adv-diagnostics", "adv-developer"]:
        if page.locator(f"#{fold}").evaluate("el => el.open"):
            problems.append(f"#{fold} 默认应收起")

    # 4. 折叠区可展开
    page.locator("#adv-diagnostics > summary").click()
    if not page.locator("#adv-diagnostics").evaluate("el => el.open"):
        problems.append("#adv-diagnostics 点击后未展开")
    page.locator("#adv-diagnostics > summary").click()

    # 5. 扫描按钮初始为 idle
    state = page.locator("#start-disclosure-scan").get_attribute("data-state")
    if state != "idle":
        problems.append(f"扫描按钮初始 data-state 应为 idle，实际 {state}")
    if page.locator("#start-disclosure-scan").inner_text().strip() != "开始扫描":
        problems.append("扫描按钮初始文案应为「开始扫描」")

    # 6. 导出菜单：默认收起、点击展开、Esc 关闭
    if page.locator("#export-menu-json").is_visible():
        problems.append("导出菜单默认应收起")
    page.locator(".menu__trigger").click()
    if not page.locator("#export-menu-json").is_visible():
        problems.append("导出菜单点击后未展开")
    if page.locator(".menu__trigger").get_attribute("aria-expanded") != "true":
        problems.append("导出菜单展开后 aria-expanded 应为 true")
    page.keyboard.press("Escape")
    if page.locator("#export-menu-json").is_visible():
        problems.append("Esc 未关闭导出菜单")

    # 7. #/diagnostics 深链接落到工作台并展开诊断区
    page.goto(f"{BASE}#/diagnostics", wait_until="networkidle")
    page.wait_for_timeout(400)
    if page.locator("#view-workbench").is_hidden():
        problems.append("#/diagnostics 未落到工作台")
    if not page.locator("#adv-diagnostics").evaluate("el => el.open"):
        problems.append("#/diagnostics 未展开诊断折叠区")

    # 8. 三个视口无横向溢出
    for width in [1440, 1920, 430]:
        page.set_viewport_size({"width": width, "height": 900})
        page.wait_for_timeout(200)
        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        if overflow > 0:
            problems.append(f"{width}px 横向溢出 {overflow}px")

    browser.close()

print(json.dumps({"problems": problems, "logs": logs}, ensure_ascii=False, indent=2))
sys.exit(1 if problems else 0)
```

- [ ] **Step 4: 跑 harness**

Run: `python /tmp/te-verify/check.py`

Expected: `{"problems": [], "logs": []}`，退出码 0。

若有 `problems`，逐条修 `web/` 下源文件，重跑本步骤直到清空。修完后要重跑 Task 6 Step 4 的 pytest 确认没回退。

- [ ] **Step 5: 关服务、删 harness**

```bash
rm -rf /tmp/te-verify
```

并停掉 Step 2 起的 uvicorn 进程。

- [ ] **Step 6: 跑全量测试确认无连带影响**

Run: `python -m pytest -q --basetemp=.pytest_tmp`

Expected: `152 passed`（与改动前基线一致）。前端改动不应影响任何后端测试；若数字变化，说明动到了不该动的文件。

- [ ] **Step 7: 若有修复则提交**

```bash
git add web/
git commit -m "fix: address browser verification findings"
```

若 Step 4 一次通过、无文件改动，跳过本步。

---

## Task 8: 归档到开发日志

**Files:**
- Modify: `docs/development-log.md`

- [ ] **Step 1: 写归档段落**

在 `docs/development-log.md` 的 `## 2026-07-31` 之下、`### 前端产品化 spec 分解` 之前插入：

```markdown
### Spec 1 落地：扫描入口与信息架构收口

对应 spec：`docs/superpowers/specs/2026-07-31-scan-entry-consolidation-design.md`

已完成：

- 侧栏从 4 tab 降为 3 tab，扫描诊断不再是顶级视图。
- 「生成披露日汇总」与「扫描诊断」合并为单一「开始扫描」。两者原本调用同一条链路
  （同一 `loadDisclosureDay()`、同一 job、同一份 bundle），差别只是最终落在哪个视图，
  因此合并未改变任何扫描行为。
- 扫描按钮改为单节点三态 `idle / scanning / cancelling`，扫描期间原地变「停止扫描」，
  空闲态不再常驻一个永远灰着的按钮。原先分散在两个 catch 分支与 `finishDisclosureJob()`
  中的三处 disabled 重置，收敛到 `setScanState()`。
- 扫描诊断与开发者工具（RSS 触发 / 披露季复盘 / 原始操作日志）各成一个原生 `<details>`
  折叠区，默认收起。两区语义分开：诊断回答业务问题「这家为何没出卡」，开发者区是系统内部状态。
- 折叠区是 `index.html` 里的静态 `<details>` 包住原有容器，容器 id 全部未变，
  因此 `renderDiagnostics()` / `loadQuarterly()` / `setStatus()` 一行未改。
- `#/diagnostics` 保留为深链接：落到工作台、展开诊断区、滚动到位。扫描完成后不自动展开，
  因为数据问题家数已在工作台「数据问题」分章报出。
- 导出 JSON / CSV 收进顶栏「导出 ▾」菜单，新增 `web/components.js` 放这个唯一需要 JS 的原语。
- 删除 `api.analyzeDisclosureDay` / `api.scanDisclosureDay` / `api.disclosureDayBundle`
  三个已无调用点的 wrapper。后端对应路由保留，它们有后端测试覆盖且可能被 CLI 使用。

验证：

```bash
python -m pytest tests/test_frontend_contracts.py tests/test_frontend_diagnostics.py tests/test_frontend_productization.py -q --basetemp=.pytest_tmp
```

只跑前端三个测试文件，因为同期有后端在途改动，全量基线不干净。

另用 Playwright headless 验证（harness 建在仓库外，跑完删除）：console / pageerror 为 0、
侧栏 3 tab、折叠区默认收起且可展开、扫描按钮初始 `idle`、导出菜单 Esc 可关、
`#/diagnostics` 深链接落到展开态、1440 / 1920 / 430px 无横向溢出。

完整无障碍结论需真实读屏软件与人工评审，此处只覆盖可自动测量部分。
```

把上面代码块里的 pytest 命令保留为 fenced code block（注意嵌套：写入文件时它是普通的 ```bash 块）。

- [ ] **Step 2: 提交**

```bash
git add docs/development-log.md
git commit -m "docs: archive scan entry consolidation"
```

---

## Self-Review

**Spec 覆盖核对：**

| Spec 小节 | 对应 Task |
| --- | --- |
| 1. 信息架构（3 tab / 两折叠区 / 纵向顺序） | Task 1、2 |
| 1. `VIEWS` 收缩 + `parseHash` diagnostics 分支 + `applyRoute` 展开 | Task 1 Step 5、Task 5 |
| 2. 顶栏四控件 + 入口合并 + 停止扫描原地替换 + `setScanState` | Task 3 |
| 2. 导出下拉 | Task 4 |
| 3. 折叠区静态 `<details>`、render 函数不动 | Task 2 |
| 4. `createMenuButton` 单原语 + `components.js` | Task 4 |
| 5. 数据流不变 | 无独立 Task（Task 2/3 均不改 render 函数体与轮询逻辑；Task 7 Step 4 验证页面仍可跑） |
| 6. wrapper 清理，后端路由保留 | Task 6 |
| 7. 错误处理保持现状 | Task 3 Step 6（catch 分支只换 disabled 重置方式，`notify` / `setStatus` 不动） |
| 测试：三个文件的断言调整 | Task 1、2、3、4、5、6 各自的 Step 1 |
| 验证：pytest + Playwright | Task 6 Step 4、Task 7 |

无遗漏。

**命名一致性核对：**

- `setScanState(state)`：Task 3 定义，Task 3 Step 6 三处调用，Task 3 Step 1 断言，签名一致。
- `scanButton`：Task 3 Step 5 定义，Step 6、Step 7 使用，一致。
- `createMenuButton({ mount, label, items })`：Task 4 Step 3 定义，Step 6 按此签名调用（`mount` / `label` / `items`，每项含 `id` / `label` / `onSelect`），一致。
- `#adv-diagnostics` / `#adv-developer`：Task 2 创建，Task 2/5 断言，Task 5 Step 4 与 Task 7 引用，一致。
- `#start-disclosure-scan`：Task 3 创建，Task 3 Step 5 引用，Task 6 Step 1 与 Task 7 断言，一致。
- `#export-menu-mount`：Task 3 Step 3 创建占位，Task 4 Step 6 消费，Task 4 Step 1 断言，一致。
- `expandDiagnostics`：Task 5 Step 3 产出，Step 4 消费，Step 1 断言，一致。

**已知的中间红态**（有意为之，不是缺陷）：

- Task 1 结束时测试是红的——容器已从 HTML 删除但折叠区还没建。Task 2 结束回绿。Task 1 Step 6 明确写了不要 commit。
- Task 5 结束时 `test_frontend_keeps_disclosure_diagnostics_in_advanced_fold` 仍红——它断言 `scanDisclosureDay(date)` 不在 `app.js` 中，而 wrapper 到 Task 6 才删。Task 5 Step 5 明确写了不要 commit，Task 6 Step 4 转绿。

---

## 不在本计划范围内

- **续扫能力。** 停止后再次扫描是整轮重跑，已抓过的公司会重复请求 Tushare。后端无 cursor / resume 机制（grep `pause|resume|cursor|paused|continue_from|skip_existing` 零命中）。按钮文案保持「开始扫描」不变，避免现在改、后端做完又改回。
- **job 恢复与 history**（Spec 2）
- **复核状态后端化、后端导出接口**（Spec 3）
- **飞书 interactive card + callback**（Spec 4）
