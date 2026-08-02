# Agent 前端对接设计（对话式人机交互面板）

**日期**：2026-08-02
**范围**：`web/` 前端 Agent 问答面板 + 后端 `actions` 契约扩展。研究员在浮层里向 Agent 提问、查看带引用的回答、确认执行重抽数据动作。
**不包含**：快捷指令（斜杠命令）、流式输出、移动端适配、自由文本审核器、复核标注类动作。

## 一、目标

后端问答闭环已在 `2026-08-02-agent-backend-design.md` 落地，`POST /api/agent/chat` 可用，但该 spec 明确把「前端右侧问答栏」留作待办。本次补上这一环，并解决一个后端缺口：现有 Agent 工具全是只读，无法表达「建议重新抓取数据」。

成功标准：

- 研究员看着研判卡就能提问，回答附可点开的证据引用；
- Agent 判断数据需要重抓时，给出一张动作卡，研究员点确认后才执行；
- 面板不压缩主区内容宽度，正文字号不缩水；
- 换卡后回看历史，一眼能分清哪段属于哪张卡。

## 二、现状与复用

**后端已有**：

- `POST /api/agent/chat`，请求 `{ts_code, period, question, session_id?}`，响应 `{session_id, answer, references, message_id}`；一次性 JSON，非流式；
- 错误码：400（卡不存在 / session 与 ts_code 不匹配）、422（工具解析失败）、500（LLM 失败）、503（Agent 未配置）；
- 会话绑定 `(ts_code, period)`，历史消息是唯一上下文来源，保留最近 20 轮；
- 引用硬校验：伪造的 `fact_id` / `evidence_id` 被丢弃并记日志，回答照常返回；
- 只读工具白名单 4 个，**无写工具**。

**前端已有**（`web/` 纯原生，无构建）：

- `web/app.js` 1499 行，`requestJson` + `api` 对象封装请求；`state` 单一全局状态；
- `loadCompany(tsCode, period)` 调 `/api/analyze/company`，带 `companyProgress` 进度条；
- `loadDisclosureDay(date)` 调 `/api/disclosure-day/jobs` 并轮询，带 `scanProgress` 进度条与 job 恢复逻辑；
- `#evidence-dialog` 证据溯源弹窗、`notify()` snackbar、`web/components.js` 的 `createMenuButton` 组件先例；
- `web/styles.css` 完整 token 体系（M3 role 承载 Anthropic 色值），顶栏用 `backdrop-filter: blur(16px) saturate(150%)` 半透明材质，`--shadow-3` 为浮层阴影。

**PlatoAcademy 参考**（同为原生 HTML/CSS/JS）：值得复用的是可折叠可拖宽的聊天栏（宽度存 localStorage）、`#context-bar` 显式上下文绑定 + placeholder 联动、Enter 发送 / Shift+Enter 换行、错误以气泡入流、AI 结果挂「确认后落地」动作按钮。不宜搬的是手写正则 Markdown、无等待反馈、无停止按钮、硬滚到底、无响应式。

## 三、设计原则

1. **后端只建议，前端才执行**。Agent 工具白名单一个不加，动作只是回答的结构化输出；执行走已有的 `/api/analyze/*` 接口。
2. **动作卡即确认门**。动作永不自动执行，点确认才跑，不再叠加二次确认弹窗。
3. **不压缩主区**。面板浮在内容之上，`--page-max: 1320px` 与正文 13px 均不让步。
4. **复用而非新建**。引用溯源用现有 `#evidence-dialog`，执行进度用现有进度条，颜色只用现有 token。
5. **上下文显式声明**。当前答疑对象写在面板顶部，不让 Agent 猜。

## 四、后端契约扩展

`copilot/agent/contracts.py` 新增：

```python
class AgentAction(BaseModel):
    action: Literal["refetch_company", "rescan_disclosure_day"]
    params: dict
    reason: str
```

`AgentChatResult` 增加 `actions: list[AgentAction] = []`。

参数形状：

| action | params | 前端执行 |
|---|---|---|
| `refetch_company` | `{ts_code, period}` | `POST /api/analyze/company` |
| `rescan_disclosure_day` | `{date}`（YYYYMMDD） | `POST /api/disclosure-day/jobs` |

`AgentService` 解析 LLM 输出的 `actions` 字段，三层校验后放行：动作名在白名单内、参数过 Pydantic 模型、`ts_code` / `period` / `date` 格式合法。任一层失败即丢弃该条动作并记日志，回答照常返回——与现有引用校验的处理方式一致，不阻断、不重试。

system prompt 补充动作产出规则：卡不存在、数据明显过期、研究员明确要求重抓时给动作；能用现有数据回答时不给。同一次回答最多 2 条动作。

`AppMeta` 增加 `agent_ready: bool`，取值为 `agent_service is not None`。前端据此在初始化阶段就能判断 Agent 可用性，不必等用户发出第一条消息才收到 503。`real_app.py` 里 `ReportService.get_meta()` 相应填充该字段。

## 五、前端模块划分

`web/app.js` 已 1499 行，不再往里堆。新增两个文件，`index.html` 追加两个 `<script>`：

**`web/agent-panel.js`** — 浮层外壳，只管窗口行为，不知道研判卡是什么，不发请求。

```
createAgentPanel({ mount, onSend, onAction })
  → { open, close, appendMessage, appendAction, startGroup, setContext, setPending, setDisabled }
```

职责：停靠/拖离/吸附、拖宽、折叠成药丸、位置尺寸存取 localStorage、启动时 clamp 回视口、消息与分组渲染、等待占位气泡、滚动策略。

**`web/agent-chat.js`** — 会话逻辑，持有 `sessionId` 与当前绑定的 `(ts_code, period)`。

```
createAgentChat({ panel, api, executors })
  → { bindCard(tsCode, period), clearCard() }
```

职责：调 `api.agentChat`；把 `answer` / `references` / `actions` 交给面板渲染；换卡时重置 sessionId 并开新分组；动作确认后分发到 `executors`。

**`web/app.js`** 只加三处接线：`api.agentChat` 方法；初始化时创建面板与会话；把 `loadCompany` / `loadDisclosureDay` 作为 executors 传入。渲染卡片与生成单票的既有代码里各加一次 `bindCard` 调用。

**`web/styles.css`** 追加 Agent 面板样式段，只用现有 token，不新增颜色变量。

这个切法让两个单元可独立测试：给 `agent-panel` 假的 `onSend` 就能验证拖动吸附；给 `agent-chat` 假面板就能验证 sessionId 复用与动作分发。

## 六、浮层布局与拖动

**停靠态（默认）**：绝对定位贴右，四周留 `--space-4` 间隙，`--radius-lg` 圆角，`--shadow-3` 阴影，外壳用顶栏同款 `backdrop-filter: blur(16px) saturate(150%)` 半透明材质。上下拉满（顶部让开 52px 顶栏），宽度默认 400px，可拖 320–560px。

**浮窗态**：抓面板头部拖离右缘即切换，可拖到视口任意位置，尺寸 320–560 × 360–720。

**吸附**：浮窗态下拖到距右缘 24px 内自动吸回停靠态；接近时右侧显示一条 2px 陶土橙高亮带预告吸附。

**关闭态**：收成右下角药丸按钮（深墨底 + 陶土橙小方块），点开恢复上次状态。

localStorage 键 `tradeeye.agentPanel`，存 `{mode: "docked"|"floating", width, height, left, top, open}`。启动时对 `left/top/width/height` 做 clamp，保证至少 120×80 落在视口内——换显示器或缩窗口后不会飘到屏外。窗口 `resize` 时同样 clamp。

## 七、上下文绑定与数据流

面板顶部上下文栏显示「当前：603026.SH · 2025Q2」，底色 `surface-container-high`、左侧 3px 陶土橙竖线（沿用现有 `.lede` 的 `border-left: 3px solid var(--clay)` 语汇）。

绑定时机：

- 披露日研判视图点某家公司行 → 绑定该卡；
- 单票研判生成完卡 → 绑定该卡；
- 无卡时上下文栏显示「未选择研判卡」，输入框禁用并提示先选卡。

**换卡不清空对话**，但新起 session（后端 session 绑定 `(ts_code, period)`，换卡必然换 session）。历史按卡分组保留：每组带左竖线与组头（`ts_code · period` + 状态徽标），当前组竖线用 `--clay` 且徽标为深墨底「当前」，历史组竖线用 `--outline-variant`、徽标浅灰「已切走」。

历史组的后退感用**色阶而非 opacity**：文字降到 `--md-sys-color-on-surface-muted`（4.89:1，仍过 AA 正文），气泡底换 `surface-container-low`。用 `opacity: .52` 会把 6.04:1 的正文压到 AA 以下，且与项目「层级靠 1px 边框和极窄明度带」的原则相悖。

一轮问答的数据流：

```
研究员输入
  → agent-chat 组装 {ts_code, period, question, session_id?}
  → POST /api/agent/chat
  → 记下 session_id 供下轮复用
  → 面板渲染 answer + references(chip) + actions(动作卡)

点动作卡「确认执行」
  → agent-chat 分发到 executors
      refetch_company        → app.js loadCompany（复用 companyProgress）
      rescan_disclosure_day  → app.js loadDisclosureDay（复用 scanProgress 与 job 轮询）
  → 完成后向对话追加系统气泡「已重新抓取，卡已更新」
```

引用 chip 点击调 `api.getEvidence(ts_code, period, rule_id)` 并打开现有 `#evidence-dialog`，不新写溯源弹窗。

## 八、输入与等待反馈

`<textarea rows="2">`，Enter 发送、Shift+Enter 换行，随内容自动增高至 5 行上限（PlatoAcademy 固定 2 行导致长问题内部滚动，此处改进）。右侧发送按钮。

发送后立即插入占位气泡显示三点脉冲动画，收到响应替换该气泡；期间发送按钮禁用。动画走 `prefers-reduced-motion` 降级为静态「正在思考…」。

滚动策略：仅当用户已在底部（`scrollHeight - scrollTop - clientHeight < 40`）时自动滚到底；上滑翻历史时不抢滚动。

无停止生成按钮——后端非流式，请求发出即无法中断。

## 九、错误处理

错误一律以气泡留在对话里，不用 snackbar 一闪而过，便于回看时定位失败轮次。

| 情况 | 面板表现 |
|---|---|
| 400 卡不存在 | 气泡「该报告期尚未生成研判卡」+ 动作卡建议重抽该票 |
| 400 session 与 ts_code 不匹配 | 气泡提示已重置会话，清空 sessionId 后自动重发一次 |
| 422 无法理解 | 气泡「无法理解，请换个问法」 |
| 500 LLM 失败 | 气泡 + 「重试」按钮，重发上一条问题 |
| 503 Agent 未配置 | 面板整体禁用，输入框提示未配置 LLM |
| 网络错误 | 气泡显示 `error.message` + 「重试」按钮 |
| 动作执行失败 | 追加气泡写明失败原因，绑定卡状态不变 |

400 自动重发只做一次：重发仍失败则按普通错误气泡处理，不再循环。

动作执行期间按钮变禁用态并显示进度；已执行过的动作卡按钮置灰并标注「已执行」，防止重复触发。

面板初始化时读 `/api/meta` 的 `agent_ready`；为 `false` 时直接进禁用态，不等到用户发第一条消息才报错。

## 十、无障碍

- 面板 `role="complementary"`，`aria-label="Agent 问答"`；
- 消息容器 `aria-live="polite"`，新回答自动播报；
- 拖动把手与调宽把手可键盘操作：聚焦后方向键移动/调宽 8px 一档，Esc 取消本次拖动；
- 动作卡按钮为原生 `<button>`，Tab 可达；
- 折叠药丸按钮有 `aria-expanded`；
- 引用 chip 为 `<button>`，标注「查看 xxx 的证据」。

## 十一、测试边界

**后端 pytest**（`tests/test_agent_actions.py` 新增，其余沿用现有文件）：

1. `actions` 字段解析正常，`action` / `params` / `reason` 落到响应；
2. 白名单外动作名被丢弃，回答照常返回；
3. `params` 缺字段或类型错误被丢弃；
4. `ts_code` / `period` / `date` 格式非法被丢弃；
5. 动作与引用可共存，互不影响；
6. 单次回答动作超过 2 条时截断；
7. `POST /api/agent/chat` 响应契约含 `actions`；
8. 现有全量测试保持通过。

**前端 node 单测**：TradeEye 目前无前端测试基建（无 `package.json`，无既有测试文件），需新建最小基建——根目录 `package.json` 仅声明 `"type": "module"` 与 `"test": "node --test web/"`，不引入任何依赖，用 Node 内置 `node:test` + `node:assert`。

为此，两个新模块中不依赖 DOM 的部分（吸附判定、clamp、localStorage 序列化、sessionId 与分组状态推进、动作分发、滚动判定）写成接收参数返回结果的纯函数，集中在文件顶部并挂到 `window` 供浏览器使用、同时 `export` 供测试导入。DOM 渲染部分不做单测，靠手动联调覆盖。

测试文件 `web/agent-panel.test.mjs` / `web/agent-chat.test.mjs`：

1. 吸附判定：距右缘 <24px 返回停靠，否则浮窗；
2. clamp：视口外坐标被拉回，尺寸被夹在上下限内；
3. localStorage 存取往返一致，缺字段时回落默认值；
4. sessionId 首轮为空、次轮复用返回值；
5. 换卡时 sessionId 重置且开新分组；
6. 动作分发到正确 executor，参数透传无改写；
7. 滚动策略：在底部返回应滚，上滑后返回不滚。

**手动联调**：真实 LLM 下走通问答、引用点开溯源、重抽单票、重扫披露日；后端接口暴露问题时直接 debug 修复（已获授权）。

## 十二、明确不做

- 不做快捷指令 / 斜杠命令；
- 不做流式输出（后端非流式，无 SSE 基础设施）；
- 不做停止生成按钮；
- 不做移动端响应式（研究员桌面场景）；
- 不让 Agent 提出复核标注类动作——复核属内部评估，避免污染评估数据；
- 不给 Agent 新增写工具；
- 不引入 Markdown 渲染库；回答按纯文本渲染并转义，段落按换行切分。
