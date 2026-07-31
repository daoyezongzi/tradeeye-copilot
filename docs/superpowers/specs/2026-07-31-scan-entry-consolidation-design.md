# 扫描入口与信息架构收口

**日期：** 2026-07-31
**范围：** 前端（`web/`）+ 前端契约测试（`tests/test_frontend_*.py`）
**不改：** 后端 service 层、API 路由、job 状态机

## 背景

前端在功能上已经跟上后端的 job 化扫描，但信息架构还停留在能力堆叠阶段：顶栏挤了 7 个控件，侧栏 4 个 tab 里有一个是给开发者看的诊断表，两个主按钮调用的是同一条链路。

本 spec 是前端产品化四个 spec 中的第一个，只处理不依赖新后端接口的部分：

| Spec | 主题 | 依赖 |
| --- | --- | --- |
| **1（本文）** | 扫描入口与信息架构收口 | 无 |
| 2 | job 恢复与 history | 需新增 job 列表接口 |
| 3 | 复核状态后端化 + 后端导出接口 | 需新增持久层与路由 |
| 4 | 飞书 interactive card + callback | 需新增卡片渲染与 callback 路由 |

## 现状认定

以下四点为读码核实结果，是本 spec 的设计前提。

**两个扫描入口行为重合。** `web/app.js:1128` 的「生成披露日汇总」走 `navigate('#/day/${date}')` → `applyRoute()` → `loadDisclosureDay(date)`；`web/app.js:1137` 的「扫描诊断」直接调 `loadDisclosureDay(date)` 再 `navigate('#/diagnostics')`。同一函数、同一 job、同一份 bundle，唯一差别是最终落在哪个视图。合并入口不改变任何扫描行为。

**诊断数据一直在渲染。** `finishDisclosureJob()`（`web/app.js:956`）已经同时调用 `renderSummary` / `renderCards` / `renderDiagnostics` 三者。诊断从独立视图降为折叠区，只改渲染目标容器，不改数据获取。

**三个 API wrapper 已无调用点。** grep `api.` 全量调用后确认，`web/app.js` 中只有 `api.analyzeCompany`（第 1021 行）与 `api.pollRss`（第 1166 行）被真正调用。以下三个 wrapper 为死代码：

- `api.analyzeDisclosureDay`（第 146 行）
- `api.scanDisclosureDay`（第 154 行）
- `api.disclosureDayBundle`（第 162 行）

**停止扫描后无法续扫。** grep `copilot/` 全目录的 `pause|resume|cursor|paused|continue_from|skip_existing` 零命中。`analyze_disclosure_day_bundle()`（`copilot/service/analyzer.py:104`）每次从 `calendar.fetch_events()` 拿全量事件从头遍历，无起始偏移参数；取消走 `break` 出循环后用已完成的 `results` 出 partial bundle；job 状态机只有 `running / completed / cancelled / failed`，无 `paused`。因此停止后再次扫描是整轮重跑，已抓过的公司会重复请求 Tushare。

## 设计

### 1. 信息架构

侧栏从 4 tab 降为 3 tab：

```
披露日研判   ← 主视图
单票研判
复核队列
```

工作台视图纵向顺序：

```
扫描进度条（扫描中可见）
报头 + 导语 + 分布条 + 数字条        ← 不变
研判明细（按严重度分章）              ← 不变
─────────────────────────────
▸ 高级诊断                          ← 新增，默认收起
    覆盖池 / 披露 / OK / 待数据 / 不完整 / 错误 六格
    逐家原因表（代码·名称·报告期·行业·状态·原因）
▸ 开发者                            ← 新增，默认收起
    RSS 触发（轮询按钮）
    披露季复盘（指标格）
    操作日志（最近一次接口原始返回）
─────────────────────────────
colophon 数据来源说明                ← 不变
```

两个折叠区不合并：高级诊断回答业务问题「这家公司为什么没出卡」，属于分析结果；开发者区是系统内部状态，与当日研判结论无关。

代码改动：

- `VIEWS` 从 `["workbench","company","review","diagnostics"]` 减为前三项，`VIEW_TITLES` 同步
- `parseHash()` 新增分支：`parts[0] === "diagnostics"` 返回 `{ view: "workbench", expandDiagnostics: true }`
- `applyRoute()` 在 `expandDiagnostics` 为真时展开诊断折叠区并滚动到位

`#/diagnostics` 保留为深链接，旧链接不失效。扫描完成后两个折叠区都不自动展开——数据问题家数已在工作台「数据问题」分章报出，自动展开等于把刚降级的内容推回主位。

### 2. 顶栏

四个常驻控件，竖线左侧为「产出数据」，右侧为「分发数据」：

```
披露日研判  ····  [2025-08-21]  [开始扫描]  │  [导出 ▾]  [预览飞书摘要]
```

**入口合并。** `#analyze-disclosure-day` 与 `#scan-disclosure-day` 并为单一 `#start-disclosure-scan`，点击后 `navigate('#/day/${date}')`，与现「生成披露日汇总」行为一致。

**停止扫描原地替换。** `#stop-disclosure-scan` 不再作为常驻 disabled 按钮存在。扫描期间「开始扫描」原地变为「停止扫描」（filled → outlined），结束后变回。

实现为单 button 切 `data-state`（`idle` / `scanning`）加切文案与 class，不用两节点互相 hide——两节点方案需在两处同步 disabled 状态，而当前 bug 面正在此处：`web/app.js:1004`、`:1012` 两个 catch 分支与 `finishDisclosureJob()` 各自手动重置 `disabled`，共三处重复。统一收敛为 `setScanState('idle'|'scanning')`，三处调用同一函数。这是收拢已重复三遍的代码，不是新增抽象。

**导出下拉。** `#export-menu-json` / `#export-menu-csv` 收进单个 `[导出 ▾]`，展开后两项。

按钮文案保持「开始扫描」，不改为「重新扫描」：续扫能力待后端 resume 就绪后一并处理，现在改文案会在后端完成后再改回。

### 3. 折叠区实现方式

折叠区在 `web/index.html` 中静态声明为原生 `<details>` + `<summary>`，把现有容器原样包进去，**不新增 JS 工厂函数**：

```html
<details id="adv-diagnostics" class="fold">
  <summary>高级诊断<span class="fold__hint">每家覆盖池公司为什么出卡或未出卡</span></summary>
  <div class="fold__body">
    <div id="diagnostic-status"></div>     <!-- id 不变 -->
  </div>
</details>

<details id="adv-developer" class="fold">
  <summary>开发者<span class="fold__hint">系统内部状态，与当日研判结论无关</span></summary>
  <div class="fold__body">
    <button id="poll-rss" class="outlined">轮询 RSS</button>   <!-- id 不变 -->
    <div class="metric-grid" id="quarterly-review"></div>      <!-- id 不变 -->
    <pre id="operation-status" class="log"></pre>              <!-- id 不变 -->
  </div>
</details>
```

这与项目现有模式一致：`index.html` 静态声明所有视图、区块与 dialog，`app.js` 只往既有容器里填内容。因此 `renderDiagnostics()`、`loadQuarterly()`、`setStatus()`、RSS 按钮的事件绑定**全部无需改动**——它们通过 id 查找的元素依然存在，只是在 DOM 中的位置变了。

选原生 `<details>` 而非自行拼 div：键盘可达、`Ctrl+F` 可搜到收起区内文字、`prefers-reduced-motion` 无需特殊处理。自行实现需补 `aria-expanded` / `role` / 键盘监听。

深链接展开即 `el("adv-diagnostics").open = true` 加 `scrollIntoView()`，无需组件封装。

### 4. 组件

新文件 `web/components.js`，只放一个 UI 原语：

`createMenuButton({ label, items })` → 顶栏「导出 ▾」

需要 JS 是因为菜单项由数据驱动且要处理交互：点外部关闭、Esc 关闭、方向键在项间移动、`aria-haspopup="menu"`、`aria-expanded` 同步。

单独成文件而非塞进 `app.js`：`app.js` 已 1212 行，且 Spec 2 的 job history 也会用到菜单原语。

样式加在 `styles.css`，沿用现有 token：折叠区标题用 `--serif`，边框用 `--md-sys-color-outline-variant`，`<summary>` 的展开标记用 `--clay`——陶土橙已是导语竖线与焦点环的用色，折叠区指示器属同类「极小面积方向性强调」，不引入新颜色。

### 5. 数据流

数据流无变化，仅 DOM 位置变化：

```
[开始扫描] → navigate(#/day/YYYYMMDD) → applyRoute() → loadDisclosureDay(date)
  → startDisclosureDayJob → 1s 轮询 → finishDisclosureJob(job)
      ├→ renderSummary     → 报头
      ├→ renderCards       → 研判明细
      └→ renderDiagnostics → #diagnostic-status（元素不变，现位于折叠区内）
```

不碰 job 轮询逻辑、不碰 bundle 渲染逻辑、不碰任何 render 函数体。

### 6. wrapper 清理

从 `web/app.js` 删除 `api.analyzeDisclosureDay`、`api.scanDisclosureDay`、`api.disclosureDayBundle` 三个无调用 wrapper。

后端路由 `/api/analyze/disclosure-day`、`/api/scan/disclosure-day`、`/api/disclosure-day/bundle` 保留不动——它们有后端测试覆盖，也可能被 CLI 使用，删除超出本 spec 范围。

### 7. 错误处理

保持现状：失败走 `notify(msg, true)` + `setStatus({error})`，原始返回落在开发者区的操作日志。折叠区自身无网络请求，无新增失败模式。

## 测试

改三个现有测试文件，不新增测试文件。

`tests/test_frontend_productization.py`

- `test_workbench_information_architecture_has_four_views` 改为三视图断言，函数名同步改为 `..._has_three_views`
- 新增断言：`id="adv-diagnostics"` 与 `id="adv-developer"` 两个 `<details>` 存在于 `index.html`
- `test_exports_cover_csv_and_json` 现断言 `id="export-menu-csv"` / `id="export-menu-json"` 存在于 `index.html`；导出项改由 `createMenuButton` 在 JS 中创建后，这两个 id 移入 `app.js`，断言目标随之从 `html` 改为 `js`。id 本身保持不变，`exportBundleCsv` / `exportBundleJson` / `csvCell` 转义等其余断言不动。

`tests/test_frontend_diagnostics.py`

- 移除 `scan-disclosure-day` 与 `scanDisclosureDay(date)` 断言
- 改为断言诊断折叠区容器存在且 `renderDiagnostics` 仍在，即能力未丢失

`tests/test_frontend_contracts.py`

- 移除 `analyzeDisclosureDay(date)`、`analyze-disclosure-day`、`/api/analyze/disclosure-day` 断言
- 换为 job 三件套断言（`startDisclosureDayJob` / `getDisclosureDayJob` / `cancelDisclosureDayJob`）
- `poll-rss` 断言保留：RSS 只是移位到开发者区，未删除

## 验证

```bash
python -m pytest -q --basetemp=.pytest_tmp
```

基线为当前 144 passed，改动后应仍全绿。

另按 P2 改版的既有做法，用 Playwright headless 在仓库外建 harness 跑一遍，跑完删除 harness：

- console / pageerror 为 0
- 1440 / 1920 / 430px 无横向溢出
- 折叠区展开收起可交互
- `#/diagnostics` 深链接落到诊断展开态
- 对比度仍过 WCAG AA 正文 4.5:1

完整无障碍结论需真实读屏软件与人工评审，此处只覆盖可自动测量部分。

## 已知限制

- 停止扫描后再次扫描是整轮重跑，已抓过的公司会重复请求 Tushare。续扫需后端支持 `resume_from_job_id` 或 `skip_ts_codes`，待后端就绪后单独处理。
- 复核状态仍在 localStorage，非权威状态（Spec 3 处理）。
- 导出仍为前端内存导出（Spec 3 处理）。
- 飞书仍为文本预览/发送，无 interactive card（Spec 4 处理）。
- 刷新后无法恢复正在跑或刚跑完的 job（Spec 2 处理）。
