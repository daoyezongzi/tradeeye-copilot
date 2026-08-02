# 前端导航收口与股票名称优先展示设计

**日期**：2026-08-02
**范围**：研究员前端导航信息架构收口；删除复核队列一级页面；股票展示从代码优先改为名称优先、代码辅助。
**不包含**：删除后端复核/eval API、修改复核数据模型、引入新页面、把 Agent 改成独立导航页。

## 一、目标

前端左侧导航只保留研究员真正的主路径：

- 披露日研判：批量发现入口，回答“某个披露日覆盖池里谁值得优先看”；
- 单票研判：精查入口，回答“某一只股票某个报告期怎么看”。

复核属于内部评估，不是研究员主流程；Agent 是横跨两个视图的浮层交互，不是页面。导航应表达产品主路径，而不是系统能力清单。

同时，股票展示层应从代码优先调整为名称优先，减少研究员阅读负担；代码仍保留为唯一标识。

## 二、现状

`web/index.html` 当前左侧 nav 有三个一级 tab：

```html
<button data-view="workbench">披露日研判</button>
<button data-view="company">单票研判</button>
<button data-view="review">复核队列</button>
```

`web/app.js` 对应：

```js
const VIEWS = ["workbench", "company", "review"];
const VIEW_TITLES = {
  workbench: "披露日研判",
  company: "单票研判",
  review: "复核队列",
};
```

`view-review` 页面展示：

- `review-metrics`：精确率等内部评估指标；
- `review-table`：标注明细；
- `export-review-csv`：人工复核 CSV 导出。

标注动作本身不在 `view-review` 内，而在公司卡底部 `renderReviewActions(card)` 的 `TRUE / FALSE / UNREVIEWED` chip。也就是说，`view-review` 是复核结果汇总页，不是研究员分析入口。

股票展示当前多处代码优先，例如：

```js
code.textContent = `${card.ts_code} · ${card.period}`;
```

已有 `displayName(tsCode)` 可从 `state.meta.company_names` 取得公司名，但没有形成统一展示规则。

## 三、设计原则

1. **导航只放主路径**：左侧一级导航只表达研究员工作对象，不放内部评估、开发者、导出、通知、Agent。
2. **复核前端下线，不删后端能力**：后端复核/eval API 与内部测试能力保留；研究员前端不展示复核队列、指标、明细和 CSV。
3. **Agent 是浮层，不是页面**：继续使用右下角机器人入口 + 浮层问答，不新增 `Agent` 导航项。
4. **名称优先，代码辅助**：展示层优先显示公司名，代码作为唯一标识留在第二行或弱化位置。
5. **旧路由不制造幽灵页面**：`#/review` 不保留隐藏 view，访问时回到 `#/workbench`。

## 四、导航结构

改造后左侧导航：

```text
披露日研判
单票研判
```

删除：

- `tab-review` 按钮；
- `view-review` section；
- `review` view title；
- `review` 作为合法 hash view。

`VIEWS` 改为：

```js
const VIEWS = ["workbench", "company"];
```

`VIEW_TITLES` 改为：

```js
const VIEW_TITLES = {
  workbench: "披露日研判",
  company: "单票研判",
};
```

`parseHash()` 对 `#/review` 不特殊兼容为隐藏页面；它和其他未知 hash 一样回到 `{ view: "workbench" }`。后续导航归一到 `#/workbench`，不继续保留 `#/review` 语义。

## 五、复核前端处理

从研究员前端删除：

- `view-review` 整个 section；
- `review-metrics` 展示；
- `review-table` 展示；
- `export-review-csv` 按钮；
- 复核 CSV 导出入口；
- 公司卡底部 `TRUE / FALSE / UNREVIEWED` 标注 chip；
- 前端复核状态读取、指标读取与渲染调用。

保留但不在研究员前端曝光：

- 后端 `/api/reviews/*`；
- `eval` 相关测试与内部评估数据。

`renderReview()` / `renderReviewMetrics()` / `exportReviewCsv()` / `renderReviewActions(card)` 等只服务已删除 UI 的前端函数删除。`loadReviewLabels()` / `loadReviewMetrics()` 启动调用删除。`state.reviewLabels` 从前端 state 删除。

研究员前端不保留“复核回写状态”块，不展示 precision、标注明细、标注 chip 或 CSV 入口。后端与测试能力保留。

## 六、股票名称优先展示

新增统一展示 helper（位置在 `displayName()` 附近）：

```js
function companyTitle(tsCode) {
  return displayName(tsCode) || tsCode;
}

function companySubtitle(tsCode, period) {
  return `${tsCode} · ${periodLabel(period)}`;
}
```

展示规则：

```text
公司名
ts_code · 报告期中文名
```

例：

```text
石大胜华
603026.SH · 2025 半年报
```

影响范围：

- 工作台公司卡 `renderCard()`：`.card__name` 使用 `companyTitle(card.ts_code)`；`.card__code` 使用 `companySubtitle(card.ts_code, card.period)`；
- 单票详情卡复用 `renderCard()`，自然同步；
- Agent 上下文与分组标题：从 `ts_code · period` 改为 `公司名 / ts_code · 报告期中文名`；
- 扫描进度 `renderJobProgress()`：优先 `displayName(current_ts_code)`，无名时退回代码；
- 数据问题表 / 扫描历史 / 诊断中涉及股票的显示：名称列优先，代码列保留等宽字体。

底层 API 请求、hash、session、Agent action 参数仍然全部使用 `ts_code` / `period`，不以公司名作为标识。

## 七、数据流与状态

导航收口不改后端数据流：

- 披露日扫描仍走 `/api/disclosure-day/jobs`；
- 单票分析仍走 `/api/analyze/company`；
- Agent action 仍确认后调用现有分析接口；
- 后端 reviews API 保留但不由研究员前端调用。

启动流程调整：

- `boot()` 不再调用 `renderReview()`；
- `boot()` 不再调用 `loadReviewLabels()` / `loadReviewMetrics()`；
- `renderCards()` 不再依赖 `state.reviewLabels`；
- `state.reviewLabels` 从前端 state 删除。

## 八、错误处理

- 访问未知 hash（包含 `#/review`）回到工作台；不弹错误，不保留旧页面。
- 如果 `company_names` 中没有某个代码，展示回退到 `ts_code`，不阻断页面。
- 删除复核前端入口后，reviews API 失败不再影响 boot，也不会污染研究员页面状态。

## 九、测试边界

需要新增或更新前端产品化测试（沿用已有 `tests/test_frontend_productization.py` 风格）：

1. `web/index.html` 不包含 `tab-review` / `view-review` / `review-table` / `review-metrics` / `export-review-csv`；
2. `web/app.js` 中 `VIEWS` 只包含 `workbench` / `company`；
3. `parseHash()` 不再把 `review` 当合法 view；
4. 前端不再调用 `loadReviewLabels()` / `loadReviewMetrics()`；
5. `renderCard()` 使用公司名作为主标题，代码和报告期中文名作为辅助；
6. `companyTitle()` / `companySubtitle()` 无公司名时稳定回退代码；
7. 全量 pytest 保持通过；Node 前端测试保持通过。

## 十、明确不做

- 不删除后端 reviews API；
- 不删除 eval/manual review 数据结构和测试；
- 不新增 Agent 左侧导航页；
- 不把开发者区拆成一级导航；
- 不用公司名替代 `ts_code` 做 URL、API 参数或 session key。
