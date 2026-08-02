# TradeEye Copilot

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-teal.svg)](https://fastapi.tiangolo.com/)

**TradeEye Copilot** 是面向买方研究员（PM / 分析师）的 A 股财报披露即时研判系统。财报落地后，系统输出**结构化财务事实**、**规则驱动的异常发现**、**可溯源的依据**、**归因摘要**与**市场上下文**——而不是又一份需要读完的财报摘要。

> 简体中文 | [English](README.en.md)

---

## 目录

- [这是什么](#这是什么)
- [为什么这样设计](#为什么这样设计)
- [核心设计原则](#核心设计原则)
- [功能特性](#功能特性)
- [架构](#架构)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
- [配置参考](#配置参考)
- [规则引擎](#规则引擎)
- [飞书推送](#飞书推送)
- [自动化调度](#自动化调度)
- [LLM 使用（外部 LLM API）](#llm-使用外部-llm-api)
- [Agent 事实契约](#agent-事实契约)
- [评估与基准](#评估与基准)
- [项目结构](#项目结构)
- [测试](#测试)
- [合规边界](#合规边界)
- [相关项目](#相关项目)
- [文档与参考](#文档与参考)

---

## 这是什么

TradeEye Copilot 是专为买方机构打造的轻量级协同投研助手。披露高峰期研究员不缺财报摘要，缺的是**优先级排序**与**可复核的异常发现**。

本项目把主线从"总结财报"改为"**找出值得追问的问题**"。

系统覆盖可配置的覆盖池（默认 **100 家 A 股公司**），每个工作日扫描披露日历事件，运行确定性财务校验，并交付：

- **当日汇总**：按异常严重度排序的公司全量覆盖视图
- **公司研判卡**：事实 → 异常 → 归因 → 市场四层结构
- **依据溯源**：每条 finding 携带 `Evidence(source, field, period, value)`，可下钻到原始数值
- **季度复盘**：覆盖池、披露数、命中数与规则分布
- **飞书推送**：正式披露摘要文本推送至群聊

## 为什么这样设计

| 问题 | TradeEye Copilot 的解法 |
| --- | --- |
| 严肃金融场景下 LLM 处理数字会幻觉 | **LLM 永不接触算术**。财务数字来自 Tushare + pandas，经脚本级硬校验；LLM 只做措辞判断与文字归因 |
| 多 Agent 动态协商耗时、耗 token | **单次分析聚合**：一次扫描同时产出当日汇总与扫描结果，飞书/Web 不再重复请求 Tushare |
| Chatbot 对话框有 Prompt 门槛 | **零 Prompt 主路径 + 可选 Agent**：Web 工作台一键扫描、原位刷新；Agent 浮层按当前研判卡答疑，并在执行重抓/重扫前要求研究员确认 |
| 硬校验失败会静默降质 | **硬门禁**：数据不完整或交叉验算失败时阻断研判卡，而不是伪造"未见异常" |

## 核心设计原则

1. **确定性管道优先**。所有核心财务指标由确定性代码提取并交叉校验，准确率不依赖模型运气。
2. **依据胜过断言**。每条异常 finding 绑定 `Evidence(source, field, period, value)`，UI 可下钻查看。
3. **单次分析**。披露日分析聚合一次，Web / 飞书 / 自动化全部复用结果。
4. **可恢复、可取消的扫描**。披露扫描 job 化并持久化到 SQLite，部分运行可通过 `skip_ts_codes` 续扫；取消是公司/表间的安全停止。
5. **银行感知的规则**。银行走最小 hard-check 分支（不臆造行业规则），覆盖但不幻觉。
6. **事实是唯一接口**。`CompanyCard.facts` 是 Agent 交互的唯一事实接口；Agent 永不计算财务数字（见 [Agent 事实契约](#agent-事实契约)）。

## 功能特性

### 披露扫描
- 由 **Tushare 披露日历**触发；RSS 可选作为触发提示（`copilot/rss/announcements.py` 过滤财报标题，Tushare 未就绪时标记 `DATA_PENDING`）
- 每家公司拉取三期（本期 / 上季 / 去年同期）四张表（利润表 / 资产负债表 / 现金流量表 / 财务指标）
- **SQLite 持久化**：快照、job、复核标签、通知日志
- **可续扫 job store**：`POST /api/disclosure-day/jobs`、`resume_from_job_id`、`X-TradeEye-Owner` 隔离、前端 1 秒轮询

### 规则引擎（确定性算术）
六条算术规则，阈值来自 `config.yaml`（`rules.thresholds`）：

| 规则 | 触发条件 |
| --- | --- |
| 应收账款背离 | 应收账款增速与营收增速差值 ≥ 30 个百分点 |
| 存货背离 | 存货增速与营收增速差值 ≥ 30 个百分点 |
| 现金流质量 | 经营现金流 / 净利润 < 50% |
| 毛利率异动 | \|毛利率变化\| ≥ 5 个百分点 |
| 利润与营收方向背离 | 净利润与营收方向相反 |
| 非经常性损益占比 | 非经常性损益占净利润 ≥ 30% |

另有 **管理层语气退坡** finding（`management_tone_weakened`，YELLOW）：LLM 对比 PDF 管理层讨论章节与去年同期措辞产出。

### 研究工作台（Web）
- **当日汇总**——报头、导语、严重度分布条（红 / 黄 / OK / 数据问题）
- **公司研判卡**——名称优先展示，代码与报告期作为辅助标识；可展开，默认展开最高分卡片
- **单票研判**——输入股票代码与报告期，直接生成单家公司研判卡
- **Agent 浮层**——右下角小机器人入口，默认右侧停靠、可拖离/吸附；围绕当前卡片答疑，并可建议单票重抓或披露日重扫，执行前必须确认
- **依据溯源弹窗**——逐条 finding 展示原始 `Evidence` 数据
- **季度复盘**——覆盖池、披露数、命中数与规则分布；复核指标保留在后端评估能力中，不进入研究员前端主路径
- **诊断与开发者工具**——折叠区展示扫描状态、job、自动化联调与通知日志
- **导出**——JSON / CSV 菜单；深链 `#/day/{date}`、`#/company/{ts_code}/{period}`

### 飞书推送
- 正式披露摘要文本（总览 + 全部红/黄异常 + 数据问题；未见异常仅计数）
- **长文本分段**（`split_feishu_text`，3500 字符/段，带 `[i/n]` 头）
- 按日期**幂等去重**、**发送日志**、**预览**与**手动重发**接口
- 交互卡片 **callback** 端点（challenge / verification token 校验），无需公网入站 webhook

### 自动化
- `POST /api/automation/disclosure-day/cron`，由 `X-Automation-Token`（`AUTOMATION_TRIGGER_TOKEN`）保护
- GitHub Actions 工作流 `disclosure-automation.yml`：cron `"30 10 * * 1-5"`（工作日 10:30 UTC）+ `workflow_dispatch`（date / notify 输入）

## 架构

```text
披露日历 -> Context 装配 -> 硬校验 -> 规则引擎 -> 报告编排 -> Web / 飞书
                               \-> PDF 原文抽取 -> LLM 语气对比/归因
```

- **确定性管道**：Tushare → pandas → SQLite → 硬校验 → 规则。数字永不经过 LLM。
- **Narrative 模块**：从 PDF 抽取管理层讨论章节，用 OpenAI 兼容 LLM（温度 0.0）对比去年同期措辞，输出严格 JSON 的语气 finding，以 PDF 章节作为 Evidence。
- **API 层**：`create_app()` 工厂，`real_app`（正式版，真实服务）使用；demo 数据应用已移除。
- **前端**：零依赖原生 JS 工作台（`web/`），由 FastAPI 静态挂载，无构建步骤。

### 模块结构

```text
copilot/
├── api/            # FastAPI：real_app.py（正式入口）、app.py（create_app 工厂）
├── checks/         # reconcile：交叉验算 / 硬校验
├── datasource/     # tushare_client、calendar、fundamentals
├── eval/           # backtest 汇总、real_backtest、人工复核精确率
├── llm/            # OpenAI 兼容客户端，失败降级返回 None
├── narrative/      # PDF 抽取 + 语气对比
├── notify/         # 飞书渲染、长文本分段
├── report/         # 公司研判卡 / 季度复盘构建器
├── rss/            # 公告触发提示 + 轮询服务
├── rules/          # 算术规则引擎：base、divergence、caliber、registry
├── service/        # analyzer、disclosure_scan（单次聚合）、disclosure_jobs、review_store、notify_store
├── store/          # SQLite store
├── scheduler.py    # 自动化 cron 触发处理
├── watchlist.py    # 覆盖池 YAML 校验（代码 + 名称 + 行业）
└── models.py       # pydantic 模型：Context、Evidence、Finding、PeriodSnapshot……
```

## 快速开始

### 环境要求

- Python **≥ 3.11**
- [Tushare](https://tushare.pro/) Token（财务数据）
- *（可选）* OpenAI 兼容的 LLM 端点（语气 finding）
- *（可选）* 飞书自定义机器人 webhook（群推送）

### 安装

```bash
git clone git@github.com:daoyezongzi/tradeeye-copilot.git
cd tradeeye-copilot
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

### 配置

```bash
cp .env.example .env
```

填入密钥（详见 [配置参考](#配置参考)）：

```bash
TUSHARE_TOKEN=...
ASCEND_API_KEY=...            # 可选
FEISHU_WEBHOOK=...            # 可选
AUTOMATION_TRIGGER_TOKEN=...  # 可选，cron 接口需要
FEISHU_VERIFICATION_TOKEN=... # 可选，卡片 callback 需要
PUBLIC_BASE_URL=...           # 可选，部署实例的公网地址
```

非密钥配置在 `config.yaml`：覆盖池（100 家）、公司名、行业路由、规则阈值、LLM 端点、PDF 缓存、评估窗口。

### 运行

**Windows 一键启动：**

```bat
start_real.bat
```

脚本会安装依赖、打开 `http://127.0.0.1:8000/` 并启动：

```bash
python -m uvicorn copilot.api.real_app:app --reload --host 127.0.0.1 --port 8000
```

打开工作台后，点击任意 finding 的 `依据` 即可查看原始证据 JSON。

### 验证

```bash
pytest -q
```

## 使用指南

### 研究员操作流程（工作台）

1. 打开 `http://127.0.0.1:8000/`，进入披露日视图。
2. 选择披露日期，点击 **开始扫描**（可停止 / 取消 / 恢复——部分完成的 job 会持久化）。
3. **当日汇总**展示严重度分布条（红 / 黄 / OK / 数据问题）。
4. 点击公司行展开**研判卡**（事实 → 异常 → 归因 → 市场）。
5. 点击任意 finding 的 `依据` 打开**证据溯源弹窗**，查看精确的源数值。
6. 需要追问时，点击右下角小机器人打开 **Agent 浮层**；Agent 只基于当前卡片事实答疑，涉及重抓/重扫时会给出确认卡。
7. 点击 **预览飞书摘要** 检查文案，再点击 **发送**（未配置 webhook 时按钮禁用）。
8. 在**通知日志**中查看投递结果。

部署后，GitHub Actions cron（或任意调度器）调用[自动化接口](#自动化调度)，流程即可无人值守运行。

### API 速览

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/api/meta` | 应用元信息 / 能力 |
| `GET` | `/api/daily/{date}` | 某披露日（`YYYYMMDD`）的当日汇总 |
| `GET` | `/api/company/{ts_code}/{period}` | 公司研判卡 |
| `GET` | `/api/evidence/{ts_code}/{period}/{rule_id}` | 单条 finding 的证据 |
| `GET` | `/api/quarterly` | 季度复盘聚合 |
| `POST` | `/api/analyze/company` | 分析单家公司 |
| `POST` | `/api/analyze/disclosure-day` | 分析一个披露日（单次聚合） |
| `POST` | `/api/scan/disclosure-day` | 扫描一个披露日 |
| `POST` | `/api/disclosure-day/bundle` | 构建分析 bundle |
| `POST` | `/api/disclosure-day/jobs` | 启动可续扫的扫描 job |
| `GET` | `/api/disclosure-day/jobs` | 列出 jobs |
| `GET` | `/api/disclosure-day/jobs/{job_id}` | 查看 job 状态 |
| `POST` | `/api/disclosure-day/jobs/{job_id}/cancel` | 取消 job（安全停止） |
| `DELETE` | `/api/disclosure-day/jobs?keep_recent=N` | 清理历史 jobs |
| `GET` | `/api/reviews/labels.csv` | 内部评估：复核标签 CSV |
| `GET` | `/api/reviews/metrics` | 内部评估：precision 分解 |
| `POST` / `GET` | `/api/reviews/labels` | 内部评估：写入 / 列出复核标签 |
| `DELETE` | `/api/reviews/labels/{ts_code}/{period}/{rule_id}` | 内部评估：删除标签 |
| `POST` | `/api/rss/poll` | 轮询 RSS（触发提示） |
| `GET` | `/api/notify/logs?limit=20` | 通知发送日志 |
| `POST` | `/api/notify/feishu/callback` | 飞书交互卡片回调 |
| `POST` | `/api/notify/feishu/disclosure-day/{date}/preview` | 预览摘要文本 |
| `POST` | `/api/notify/feishu/disclosure-day/{date}` | 发送摘要到 webhook |
| `POST` | `/api/automation/disclosure-day` | 自动化触发（无 token） |
| `POST` | `/api/automation/disclosure-day/cron` | 自动化触发（需 `X-Automation-Token`） |

本地运行时可在 `http://127.0.0.1:8000/docs` 查看 FastAPI 交互式文档（OpenAPI）。

## 配置参考

### 环境变量（仅密钥）

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `TUSHARE_TOKEN` | 是 | Tushare 数据访问 Token |
| `ASCEND_API_KEY` | 否 | 外部 LLM API 密钥（语气对比） |
| `FEISHU_WEBHOOK` | 否 | 飞书自定义机器人 webhook（群推送） |
| `AUTOMATION_TRIGGER_TOKEN` | 否 | cron 自动化接口的访问令牌 |
| `FEISHU_VERIFICATION_TOKEN` | 否 | 飞书卡片回调校验令牌 |
| `PUBLIC_BASE_URL` | 否 | 卡片详情链接使用的公网地址（`notify.public_base_url`） |

`.env` 自动加载且环境变量优先；密钥只做存在性校验，绝不打印。

### config.yaml 配置节

| 配置节 | 作用 |
| --- | --- |
| `database` | SQLite 路径（默认 `data/tradeeye_copilot.sqlite`） |
| `tushare` | 超时 / 重试设置 |
| `llm` | OpenAI 兼容端点的 `base_url`、`model`、`timeout_seconds` |
| `narrative` | PDF 缓存目录、章节最大字符数 |
| `notify` | `feishu_enabled` 开关 |
| `eval` | `coverage_pool`（100 个代码）、`company_names`、`company_industries`、基准窗口与输出路径 |
| `rss` | 订阅源列表、`max_entries` |
| `rules.thresholds` | 六条算术规则的阈值 |

## 规则引擎

规则是 `copilot/rules/`（`divergence.py`、`caliber.py`、`base.py`）中的**纯算术纯函数**——不涉及 LLM。阈值在 `config.yaml` 中配置；数据不足时产出 `DATA_INCOMPLETE` / `NOT_EVALUATED` 状态，绝不伪造"未见异常"。银行通过最小 hard-check 分支（豁免应收 / 存货 / 毛利率规则）——不臆造行业逻辑。

## 飞书推送

- 由 `copilot/notify/feishu.py` 渲染（`render_formal_disclosure_text`）
- 长消息按 3500 字符分段，带 `[i/n]` 头
- 按日期幂等（一天一条）、发送日志落 SQLite、支持手动重发
- 交互卡片 callback 端点校验 verification token（challenge 式），无需公网入站 webhook

## 自动化调度

- GitHub Actions：`.github/workflows/disclosure-automation.yml`
  - cron `"30 10 * * 1-5"`（工作日 10:30 UTC）
  - `workflow_dispatch` 支持 `date` 与 `notify` 输入
  - 需要 Secrets `TRADEEYE_API_BASE_URL` 与 `AUTOMATION_TRIGGER_TOKEN`
- 工作流向 `/api/automation/disclosure-day/cron` 发送 `X-Automation-Token`；`copilot/scheduler.py` 分发披露日自动化（可选飞书推送）

## LLM 使用（外部 LLM API）

- `copilot/llm/client.py` —— OpenAI 兼容客户端；失败返回 `None`，管道优雅降级
- `copilot/narrative/extract.py` —— 从 PDF 抽取管理层讨论章节（缓存于 `narrative.pdf_cache_dir`）
- `copilot/narrative/tone.py` —— 温度 **0.0**、严格 JSON 输出，对比本期与去年同期措辞 → `management_tone_weakened` finding，以 PDF 章节为证据
- **护栏**：LLM 永不计算数字；规则与硬校验完全不含 LLM；归因只是*附加* finding，绝不替代规则证据

## Agent 事实契约

Agent 已接入研究员前端，作为悬浮问答层而不是一级导航页。契约核心（spec：[2026-08-01 Agent 事实契约设计](docs/superpowers/specs/2026-08-01-agent-fact-contract-design.md)、[2026-08-02 Agent 前端设计](docs/superpowers/specs/2026-08-02-agent-frontend-design.md)）：

- **`CompanyCard.facts` 是唯一事实接口**——Agent 不得从渲染文本反推数字
- `Fact` 状态：`VERIFIED`（必须 value + evidence，且 period/value 一致）/ `UNAVAILABLE` / `INVALID` / `NOT_APPLICABLE`
- 每条事实携带 `FactEvidence(evidence_id, source, field, period, value)` 溯源
- `RuleResultStatus`：`HIT` / `MISS` / `NOT_EVALUATED` / `BLOCKED`——数据不足不得用 `MISS` 冒充未见异常
- `CardStatus`：`OK` / `PARTIAL` / `BLOCKED`（局部阻断）
- Agent 回答不得反向覆盖 `facts` / `findings` / `rule_results`
- Agent 只建议 `refetch_company` / `rescan_disclosure_day` 两类动作；前端以确认卡执行既有分析接口，Agent 自身不写业务数据

## 评估与基准

- `eval/run_backtest.py` —— 确定性基准脚手架，输出 `artifacts/benchmark.json`
- `copilot/eval/real_backtest.py` —— 多日扫描聚合（`summarize_scan_counts`、按 status/industry/message 分组失败）
- `copilot/eval/manual_review.py` —— `compute_precision_breakdown()`：总体 / 按规则 / 按严重度 / 按行业；只计 TRUE/FALSE，`UNREVIEWED` 不计入
- `eval/manual_review_template.csv` —— 人工复核模板（`ts_code, period, rule_id, label, notes, severity, industry`）
- 复核标签与 precision 仍通过 `/api/reviews/*` 保留给内部评估；研究员前端不展示复核队列、标注明细或 CSV 入口

## 项目结构

```text
.
├── copilot/          # 后端包（API、服务、规则、存储、通知）
├── web/              # 原生 JS 前端工作台（index.html、app.js、components.js、styles.css）
├── eval/             # 基准 / 人工复核工具
├── tests/            # pytest + Node 前端测试套件（236 个 pytest，15 个 Node 测试）
├── config.yaml       # 非密钥配置
├── start_real.bat    # 一键本地启动（正式应用）
├── .github/workflows/disclosure-automation.yml
└── docs/             # 开发日志、spec 与 plan
```

## 测试

```bash
python -m pytest --basetemp=.pytest_tmp -q
npm test
node --check web/app.js && node --check web/agent-chat.js && node --check web/agent-panel.js
```

当前主分支验证规模：236 个 pytest、15 个 Node 前端测试。套件覆盖 API 路由、规则算术、披露扫描 bundle、job store 持久化/续扫、飞书渲染与分段、复核存储与内部评估指标、配置校验、覆盖池校验、前端产品化契约、Agent panel/chat 纯逻辑。

## 合规边界

TradeEye Copilot 仅呈现事实、规则触发的异常、来源证据与市场反应上下文。它**不**输出投资建议、目标价或买卖评级。

## 相关项目

- [daoyezongzi/TradeEye](https://github.com/daoyezongzi/TradeEye) —— 数据抓取、感知管道与飞书推送机制
- [daoyezongzi/PlatoAcademy](https://github.com/daoyezongzi/PlatoAcademy) —— 无头 Skill Agent 编排、RAG 检索与推理（交互参考）

## 文档与参考

- [开发日志](docs/development-log.md) —— 按时间顺序的实现记录
- [Spec 与 Plan](docs/superpowers/) —— 设计规格与实施计划：
  - [Agent 事实契约设计](docs/superpowers/specs/2026-08-01-agent-fact-contract-design.md)
  - [真实数据披露事件设计](docs/superpowers/specs/2026-07-29-real-data-disclosure-event-design.md)
  - [扫描入口整合设计](docs/superpowers/specs/2026-07-31-scan-entry-consolidation-design.md)
- [提交清单](docs/submission-checklist.md)
