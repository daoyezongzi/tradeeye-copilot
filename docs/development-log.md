# TradeEye Copilot 开发日志

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
