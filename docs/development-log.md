# TradeEye Copilot 开发日志

## 2026-07-31

### 阶段归档：后端披露扫描收口与前端待办盘点

本轮主要解决后端可观测、可停止、可恢复的披露日扫描问题，并对前端剩余产品化工作做了一轮盘点。

后端已收口：

- 披露日扫描已从同步长请求改为 job 化流程，支持 `POST /api/disclosure-day/jobs`、`GET /api/disclosure-day/jobs/{job_id}`、`POST /api/disclosure-day/jobs/{job_id}/cancel`。
- `AnalyzerService` 支持扫描进度回调和取消检查，能在公司开始、公司完成、取消时上报状态。
- `TushareFundamentalsClient` 支持表级阶段回调，当前可观察到 `fetch_income / fetch_balancesheet / fetch_cashflow / fetch_indicator`。
- job 状态已落 SQLite `disclosure_jobs`，包含当前公司、当前报告期、当前阶段、进度、日志、取消标记和最终 partial/full bundle。
- 取消语义是安全停止，不是强杀请求；已发出的单次 Tushare HTTP 请求会等返回后在下一安全点停止。

前端盘点结论：

- 当前前端实现的是「停止扫描」，不是「暂停 / 继续」。如需 pause/resume，需要后端新增暂停状态、扫描游标和 resume API，不能只加按钮。
- 「扫描诊断」不是多余能力，但作为顶级 tab 对普通用户偏重，建议改为主扫描页里的高级诊断折叠区。
- 「生成披露日汇总」和「扫描诊断」两个入口都围绕同一 disclosure-day job 流程，建议合并成一个主扫描入口，完成后同页展示汇总和诊断摘要。
- RSS 触发、原始操作日志、季度复盘更像高级/开发者入口，正式产品中应默认隐藏或折叠。
- 后端已有 job SQLite 持久化，但前端还没有 job history、刷新后恢复正在跑/刚跑完 job 的 UI。
- 复核队列仍偏 localStorage，本地可用但不是权威状态；后续应迁到后端 SQLite / D1 / API。

后端剩余待执行项：

- 如果要真正支持 pause/resume，需要升级 job 状态机、持久化扫描 cursor，并改造 Analyzer 从指定 cursor 续扫。
- 如果要进入多人/生产环境，需要补 job 多用户隔离、旧 job 清理、后台任务队列替代 FastAPI `BackgroundTasks`。
- 如果要形成业务闭环，需要补后端复核状态存储、后端导出接口、飞书 interactive card callback。
- 行业规则与正式 benchmark 仍未完成：银行 NIM/NPL/拨备覆盖率/资本充足率、券商/保险/地产/公用事业规则包，以及代表性正式覆盖池多披露日阈值校准。

### 阶段归档：可停止披露扫描闭环

本阶段围绕“大覆盖池扫描时要实时知道 Tushare 抓到哪，并能中途停止”完成闭环：

- 扫描入口从长请求改为 job 流程，前端拿 `job_id` 后轮询进度。
- 后端记录当前公司、报告期、Tushare 表级阶段、已处理家数、OK / 数据问题数量、耗时和日志。
- Tushare 拉表阶段已细化到 `fetch_income / fetch_balancesheet / fetch_cashflow / fetch_indicator`。
- 前端新增「停止扫描」按钮；取消在公司之间和表之间的安全点生效，已完成结果继续保留。
- job 状态已落 SQLite `disclosure_jobs`，服务重启后可恢复状态、取消标记和最终 partial/full bundle。
- 本阶段对应提交：`55d45ef`、`789946a`、`ab34f9b`、`64be51b`。

当前边界：

- 已发出的单次 Tushare HTTP 请求不能硬中断，只能等该表请求返回后停。
- 前端仍是 1 秒轮询，未升级 SSE / WebSocket。
- job 暂无多用户隔离、权限控制和旧记录清理策略。
- 后台执行仍用 FastAPI `BackgroundTasks`，尚未引入生产级队列。

验证：

```bash
python -m pytest -q --basetemp=.pytest_tmp
```

结果：

```text
144 passed
```

### 披露日扫描 job SQLite 持久化

在实时进度与停止能力之上，把 job 状态从纯内存升级为 SQLite 持久化：

- 新增 `SQLiteDisclosureJobStore`，复用应用 SQLite 路径，建表 `disclosure_jobs`。
- 持久化字段包括 `job_id / date / status / cancel_requested / started_at / payload`。
- `payload` 保存完整 `DisclosureJobStatus`，包含当前公司、当前阶段、进度、日志与最终 partial/full bundle。
- `cancel_requested` 单独落列，服务重启后仍能恢复取消标记。
- `RealReportService` 已从内存 `DisclosureJobStore` 切换到 `SQLiteDisclosureJobStore`，demo app 仍保持内存态。
- 用 wall-clock `time()` 记录 `started_at`，避免 `monotonic()` 跨进程恢复后失真。

验证：

```bash
python -m pytest -q --basetemp=.pytest_tmp
```

结果：

```text
144 passed
```

### 披露日扫描实时进度与停止

把披露日扫描从“一次长请求等全部 Tushare 拉完”改为可观察、可停止的 job 流程：

```http
POST /api/disclosure-day/jobs
GET  /api/disclosure-day/jobs/{job_id}
POST /api/disclosure-day/jobs/{job_id}/cancel
```

已实现：

- 后端新增内存 `DisclosureJobStore`，记录 `running / completed / cancelled / failed`、已处理家数、总数、当前公司、当前报告期、当前阶段、OK 数、数据问题数、耗时、最近日志与最终 partial/full bundle。
- FastAPI 启动 job 后立即返回 `job_id`，扫描任务放入 `BackgroundTasks`，前端不再被长请求阻塞。
- `AnalyzerService.analyze_disclosure_day_bundle()` 支持 `progress_callback` 与 `should_cancel`，每家公司开始/完成时上报进度，取消后保留已完成结果。
- `TushareFundamentalsClient` 增加表级 stage：`fetch_income / fetch_balancesheet / fetch_cashflow / fetch_indicator`，因此 UI 能显示正在抓哪家公司、哪张表。
- 取消不是强杀线程，而是在公司之间、Tushare 表之间检查 cancel flag；已完成公司保留，未完成部分不硬填假结果。
- 前端新增「停止扫描」按钮，披露日扫描改为 start job + 1 秒轮询，完成/取消后仍渲染 summary、cards、diagnostics。

验证：

```bash
python -m pytest -q --basetemp=.pytest_tmp
```

结果：

```text
143 passed
```

### P2 工作台改版：研报式信息架构 + Anthropic 色板

在 `artifacts/ui-preview/` 下先做了四个独立方向的原型（终端 / 研报排版 / 深色控制台 / Claude 设计语言），
用真实 `/api/disclosure-day/bundle` 返回渲染，按真实内容密度比对后选定方向 D 落地。

结构变更（`web/index.html`）：

| 原来 | 现在 | 理由 |
| --- | --- | --- |
| 顶部 segmented 切视图 | 左侧固定侧栏切视图 | 顶栏腾出来放当日操作，视图入口不再和操作按钮抢位置 |
| 汇总面板 + 指标卡 | 报头 + 导语 + 分布条 + 数字条 | 一句话先说清今天优先追问谁，而不是让读者自己扫五个数字 |
| 公司卡网格 | 可展开行，默认只展开最高分那条 | 覆盖池上百家时卡片网格会变成读不完的瀑布 |
| emoji 严重度（🔴🟡⚪⚠️） | 文字标签 + 色条（RED / YELLOW / OK） | emoji 在不同平台字形不一致，也不是可靠的语义载体 |
| 未见异常逐张出卡 | 压成一行名单 | 未触发规则的公司只需要知道数量和是谁 |

色板换成 Anthropic 公开 brand-guidelines 的取值（`#141413` / `#faf9f5` / `#d97757` / `#e8e6dc` / `#f0eee6`）。
token 名仍沿用 M3 的 color role 体系——M3 本身就是「给 role 赋值」的机制，因此这是用 M3 的语义层
承载品牌色，不是两套体系拼接。

陶土橙不做按钮底色。实测三种方案：

```text
白字 / 陶土橙底           3.12:1  不达标
深墨字 / 陶土橙底         5.90:1  达标但橙底黑字观感脏
暖白字 / 深墨底          17.50:1  采用
```

要让白字在橙底达标得把橙压到 `#b85736`，那已经不是品牌色了。所以陶土橙退回纯强调位：
品牌标记、导语竖线、焦点环、次级按钮 hover 描边、进度条。

严重度三色按「压在自己 tint 底上当文字」这个最差情形定值，而不是按页面底：

```text
--sev-red    #b04026  on tint 5.22:1   on paper 5.53:1
--sev-yellow #815d18  on tint 5.45:1   on paper 5.68:1
--sev-ok     #52663e  on tint 5.62:1   on paper 5.94:1
```

修掉两个实测才发现的问题：

- `.view { display: flex }` 盖掉了浏览器默认的 `[hidden] { display: none }`，四个视图同时渲染在页面上，
  窄屏下被诊断表格顶出横向滚动。改为全局 `[hidden] { display: none !important }` 兜住。
- 进度条完成后仍在滚动，会被读成还在跑。`stop()` 现在切到 `data-mode="done"`，填满且停止动画。

尺度上调一档：正文 14 → 15px，报头 30 → 34px，数字条 28 → 32px，控件高 34 → 36px，
内容区上限 1080 → 1320px。1440 视口减去侧栏还有 1188px，原来卡在 1080 会在右侧留一条空白。
散文仍由各自的 62ch measure 约束，放宽上限只让表格、事实分格和数字条铺开。

验证（Playwright headless，harness 建在仓库外并在跑完后删除）：

```text
console / pageerror                    0
横向溢出 1440 / 1920 / 430px           无
1440px 右侧空白                        110px → 0
折叠交互（点第二行）                   open 1 → 2
对比度最低值 浅色 4.89 / 暗色 5.47     全部过 WCAG AA 正文 4.5:1
python -m pytest -q                   134 passed
```

契约测试未作改动即通过：`--md-sys-color-*`、`--space-2: 8px`、`backdrop-filter`、
`@keyframes indeterminate`、`prefers-reduced-motion`、`.seg-*` 等断言在新色板下仍然成立。

完整无障碍结论需要真实读屏软件与人工评审，这里只覆盖了可自动测量的部分。

### P0 规则质量与评估闭环推进

本轮按“规则质量优先、自动化后置”的新优先级补齐了评估侧可落地闭环，不新增臆造行业规则。

已实现：

- `eval/manual_review_template.csv` 从 `ts_code,period,rule_id,label,notes` 扩为 `ts_code,period,rule_id,label,notes,severity,industry`，前端复核导出同步携带最高严重度与行业路由，便于人工复核结果回流分组统计。
- `copilot.eval.manual_review.compute_precision_breakdown()`：在 overall precision 之外，输出 `by_rule`、`by_severity`、`by_industry` 三组 precision；仍只统计 `TRUE / FALSE`，忽略 `UNREVIEWED`。
- `BacktestSummary` 增加 `severity_distribution` 与 `industry_distribution`，benchmark 不只看规则命中数量，也能看红/黄分布与行业样本分布。
- `copilot.eval.real_backtest.summarize_scan_failures()`：对多日 disclosure scan 的非 OK 事件按 `status`、`industry`、`message` 聚合，支持后续用真实失败原因驱动规则包。

验证：

```bash
python -m pytest -q --basetemp=.pytest_tmp
```

结果：

```text
134 passed
```

### 日期选择器与视觉细化

披露日从手输 `YYYYMMDD` 文本框改为原生日期选择器：

```html
<input id="disclosure-date" type="date" value="2025-08-21" />
```

接口契约与 hash 路由仍是 `YYYYMMDD`，因此在边界转换而不是改后端：

```text
toApiDate("2025-08-21") → "20250821"   控件 → 接口 / #/day/{date}
toInputDate("20250821") → "2025-08-21" 接口 / 路由 → 控件
selectedDate()                          统一读取入口，空值直接提示
```

`el("disclosure-date").value.trim()` 的四处直读全部换成 `selectedDate()`，避免再出现某一处忘记转换。控件同时设 `max` 为今天——未来日期不可能有已披露财报。

报告期同理改为 `<select>`：法定季末只有 0331 / 0630 / 0930 / 1231，倒序列出近四年且不超过今天的季末（当前 14 项）。路由带入的报告期若不在选项内，`ensurePeriodOption()` 会补插并选中，因此 `#/company/{ts_code}/{period}` 仍可直接打开任意历史期。

视觉上补的是层次而不是装饰：

| 变化 | 依据 |
| --- | --- |
| 概览面板独立为 `.overview`，顶部红→黄→绿渐变色带 | M3 强调数据面板需要视觉锚点，色带直接对应严重度语义 |
| 严重度分布条按各段数量分配 `flex-grow` | 在读数字之前先给出一眼可见的比例 |
| 30px 渐变品牌图标 + 内嵌高光 | Apple 图标的浅景深处理 |
| 全部数字改 `tabular-nums` | 刷新时数字不跳动 |
| 多层柔和阴影替换单层硬阴影 | HIG 的浅景深，而非 Material 的硬投影 |
| 过滤 chip 选中态反色 | 选中态靠明度对比而不是描边 |
| 日期 / 下拉自绘控件样式与聚焦环 | 抹平各平台原生控件差异 |
| 视图、卡片、弹窗、snackbar 入场动画 | 均在 `prefers-reduced-motion` 下关闭 |

Playwright 复验：

```text
控件：type=date，值 2025-08-21，接口收到 20250821，hash #/day/20250821
分布条：seg-red grow=2 / seg-yellow 2 / seg-ok 1 / seg-data 1
报告期：SELECT，14 项，首项 2026 半年报（未到的季末已排除）
飞书预览：495 字符 25 行，webhook 未配置时确认按钮禁用
控制台错误：0（明色 / 暗色）
窄屏 430px：横向溢出 0px
```

```bash
python -m pytest -q --basetemp=.pytest_tmp
```

结果：

```text
132 passed
```

新增 3 个契约测试：日期选择器与转换函数、报告期下拉边界、概览分布条。

### P2 前端产品化已完成

新增后端支撑接口：

```http
GET  /api/meta
POST /api/disclosure-day/bundle
POST /api/notify/feishu/disclosure-day/{date}/preview
```

- `/api/meta`：覆盖池数量、`company_names`、`tushare_ready`、`feishu_ready`。只返回布尔就绪位，不返回 token / webhook 值。
- `/api/disclosure-day/bundle`：一次调用同时返回 `summary` 与 `scan`，前端不再为了拿诊断而二次扫描。
- `/preview`：渲染正式飞书摘要但不发送，返回 `text` / `sendable` / `reason`，供发送前确认。

`dev_app` demo 数据由 1 家扩为 6 家，覆盖红 2 / 黄 2 / 未见异常 1 / 数据问题 1，使分组视图和飞书摘要可在本地预览。

P2 清单实现情况：

| 项 | 实现 |
| --- | --- |
| 正式摘要预览 + 发送确认 | 预览弹窗展示全文与字符/行数；`sendable=false` 时禁用确认按钮；发送只能经确认触发 |
| 红/黄/数据问题分组视图 | 按 severity 分组渲染，数据问题以诊断表呈现；chips 可筛选 |
| 公司名称展示 | 公司卡、诊断表、复核表、飞书摘要统一走 `company_names` |
| 扫描进度与耗时提示 | M3 indeterminate 进度条 + 实时已用时；完成后显示总耗时 |
| 导出 CSV/JSON | 披露日 bundle 导出 JSON 与合并 CSV；复核单独导出 |
| 稳定 URL | `#/day/{date}`、`#/company/{ts_code}/{period}`，支持 hashchange 与直接打开 |
| 复核状态 UI | 公司卡上标注有效/误报，localStorage 持久化，导出列与 `eval/manual_review_template.csv` 对齐 |
| 信息架构与视觉 | 工作台 / 公司 / 复核 / 诊断 四视图 + 半透明顶栏 |

### 前端设计基线

颜色角色沿用 Material Design 3 的 `--md-sys-color-*` 命名（surface-container 层级、on-* 前景、outline-variant 描边）；字体栈、8pt 栅格与「功能层半透明、内容层不透明」的分层规则取自 Apple HIG materials 指南。进度条按 M3 规定在时长未知时用 indeterminate 动画，不伪造百分比，并遵守 `prefers-reduced-motion`。明暗双色通过 `prefers-color-scheme` 切换。

### 前端验证方式

除 pytest 契约测试外，用 jsdom 与 Playwright 真实渲染 demo 服务验证：

```text
控制台错误：0（明色 / 暗色）
分组：🔴 2 / 🟡 2 / ⚪ 1 / ⚠️ 1
公司名称：石大胜华、航天机电、浙江新能、哈森股份、金鹰股份
飞书预览：495 字符 25 行，webhook 未配置时确认按钮禁用
依据溯源弹窗：59ms 内打开并渲染 Evidence
复核标注：写入 localStorage，精确率指标同步
导出：tradeeye-20250821.csv / .json / manual_review.csv
诊断表：6 行，message 经 escapeHtml，无原始 script 标签
窄屏 430px：单列，无横向溢出
```

截图存于 `artifacts/ui-preview/`（该目录已被 `.gitignore` 忽略）。

```bash
python -m pytest -q --basetemp=.pytest_tmp
```

结果：

```text
129 passed
```

### 本轮仍未做

- 飞书交互卡片 / 按钮 callback：预览与发送确认仍在 Web 端，飞书侧仍是静态文本。
- 复核标注仍存浏览器 localStorage，尚未落库；但前端导出已可回流 `eval/` 做按规则、严重度、行业分组 precision。
- 稳定 URL 是前端 hash 路由，不是可分享的服务端渲染详情页。
- 前端未做真实 Tushare 大覆盖池压测；进度条为 indeterminate，因为后端未提供逐家进度事件。
- 导出为前端内存数据导出，未提供后端导出接口。

### 当前剩余待办

#### P0：规则质量与评估闭环

- 行业规则优先：银行目前只做了 hard-check 分流，尚未实现净息差、不良率、拨备覆盖率、资本充足率等真实银行指标。
- 其他行业规则包：券商、保险、地产、公用事业等仍待真实失败样本驱动，不预先臆造规则。
- 阈值校准：对现有应收、存货、现金流、毛利率、利润/营收背离等规则跑真实披露季 benchmark，识别误报与漏报；当前已能输出规则、严重度、行业分布。
- 人工复核 precision：前端导出已携带 `severity / industry`，`eval` 已支持 overall / by_rule / by_severity / by_industry precision；下一步是用真实复核 CSV 跑样本。
- 规则证据质量：每条 finding 继续保留可复核 Evidence，避免 LLM 或文本归因替代算术规则。

#### P0：正式覆盖池与样本扫描

- 当前 100 支仍是烟测池，需要替换为真实关注股票池，并通过 watchlist loader 校验公司名与行业路由。
- 用正式覆盖池跑多披露日 scan，输出 `OK / DATA_NOT_READY / DATA_INCOMPLETE / ERROR` 分布与失败原因；当前已有多日 scan count 与 failure grouping helper，待接真实扫描产物。
- 根据真实失败样本决定下一批行业规则，不按行业名称预先臆造。
- 后端已支持单次 `DisclosureAnalysisBundle` 复用，但真实大覆盖池还需要记录耗时、Tushare 调用次数、重试次数与失败分布。

#### P1：飞书摘要与详情承载

- 当前飞书正式发送仍是 webhook 静态文本，已支持长文本分段，但最终不应依赖多段长文本阅读。
- 下一步产品形态应改为短摘要 + Top 风险 + 全量异常入口；是否升级 interactive card 放在规则质量稳定之后。
- 稳定详情 URL：当前是 hash route；正式飞书摘要需要可公网访问的详情页 URL。
- 后端导出接口未做：目前 CSV/JSON 由前端内存导出，后续应提供后端导出以支撑邮件/飞书/归档。

#### P2：部署与交互闭环

- 前端静态托管：可用 GitHub Pages 或 Cloudflare Pages；若 Worker 也在 Cloudflare，Cloudflare Pages 更顺。
- Python 分析后端部署：当前 FastAPI / Tushare / pandas / SQLite 不建议迁到 Cloudflare Worker；应部署到 Render、Railway、Fly.io、轻量云服务器等 Python 友好的平台。
- 飞书交互卡片：规则质量稳定后再做 interactive card。
- Cloudflare Worker callback：按钮点击回调放到 Cloudflare Worker，提供公网 HTTPS callback。
- Cloudflare D1 复核表：存储 `date / ts_code / period / rule_id / user / action / timestamp`，替代浏览器 localStorage 作为权威状态。
- 飞书回调安全：需要校验飞书签名或 verification token，处理重复点击、幂等与异常响应。
- 复核状态回流：前端与后端读取 D1 或同步后的 review 状态，进入人工复核 precision 链路。
- Secrets 管理：`TUSHARE_TOKEN`、`FEISHU_WEBHOOK`、飞书 App Secret、Cloudflare 绑定均走环境变量或平台 secret，不写入仓库。

#### P3：自动化与归因

- 自动触发下一步再做：scheduler、系统定时任务、RSS retry queue、失败重试 daemon 均暂后置。
- PDF / LLM 归因仍未接入真实卡片；接入前需满足 PDF 获取、章节抽取、token/latency 预算与失败降级 gate。

## 2026-07-30

### Real Data Disclosure Event 已完成

对应提交：

- `5effb84 feat: load real data runtime settings`
- `39ad7d6 feat: create tushare client from environment token`
- `fb55a94 feat: cache latest analysis reports`
- `3b3d78e feat: analyze real company fundamentals`
- `7f5a841 feat: analyze disclosure day summaries`
- `77c3bf1 feat: expose analysis API routes`
- `190b09f feat: wire real data app startup`
- `68d5c8a feat: classify financial report rss announcements`
- `05e04d1 feat: poll rss announcements as trigger hints`
- `c17b381 feat: expose rss poll API`
- `49a544e feat: expose feishu disclosure notification API`
- `60d03af feat: add frontend real data API controls`
- `54e8ac3 fix: harden real data disclosure workflow`

已实现：

- `.env` 自动加载，`TUSHARE_TOKEN` / `FEISHU_WEBHOOK` 只从环境读取，不打印值。
- 真实 Tushare client factory：缺 token 抛明确错误。
- `AnalyzerService.analyze_company(ts_code, period)`：拉本期、上季、去年同期四表快照，落 SQLite，装配 Context，执行 hard checks 和规则，返回 `CompanyAnalysisResult`。
- `AnalyzerService.analyze_disclosure_day(date)`：调用 Tushare `disclosure_date`，按 `eval.coverage_pool` 过滤，对命中公司批量跑单票分析并生成 `DailySummary`。
- `ReportCache`：缓存最近单票 card 和披露日 summary，供 API / 飞书复用。
- RSS trigger hint：解析 RSS item，识别正式财报标题，排除摘要/更正/补充/英文版；RSS 只作为 trigger，结构化财务数据仍走 Tushare。
- 飞书静态文本推送 API：`POST /api/notify/feishu/disclosure-day/{date}`。
- 真实 app：`copilot.api.real_app:app`。
- Windows 启动脚本：`start_real.bat`。
- 前端最小真实接口控件：单票研判、披露日汇总、发送飞书、轮询 RSS。

新增 API：

```http
POST /api/analyze/company
POST /api/analyze/disclosure-day
POST /api/rss/poll
POST /api/notify/feishu/disclosure-day/{date}
```

### 真实 smoke 发现

已确认 `.env` 存在，且运行时能识别：

```text
tushare_token_configured=True
feishu_webhook_configured=True
coverage_pool=['000001.SZ']
```

真实单票 smoke：

```text
POST /api/analyze/company
{"ts_code": "000001.SZ", "period": "20250630"}
```

结果：

```text
status=DATA_NOT_READY
has_card=False
```

原因不是“没财报”，而是当前通用规则模型依赖的字段对银行股不适配：

- `income` 返回了营收、归母净利。
- `cashflow` 返回了经营现金流。
- `balancesheet` 中 `accounts_receiv` / `inventories` 对银行为空。
- `fina_indicator` 中 `grossprofit_margin` 对银行为空。

结论：当前 MVP 规则更适合非金融企业；银行股需要单独的银行规则集，例如净息差、不良率、拨备覆盖率、资本充足率等。现阶段 hard check 拒绝出卡是为了避免用不适配字段生成误导性结果。

披露日 smoke：

```text
POST /api/analyze/disclosure-day
{"date": "20250821"}
```

Tushare `disclosure_date(ann_date="20250821")` 返回 16 条披露事件，但当前 `coverage_pool` 只有 `000001.SZ`，该日无平安银行披露，因此：

```text
coverage_count=1
disclosed_count=0
cards=[]
```

飞书因此不会发送，属于 `no_disclosures` 行为。

### 当前结论

- 真实链路已经接通，但需要选择合适的非金融披露样本完成“出卡 + 飞书”烟测。
- `000001.SZ` 不适合作为当前通用规则 smoke 样本；应临时使用 `20250821` 当天披露的非金融公司，例如 `601012.SH`、`600438.SH` 等，再观察四表字段完整性。
- 下一步目标：不改正式 `config.yaml` 的前提下，用临时 service/临时 coverage pool 找到一个可出卡样本，并真实触发一次飞书 webhook 静态文本推送。

### 飞书真实烟测

在不修改正式 `config.yaml` 的前提下，使用临时 coverage pool 从 `20250821` 的 Tushare 披露事件中寻找可出卡样本。

烟测结果：

```text
CANDIDATE_COUNT=16
SELECTED_TS_CODE=920056.BJ
SELECTED_PERIOD=20250630
SMOKE_STATUS=CARD_READY
FINDING_COUNT=0
MAX_SEVERITY=None
SUMMARY_DISCLOSED_COUNT=1
SUMMARY_CARD_COUNT=1
FEISHU_SENT=True
FEISHU_REASON=ok
```

结论：

- 单票真实 Tushare 抓取 + 分析可以出卡。
- 披露日汇总可以在临时 coverage pool 下生成 `DailySummary`。
- 飞书 webhook 静态文本推送已真实发送成功。
- 当前正式配置仍只有 `000001.SZ`，因此日常披露日汇总是否发送取决于 coverage_pool 是否包含当日实际披露公司。

### 下一阶段待办：正式覆盖池与行业规则

正式覆盖池推进思路：

```text
配置正式 coverage_pool
→ 按披露日批量扫描真实样本
→ 记录每家公司状态：OK / DATA_NOT_READY / DATA_INCOMPLETE / ERROR
→ 按失败原因归类：字段缺失、行业不适配、Tushare 接口异常、规则阈值问题
→ 与行业规则集一起修复
```

已知待办：

- 正式 `coverage_pool` 配置：当前只有 `000001.SZ`，需要换成真实关注股票池。
- 行业规则集：银行股已确认不适配通用工商企业规则；后续可能还会遇到券商、保险、地产、公用事业等行业，需要按真实扫描结果分层处理。
- Hard checks 分层：当前 hard check 偏通用企业，后续要按行业/字段可用性调整，避免“有财报但因行业字段为空不出卡”。
- 披露日诊断输出：需要更清楚展示每个覆盖池公司为什么没出卡，而不是只返回 cards。
- RSS 真实 feed 配置：当前 `rss.feeds` 为空；`rss.company_names` 也需要随覆盖池维护。
- 飞书交互卡片：当前只做 webhook 静态文本，尚未做按钮、复核、callback。
- 自动触发：当前是手动 API/前端按钮，尚未做 scheduler、系统定时任务或 retry daemon。
- PDF / LLM 归因接入真实卡片：当前真实 card 归因仍是降级/占位，未接真实财报 PDF 管理层讨论章节。
- CLI 入口：尚未做命令行触发披露日汇总/飞书推送。
- 真实回测：尚未跑正式覆盖池披露季 benchmark、人工复核 precision。

下一阶段优先目标：

- 先走正式 `coverage_pool`。
- 扫描真实披露日，收集失败样本和行业分布。
- 不预先臆造行业规则，先用真实失败原因驱动银行/其他行业规则集修复。

### 100 支临时覆盖池扫描烟测

在不提交正式 `config.yaml` 股票池、不打印任何 secret 的前提下，用 Tushare 真实数据临时构造 100 支覆盖池：

- 扫描日期：`20250825`
- 构造方式：取当日 `disclosure_date(ann_date="20250825")` 返回披露事件中的前 100 个去重 `ts_code`
- 行业映射：通过 `stock_basic` 辅助识别；该批样本均按 `generic` 路由

扫描结果：

```text
TEMP_COVERAGE_COUNT=100
DISCLOSED_COUNT=100
OK_COUNT=100
DATA_NOT_READY_COUNT=0
DATA_INCOMPLETE_COUNT=0
ERROR_COUNT=0
```

结论：

- 新增披露日诊断链路可以处理 100 支临时真实覆盖池。
- 该批 `20250825` 非银行样本没有触发字段缺失或行业不适配问题。
- 银行 hard check 已先做最小分流，避免继续用毛利率、应收账款、存货字段误拒银行上下文。
- 复测 `000001.SZ / 20250630`，在显式 `bank` 路由下已从 `DATA_NOT_READY` 变为 `OK` 并成功生成 card。
- 这批 100 支已按用户要求写入 `config.yaml` 作为正式烟测池，后续仍应替换为真实关注股票池。

### 飞书正式摘要实发验证

使用正式飞书摘要路径实发一次：

```text
POST /api/notify/feishu/disclosure-day/20250825
STATUS_CODE=200
sent=True
reason=ok
```

本次正式摘要规模：

```text
TEXT_CHARS=5195
TEXT_LINES=191
RED=69
YELLOW=18
DATA_PROBLEMS=0
```

结论：

- 飞书正式摘要发送成功。
- 正式摘要会发送全部红色/黄色异常公司；未见异常公司只汇总数量，不逐条展开。
- 本次样本没有数据问题事件，因此 `DATA_PROBLEMS=0`。
- 当前发送耗时偏长不是因为 LLM；真实卡片仍未接 LLM。
- 耗时主因是 100 家覆盖池逐家拉 Tushare 三期四表，且正式发送路径当前会先 `analyze_disclosure_day()` 再 `scan_disclosure_day()`，存在重复分析风险。
- 后续性能优化应改为一次 disclosure scan 复用 `CompanyAnalysisResult`，同时生成 `DailySummary` 和 diagnostics，再直接渲染飞书。

### Watchlist replacement path

The current 100-stock pool is a smoke pool. The production replacement path should use a YAML watchlist with:

```yaml
coverage_pool:
  - 000001.SZ
company_names:
  000001.SZ: 平安银行
company_industries:
  000001.SZ: bank
```

The backend loader validates that every code has both a display name and an industry route before replacing the smoke pool.

### Industry rule pack gate

The current smoke pool does not provide enough concrete industry-specific failure samples to implement another rule pack safely. Do not add securities, insurance, real-estate, utilities, or true bank metric rules until a real sample identifies the exact Tushare fields and expected finding logic.

### PDF / LLM attribution gate

Do not connect LLM attribution into real Feishu cards until these gate conditions are met:

- Stable source PDF retrieval for the exact report announcement.
- Deterministic extraction of management discussion text.
- Token/latency budget measured on at least 20 real cards.
- Attribution text remains evidence-linked and never replaces arithmetic rule findings.
- If LLM call fails, card still sends with rule evidence.

### Backend Feishu completion self-review

Completed in this phase:

- Formal Feishu disclosure renderer: total summary, all red/yellow abnormalities, data-problem events, normal-company count.
- Real notify path now combines `DailySummary` with `DisclosureScanResult`.
- Company display names are available through `eval.company_names`.
- Frontend intentionally unchanged in this phase.

Still not done:

- Feishu interactive card/buttons/callback.
- Stable hosted detail URL for every disclosure day.
- True industry-specific bank metrics such as NIM/NPL/provision coverage/capital adequacy.
- Other industry rule packs for securities, insurance, real estate, utilities.
- Scheduler/retry daemon/RSS retry queue.
- PDF/LLM management discussion attribution in real cards.
- Formal replacement of the smoke 100-stock pool with the user's true watchlist.


```bash
python -m pytest -q --basetemp=.pytest_tmp
```

结果：

```text
90 passed
```

```bash
cmd.exe //C "python -m pip install -e .[dev]"
```

结果：

```text
Successfully installed tradeeye-copilot-0.1.0
```

---

## 2026-07-29

### 当前定位

TradeEye Copilot 的主线是面向买方研究员的 A 股财报披露即时研判系统。核心价值不是“总结财报”，而是在披露高峰期帮助研究员发现值得优先追问的异常，并提供可复核依据。

当前实现状态：

- 工程骨架、规则内核、Web demo、评估 scaffold、飞书 webhook 底层能力已完成。
- 真实外部数据主链路尚未完全接通。
- 昇腾真实端点暂未接入，保留 OpenAI-compatible `LLMClient` 适配层。

---

## 已完成内容

### 1. 计划与设计文档

已提交：

- `docs/superpowers/specs/2026-07-29-tradeeye-copilot-design.md`
- `docs/superpowers/plans/2026-07-29-tradeeye-copilot-core.md`
- `docs/superpowers/plans/2026-07-29-tradeeye-copilot-narrative-web.md`
- `docs/superpowers/plans/2026-07-29-tradeeye-copilot-evaluation-delivery.md`

对应提交：

- `f86a5e4 docs: add TradeEye Copilot implementation plans`

### 2. 数据与规则内核

对应提交：

- `f32971c feat: implement TradeEye Copilot core rules`

已实现：

- `PeriodSnapshot`
- `Context`
- `Evidence`
- `Finding`
- `Severity`
- SQLite store：财务快照与 findings 持久化
- Tushare 四表标准化：
  - `income`
  - `balancesheet`
  - `cashflow`
  - `fina_indicator`
- 披露日历事件标准化
- 硬校验层
- 规则协议与注册表
- 6 条算术规则：
  - 应收账款增速背离
  - 存货增速背离
  - 现金流质量
  - 毛利率异动
  - 利润与营收方向背离
  - 非经常性损益占比

当前规则层特点：

- LLM 不参与算术。
- 每条 finding 携带 Evidence。
- 规则测试均为纯函数测试，便于回归。

### 3. Narrative / LLM / Web demo

对应提交：

- `65559ab feat: add narrative API and web dashboard`

已实现：

- OpenAI-compatible `LLMClient`
- `ASCEND_API_KEY` 环境变量读取
- PDF 管理层讨论章节抽取
- 管理层语气退坡 finding
- FastAPI app factory
- demo API service
- 静态 Web dashboard
- Evidence 弹窗
- 季度复盘展示区

当前 Web 说明：

- 目前前端看到的是 `copilot/api/dev_app.py` 中的 demo 数据。
- 尚未接入真实 Tushare 输入表单与动态分析 API。

### 4. 评估与交付 scaffold

对应提交：

- `cf40e29 feat: add evaluation delivery workflow`

已实现：

- `BacktestCompanyResult`
- `BacktestSummary`
- benchmark summary 聚合
- 人工复核 CSV 读取
- precision 计算
- `eval/run_backtest.py`
- `eval/manual_review_template.csv`
- 飞书 webhook text sender
- 飞书 daily summary 文本渲染
- `/api/quarterly`
- README
- `docs/submission-checklist.md`

当前评估说明：

- `eval/run_backtest.py` 当前是 deterministic scaffold。
- 尚未跑真实覆盖池披露季。
- `artifacts/benchmark.json` 为本地生成文件，已被 `.gitignore` 忽略。

### 5. 一键启动脚本

对应提交：

- `a8af6b0 chore: add demo startup script`

已实现：

- `start_demo.bat`

行为：

1. 进入项目根目录。
2. 执行 `python -m pip install -e .[dev]`。
3. 打开 `http://127.0.0.1:8000/`。
4. 启动：
   ```bash
   python -m uvicorn copilot.api.dev_app:app --reload --host 127.0.0.1 --port 8000
   ```

### 6. Editable install bug 修复

对应提交：

- `01d5be2 fix: restrict package discovery for editable install`

问题：

`start_demo.bat` 执行：

```bash
python -m pip install -e .[dev]
```

时报错：

```text
Multiple top-level packages discovered in a flat-layout: ['web', 'eval', 'copilot', 'artifacts']
```

根因：

- `pyproject.toml` 未限制 setuptools 包发现。
- setuptools 将 `web/`、`eval/`、`copilot/`、`artifacts/` 都识别为顶层包。

修复：

```toml
[tool.setuptools.packages.find]
include = ["copilot*"]
exclude = ["web*", "eval*", "artifacts*", "docs*", "tests*"]
```

同时 `.gitignore` 增加：

```gitignore
*.egg-info/
```

---

## 最近验证结果

已验证：

```bash
python -m pytest -q --basetemp=.pytest_tmp
```

结果：

```text
58 passed
```

已验证 Windows cmd 下 editable install：

```bash
cmd.exe //C "python -m pip install -e .[dev]"
```

结果：

```text
Successfully installed tradeeye-copilot-0.1.0
```

---

## 当前未完成项

### 1. 真实 Tushare 单票闭环

尚未完成：

```text
ts_code + period
→ Tushare 拉三期数据
→ 落 SQLite
→ assemble Context
→ hard checks
→ run rules
→ build company card
→ 前端展示
```

这是下一阶段最关键的主链路。

### 2. 披露日汇总真实链路

尚未完成：

```text
date
→ disclosure_date
→ 过滤 coverage_pool
→ 对实际披露公司批量研判
→ build_daily_summary
→ 前端展示
→ 飞书推送
```

产品逻辑应为“披露日触发”，不是自然日每日推送。

### 3. 前端真实接口适配

当前前端仍依赖 demo service。

下一阶段应增加：

- 单票分析输入框：`ts_code` + `period`
- 披露日分析输入框：`date`
- API wrapper：
  - `analyzeCompany(tsCode, period)`
  - `analyzeDisclosureDay(date)`
  - `sendFeishuDisclosureDay(date)`

不做美化，重点是接口清晰，方便后续替换前端。

### 4. 飞书推送入口

当前已有底层：

- `FeishuNotifier`
- `render_daily_summary_text`

尚未完成：

- API 触发入口
- CLI 触发入口
- 前端按钮
- 真实 webhook 发送验证

推荐下一阶段先做静态 webhook 推送，不做交互卡片 callback。

### 5. 昇腾真实接入

已保留：

- `LLMClient`
- `ASCEND_API_KEY`
- `llm.base_url`
- `llm.model`

尚未完成：

- 真实昇腾端点测试请求
- 归因摘要接入真实 report builder
- 推理延迟和 token 统计

用户当前说明：除昇腾以外，其他资源已准备好。因此下一阶段先绕开昇腾真实调用，保持 LLM 降级占位。

---

## 待决策：RSS 触发是否纳入

用户提出：是否考虑“RSS 收到财报就发”，或直接保留为不做。

当前判断：

### 方案 A：不做 RSS，保留 disclosure_date 触发

优点：

- 与原 spec 一致。
- 数据来源结构化，稳定。
- 不需要解析公告标题与 RSS 延迟问题。
- 更容易做覆盖池过滤和回测。

缺点：

- 触发不如 RSS 直观。
- 如果 Tushare disclosure_date 更新慢，可能不够“即时”。

### 方案 B：RSS 作为补充触发，不作为主链路

设计：

```text
RSS 收到疑似财报公告
→ 解析 ts_code / 公告标题 / 时间
→ 只作为 trigger hint
→ 真正财务数据仍走 Tushare 结构化接口
→ 若 Tushare 财务表尚未更新，则进入待重试队列
```

优点：

- 更贴近“公告刚落地”。
- 可展示“事件触发”感。

缺点：

- 需要处理误报、标题解析、公告类型判断、重试队列。
- 容易扩大 scope。

### 当前推荐

下一阶段先做：

```text
手动触发单票 + 手动触发披露日汇总 + 飞书静态推送
```

RSS 暂时记录为扩展方向。

如果后续要补 RSS，建议只作为 trigger hint，不替代 Tushare 结构化数据链路。

---

## 下一阶段建议

名称：

```text
real-data-disclosure-notify
```

目标：

```text
把 demo 数据替换为真实 Tushare 单票与披露日汇总链路，并补齐飞书推送入口。
```

范围：

- 真实 Tushare client factory
- `.env` 自动加载
- `AnalyzerService`
- 单票 API
- 披露日 API
- 飞书推送 API
- 前端表单与 API wrapper
- CLI 手动触发披露日汇总/推送
- 测试覆盖缺 token、无披露、字段缺失、飞书未配置等场景

不做：

- 昇腾真实调用
- RSS 自动触发
- 飞书交互卡片 callback
- 应用内常驻 scheduler
- 前端美化
