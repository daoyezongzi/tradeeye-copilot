# 正式版收尾设计

## 目标

把当前 `main` 收口到“端出来即可开测”的产品状态：发布资料与中英文说明保持一致，研究员前端没有旧复核入口残留，小 UX 不阻塞开测。此轮不加入演示 workflow、Playwright E2E、行业规则扩展或新的审核器。

## 范围

### 包含

1. 通用 LLM 配置命名
   - 将外部 LLM API key 的正式环境变量从 Ascend 专名改为 `LLM_API_KEY`。
   - `LLM_BASE_URL` 与 `LLM_MODEL` 继续用于任意 OpenAI-compatible 服务，例如 DeepSeek 或 Ascend 兼容端点。
   - `.env.example`、README、checklist 与配置测试同步使用通用命名。

2. 同步发布资料
   - `README.en.md` 与当前中文 README 的产品状态对齐。
   - `docs/submission-checklist.md` 改成真实状态清单：已由仓库状态证明的项可标记，需真实环境/人工确认的项保持未完成。
   - `docs/development-log.md` 顶部补充说明：旧 review 前端记录属于历史记录，当前研究员主路径以最新状态为准。

2. 清理旧研究员复核痕迹
   - 移除旧 review 页面截图，避免发布材料误导。
   - 保留后端 review/eval 能力、benchmark artifact 与飞书预览截图。
   - 不删除用户真实数据、数据库或密钥文件。

3. 完成小 UX
   - Agent 引用溯源从裸 JSON 改为可读证据卡，并保留原始 JSON 便于复核。
   - Agent 未配置时入口仍可见，显示明确配置引导，不让用户误判为入口丢失。
   - 单票研判输入支持公司名候选；用户输入公司名或 `ts_code` 都能解析到股票代码。

4. 开测前自审
   - 检查 README / README.en / checklist / development log 的当前状态描述一致。
   - 检查研究员前端没有 review 一级导航、review 页面、CSV 导出、复核标注 chip 或 precision 展示。
   - 运行轻量前端验证；Python 全量测试由用户稍后本地跑时，文档不冒充通过。

### 不包含

- 不新增本地演示 workflow。
- 不新增 Playwright 或浏览器 E2E 依赖。
- 不新增行业专用规则。
- 不恢复研究员复核前端。
- 不改变后端 review/eval API。

## 设计

### 发布资料同步

`README.en.md` 作为英文首页镜像，必须表达当前产品事实：Agent 已是研究员前端悬浮层，复核能力属于内部评估，研究员主路径只有披露日研判与单票研判。测试规模、API 列表、项目结构、合规边界应与中文 README 一致。

`docs/submission-checklist.md` 不作为“全部完成”的宣传页，而作为提交前状态板。仓库可证明的项目可以标记完成，例如 `.env` 未跟踪、无 researcher review 前端入口；需要密钥、真实环境、录屏或人工确认的项目必须保留未勾选。

`docs/development-log.md` 保持历史日志不重写，只在顶部新增当前状态说明，避免旧日志中提到 review 页面时被误读为现状。

### 旧截图清理

只清理明确代表旧研究员复核页面的截图文件。文件名包含 `feishu-preview` 的截图保留，因为它们不是复核页面。清理动作应通过 git diff 可见，并在最终报告中列明删除了哪些文件。

### Agent 引用溯源 UX

当前 `showAgentReference(reference)` 直接展示 JSON。改造后弹窗顶部展示结构化字段：

- 类型或规则：`reference.rule_id` / `reference.kind` / `reference.title` 中可用者优先。
- 来源：`source`。
- 字段：`field`。
- 期间：`period`。
- 数值：`value`。

字段缺失时显示“未提供”，但不伪造值。下方保留原始 JSON 代码块，方便调试与复核。该改动只影响展示，不改变 Agent contract。

### Agent 未配置引导

`agent_ready=false` 时 Agent FAB 不应消失。点击后打开面板，显示简短引导：需要配置外部 LLM API 后启用问答；当前仍可查看公司卡、依据弹窗和确定性 finding。输入框在未就绪时禁用或阻止发送，并给出同样的解释。

### 公司名搜索

单票研判继续以 `ts_code` 作为 API 参数和路由参数。前端增加公司名候选：

- 候选来源为 `/api/meta` 的 `company_names`。
- 输入可为 `603026.SH` 或 `石大胜华`。
- 若输入命中公司名，提交时转换为对应 `ts_code`。
- 若输入已经是合法代码，直接使用。
- 若无法解析，沿用现有错误提示模式，不发起无效 API 请求。

### 验证策略

前端行为用现有 Node 测试和 Python 静态产品化测试覆盖：

- Agent reference formatter：缺字段不崩溃，保留原始 JSON。
- Agent readiness：未配置时入口可见且显示引导。
- Company resolver：公司名和代码均能解析。
- Researcher frontend：继续禁止 review nav/page/chip/precision 暴露。

执行验证：

```bash
npm test
node --check web/app.js && node --check web/agent-chat.js && node --check web/agent-panel.js
```

如本轮修改触及 Python 测试断言，则运行对应 focused pytest。全量 `python -m pytest --basetemp=.pytest_tmp -q` 留给用户开测前执行，最终报告只能说明是否已由本轮实际运行。

## 成功标准

- 中英文 README 与 checklist 不再宣传已移除的 researcher review 前端。
- 旧 review 页面截图不再留在发布材料目录中。
- Agent 入口在未配置 LLM 时仍可发现，并给出配置引导。
- Agent 引用弹窗可读，不再只有裸 JSON。
- 单票研判可通过公司名候选进入，同时保持代码参数稳定。
- 轻量前端验证命令通过，或报告明确失败项。
