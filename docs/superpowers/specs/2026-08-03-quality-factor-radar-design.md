# 单公司经营质量因子与对比分析设计

**日期**：2026-08-03
**范围**：单公司经营质量因子、异常规则解释层、分档雷达图、同一时期多公司 / 同一公司多时期的自定义对比能力。
**不包含**：行业相对排名、行业基准分位、扩展行业规则包、投资评级、估值对比、连续 0–100 经营质量总分。

## 一、目标

让财报分析者打开单公司研判时，第一眼看到“经营质量哪里正常、哪里需要关注、哪里异常”，再能下钻到规则、阈值、原始事实和证据。这个视图不只服务本公司财报研究，也要为横向对比留出同一套因子口径。

成功标准：

- 单公司首屏以因子列表为主，小雷达为辅助，能直观看到 6 个经营质量维度的状态；
- 每个异常 / 关注因子都能解释到具体规则、阈值、当前观察值和证据；
- 支持同一报告期多家公司对比，以及同一公司多报告期趋势对比；
- 允许自定义公司 + 报告期组合，但必须明确提示期间不一致会降低可比性；
- 不把规则阈值包装成精确评分或投资建议。

## 二、现状与复用

**已有后端底座**：

- `PeriodSnapshot` 已包含本期、上季、去年同期分析所需的收入、净利润、扣非净利润、毛利率、经营现金流、应收账款、存货；
- `CompanyCard` 已输出 `facts`、`rule_results`、`findings`、`card_status`、`classification`；
- `Fact` / `FactEvidence` 已强制 VERIFIED 事实必须有来源、字段、报告期和值；
- `RuleResult` 已有 `HIT / MISS / NOT_EVALUATED / BLOCKED` 语义；
- SQLite 已保存快照、findings 和 company cards，可作为批量对比读取基础。

**已有前端底座**：

- 单票研判入口和公司卡已存在；
- 公司卡可展示事实行、finding、归因、证据入口、公司详情深链；
- `metric-grid`、事实分格、表格、证据弹窗、Agent 面板均可复用；
- 前端是原生 HTML/CSS/JS，无构建流程，新功能应继续沿用现有模式。

**当前缺口**：

- 没有经营质量因子模型；
- 没有因子状态与规则结果的映射契约；
- 没有雷达图或因子列表 UI；
- 没有批量公司 / 多期间对比接口；
- Tushare 行业信息和 `bank_v1` 目前只够做分类 / 不适用处理，不能支撑同业排名。

## 三、设计原则

1. **状态优先，不做伪精确**。首版只输出正常 / 关注 / 异常 / 不可计算 / 不适用，不输出 0–100 总分。
2. **规则解释因子**。因子负责组织视角，规则负责解释状态，事实和证据负责追溯数据来源。
3. **同一口径支持对比**。单公司、多公司、同公司多期间都使用同一组因子定义。
4. **可比性显式声明**。默认统一报告期；只有用户显式自定义时才允许混合报告期，并提示“仅供探索”。
5. **不扩行业规则包**。首版不做同业相对位置，不新增制造、消费、医药等行业规则包。
6. **复用现有 UI 和契约**。优先扩展 `CompanyCard` 周边契约和现有公司卡展示，不新建独立产品体系。

## 四、因子模型

首版定义 6 个经营质量因子，均映射到现有规则：

| factor_id | 展示名 | 业务问题 | 规则 |
|---|---|---|---|
| `revenue_realization_quality` | 收入兑现质量 | 应收增长是否明显快于收入增长 | `receivable_revenue_divergence` |
| `inventory_match_quality` | 存货匹配质量 | 存货增长是否明显快于收入增长 | `inventory_revenue_divergence` |
| `cashflow_quality` | 现金质量 | 利润是否有经营现金流支撑 | `cashflow_quality` |
| `profitability_stability` | 盈利稳定性 | 毛利率是否出现异常波动 | `gross_margin_change` |
| `performance_direction_consistency` | 业绩方向一致性 | 收入与净利润增长方向是否一致 | `net_profit_revenue_direction` |
| `profit_sustainability` | 利润可持续性 | 利润是否过度依赖非经常性损益 | `non_recurring_profit_share` |

因子状态：

| 状态 | 含义 | UI |
|---|---|---|
| `NORMAL` | 已计算，未触发异常规则 | 绿色 / 外圈 |
| `WATCH` | 命中黄色规则，需要关注 | 黄色 / 中圈 |
| `ANOMALY` | 命中红色规则，明显异常 | 红色 / 内圈 |
| `NOT_EVALUATED` | 缺少必要事实或对比期，无法计算 | 灰色 / 断点 |
| `NOT_APPLICABLE` | 行业或口径不适用 | 灰色 / 斜纹 |

首版不输出 `score`。如果未来需要连续分数，必须在有样本校准、行业基准或人工复核结果后另立设计。

## 五、规则映射

现有规则保持原逻辑，不直接改造成评分器。新增一个规则解释字典，把规则归属到因子并提供面向用户的解释。

| rule_id | 因子 | 触发逻辑 | 现有严重度 | 默认因子状态 |
|---|---|---|---|---|
| `receivable_revenue_divergence` | 收入兑现质量 | 应收 YoY - 营收 YoY > 30pct | RED | `ANOMALY` |
| `inventory_revenue_divergence` | 存货匹配质量 | 存货 YoY - 营收 YoY > 30pct | RED | `ANOMALY` |
| `cashflow_quality` | 现金质量 | 经营现金流 / 净利润 < 50% | YELLOW | `WATCH` |
| `gross_margin_change` | 盈利稳定性 | 毛利率 YoY 变动绝对值 > 5pct | YELLOW | `WATCH` |
| `net_profit_revenue_direction` | 业绩方向一致性 | 营收 YoY 与净利润 YoY 一正一负 | RED | `ANOMALY` |
| `non_recurring_profit_share` | 利润可持续性 | 非经常性损益 / 净利润 > 30% | YELLOW | `WATCH` |

状态映射规则：

- `RuleResult.status == MISS` → 因子 `NORMAL`；
- `RuleResult.status == HIT` 且 finding severity 为 `YELLOW` → 因子 `WATCH`；
- `RuleResult.status == HIT` 且 finding severity 为 `RED` → 因子 `ANOMALY`；
- `RuleResult.status == NOT_EVALUATED` 或 `BLOCKED` → 因子 `NOT_EVALUATED`；
- 规则明确不适用于当前行业 / 口径 → 因子 `NOT_APPLICABLE`；
- 如果未来一个因子挂多条规则，取最严重状态，并保留所有规则明细。

规则解释分两层：

**默认层**：

```text
收入兑现质量：异常
解释：应收账款增长明显快于营业收入，可能意味着回款压力或收入确认质量下降。
```

**展开层**：

```text
规则：receivable_revenue_divergence
触发条件：应收 YoY - 营收 YoY > 30pct
当前观察：应收 YoY 58.2%，营收 YoY 12.4%，背离 45.8pct
数据来源：tushare.balancesheet.accounts_receivable + tushare.income.revenue
```

## 六、后端契约

新增因子结果模型，作为 `CompanyCard` 的补充字段，避免重写现有卡片结构。

```python
class FactorStatus(StrEnum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    ANOMALY = "ANOMALY"
    NOT_EVALUATED = "NOT_EVALUATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class FactorObservation(BaseModel):
    label: str
    value: float | str | None
    unit: str | None = None
    period: str

class QualityFactor(BaseModel):
    factor_id: str
    label: str
    status: FactorStatus
    summary: str
    rule_ids: list[str]
    fact_ids: list[str]
    observations: list[FactorObservation] = []
    reason_code: str | None = None
    reason: str | None = None
```

`CompanyCard` 增加：

```python
quality_factors: list[QualityFactor] = []
quality_overview: QualityOverview | None = None
```

`QualityOverview`：

```python
class QualityOverview(BaseModel):
    status: FactorStatus
    normal_count: int
    watch_count: int
    anomaly_count: int
    not_evaluated_count: int
    not_applicable_count: int
    summary: str
```

概览状态：

- 任一 `ANOMALY` → `ANOMALY`；
- 否则任一 `WATCH` → `WATCH`；
- 否则全部可计算且正常 → `NORMAL`；
- 如果存在不可计算 / 不适用但无关注或异常 → `NOT_EVALUATED`，文案写“不完整”；
- `NOT_APPLICABLE` 不视为异常，也不硬扣。

## 七、对比能力

首版支持三种模式：

1. **同一报告期，多家公司**：默认严格统一 period，例如都比较 `20250630`；
2. **同一公司，多报告期**：同一 `ts_code` 下比较多个 period；
3. **自定义组合**：用户显式选择多个 `(ts_code, period)`，允许混合，但 UI 标注“期间不一致，仅供探索，不作为严格横向比较”。

新增只读接口草案：

```http
POST /api/quality-factors/compare
```

请求：

```json
{
  "items": [
    {"ts_code": "603026.SH", "period": "20250630"},
    {"ts_code": "600809.SH", "period": "20250630"}
  ],
  "mode": "same_period_companies"
}
```

响应：

```json
{
  "mode": "same_period_companies",
  "comparability": "STRICT",
  "warnings": [],
  "items": [
    {
      "ts_code": "603026.SH",
      "period": "20250630",
      "company": {},
      "quality_overview": {},
      "quality_factors": []
    }
  ]
}
```

`comparability`：

- `STRICT`：同一报告期多家公司，或同一公司多报告期；
- `EXPLORATORY`：自定义混合组合；
- `INCOMPLETE`：存在缺失卡片、缺失快照或不可计算因子。

接口不做自动同业分组、不按行业拉公司、不输出行业排名。

## 八、前端体验

单公司首屏采用 **因子列表优先，小雷达辅助**：

1. 顶部保留现有公司卡标题、公司名、股票代码、报告期、严重度；
2. 新增经营质量概览条：`经营质量：关注`，并写出 `异常 1 项 / 关注 1 项 / 正常 4 项`；
3. 左侧主区为 6 个因子列表，每行显示状态、摘要、关键观察值；
4. 右侧或列表上方放小雷达，雷达只表达分档状态，不表达精确分数；
5. 点击因子展开规则详情、阈值、当前观察值和证据入口；
6. `NOT_EVALUATED` / `NOT_APPLICABLE` 明确显示原因，不隐藏。

雷达分档：

- `NORMAL`：外圈；
- `WATCH`：中圈；
- `ANOMALY`：内圈；
- `NOT_EVALUATED`：灰色断点；
- `NOT_APPLICABLE`：灰色斜纹断点。

对比工作台作为第二层入口，不抢单公司首屏。入口文案：

```text
进入对比：同报告期多公司 / 同公司多期间 / 自定义组合
```

对比页优先显示矩阵：行是公司或期间，列是 6 个因子，单元格用状态徽标。点击单元格打开同一套规则解释和证据。

## 九、错误与边界

- 公司卡不存在：显示缺失状态，并提示先生成该公司 / 期间研判；
- 快照缺少去年同期：涉及 YoY 的因子为 `NOT_EVALUATED`；
- 当前期关键字段缺失：沿用 `CompanyCard.card_status = PARTIAL/BLOCKED`；
- 银行或特殊行业不适用毛利率、存货等口径时，显示 `NOT_APPLICABLE`，不参与异常数量；
- 自定义组合期间不一致：展示警告，不阻止用户继续；
- 规则命中但证据缺失：视为数据契约错误，后端应阻止 VERIFIED 状态或返回不完整原因。

## 十、测试边界

**后端 pytest**：

- 每条现有规则可映射到正确 `factor_id`；
- `MISS / HIT+YELLOW / HIT+RED / NOT_EVALUATED` 正确映射为因子状态；
- `QualityOverview` 计数和整体状态正确；
- 缺去年同期时 YoY 因子为 `NOT_EVALUATED`；
- `NOT_APPLICABLE` 不被计为异常或关注；
- compare 接口同报告期多公司返回 `STRICT`；
- compare 接口自定义混合组合返回 `EXPLORATORY` 和警告；
- 缺失公司卡或快照时返回 `INCOMPLETE` 而非空结果；
- 现有公司卡和 Agent 上下文测试保持兼容。

**前端 Node 测试**：

- 因子状态到徽标 / 雷达档位的映射正确；
- 概览条计数渲染正确；
- 不可计算和不适用文案不被隐藏；
- 对比矩阵行列顺序稳定；
- 期间不一致时展示探索性警告；
- 点击因子 / 矩阵单元格调用现有证据弹窗入口。

**手动验收**：

- 单票生成后能看到 6 因子列表和小雷达；
- 命中规则的因子能展开看到阈值、当前观察值、证据来源；
- 同报告期两家公司对比能显示矩阵；
- 同一公司两个报告期对比能显示变化；
- 自定义混合组合有明确可比性提示。

## 十一、明确不做

- 不做 0–100 分；
- 不做经营质量总分；
- 不做行业分位数；
- 不做自动同业对比；
- 不新增行业规则包；
- 不把 Tushare 行业信息当作同业基准；
- 不做投资评级、买卖建议或估值判断；
- 不引入图表库，首版雷达可用轻量 SVG 或 CSS/SVG 手写实现。

## 十二、后续增强

只有在首版规则解释稳定后，再考虑：

- 基于人工复核结果校准连续 0–100 因子分；
- 加入行业分位、历史分位和规则权重；
- 引入研究员自定义权重；
- 扩展行业规则包；
- 把 PDF 管理层语气、市场数据和估值指标纳入新的因子或旁路模块。
