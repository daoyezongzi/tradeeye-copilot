# Agent 事实输出接口设计

**日期**：2026-08-01  
**范围**：后端接口与结构化数据契约  
**不包含**：前端 UI 改造、PlatoAcademy 界面迁移、Agent 自由文本审核器实现

## 一、目标

为研究员问答 Agent 预留可靠的事实上下文接口，同时保持现有 TradeEye 研判卡和前端兼容：

- Agent 不直接计算财务数字；
- 财务数字和规则结果来自工具、硬校验与规则引擎；
- 每个可输出事实绑定报告期和来源；
- 现有 `CompanyCard` 字段保持不变；
- 新前端可以根据结构化事实实现研判卡事实高亮；
- Agent 回答本身不是高亮对象；
- 本阶段不修改 `web/`，只扩展后端模型和接口。

## 二、现状与问题

当前 `CompanyCard` 以 `fact_line: str` 承载财务摘要，以 `findings: list[Finding]` 承载规则结果。`Finding.evidence` 能够为异常规则提供证据，但 `fact_line` 中的营业收入、净利润、扣非净利润、毛利率和经营现金流没有逐项结构化证据。

因此，前端无法安全地从 `fact_line` 中定位事实并建立证据链接；如果 Agent 或前端从展示字符串反推数字和来源，就可能出现事实与证据错配。`fact_line` 继续保留用于旧前端兼容，但不再作为事实主数据来源。

当前行业判断来自配置中的公司级 `company_industries`。本设计改为优先复用 Tushare 公司基础资料提供的外部行业标签，再使用少量内部映射选择特殊规则 profile；没有映射时使用现有 generic 通用规则。未映射行业不被宣称为某个具体行业，也不因未知而猜测特殊口径。

## 三、设计原则

### 3.1 事实与展示分离

`fact_line` 是兼容展示字符串；新增 `facts` 是唯一的结构化事实接口。前端不得从 `fact_line` 解析数字来建立证据关系。

### 3.2 证据先于渲染

事实只有在具备数值、单位、报告期、工具来源、字段和审核状态时，才可标记为 `VERIFIED`。没有完整证据的事实不得作为已验证事实渲染，也不得被 Agent 当作事实输入。

### 3.3 局部阻断

普通事实不可用时，只阻断该事实及依赖它的规则结果；其他已验证事实仍可进入研判卡。核心身份、报告期或规则上下文无法确认时，才阻断整张卡。

### 3.4 不适用与不可用分离

已映射的特殊 profile 可以确定字段或规则不适用；没有行业映射时，不能由空值推断“不适用”。此时字段或规则只能进入 `UNAVAILABLE` / `NOT_EVALUATED` 状态。

### 3.5 规则结果语义严格

- `HIT`：输入完整，规则条件成立；
- `MISS`：输入完整，规则条件不成立；
- `NOT_EVALUATED`：缺少所需事实或上下文，未执行规则；
- `BLOCKED`：由于核心数据或 profile 状态，禁止输出该规则结论。

数据不足时不能用 `MISS` 代替“没有发现异常”。

## 四、接口模型

### 4.1 保留的 CompanyCard 字段

以下现有字段保持名称、类型和原有语义：

```python
class CompanyCard(BaseModel):
    ts_code: str
    period: str
    fact_line: str
    findings: list[Finding]
    attribution: str | None = None
    market_line: str = "市场数据待接入"
    max_severity: Severity | None = None
    max_score: float = 0.0
```

新字段只追加，不删除或改造旧字段。旧前端可以忽略未知字段，继续渲染 `fact_line` 和 `findings`。

### 4.2 CompanyIdentity

用于记录公司身份的工具来源，不作为财务报告期证据的替代品：

```python
class CompanyIdentity(BaseModel):
    ts_code: str
    name: str | None = None
    provider: str
    name_field: str | None = None
    retrieved_at: str | None = None
```

推荐来源为 Tushare 公司基础资料工具（例如 `stock_basic`）。如果公司资料调用失败，身份字段不能由 Agent 根据证券代码或自然语言猜测。

### 4.3 ClassificationResult

```python
class MappingStatus(StrEnum):
    MAPPED = "MAPPED"
    UNMAPPED = "UNMAPPED"
    UNAVAILABLE = "UNAVAILABLE"
    CONFLICT = "CONFLICT"


class ClassificationResult(BaseModel):
    provider: str
    provider_industry: str | None = None
    mapping_status: MappingStatus
    rule_profile_id: str = "generic"
    industry_field: str | None = None
    source_value: str | None = None
    retrieved_at: str | None = None
```

语义：

- `MAPPED`：Tushare 行业标签命中已配置的 TradeEye 特殊 profile；
- `UNMAPPED`：Tushare 返回行业标签，但内部没有特殊映射，使用现有 generic 通用规则；
- `UNAVAILABLE`：行业资料工具没有返回可用分类，仍可尝试 generic 通用规则，但不能输出具体行业结论；
- `CONFLICT`：来源之间冲突，行业特殊规则不得执行，使用 generic 通用规则或阻断相关规则。

`generic` 表示“通用规则 profile”，不表示已经确认公司属于某个普通行业。

### 4.4 FactStatus 与 Fact

```python
class FactStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FactEvidence(BaseModel):
    evidence_id: str
    source: str
    field: str
    period: str
    value: float | str


class Fact(BaseModel):
    fact_id: str
    label: str
    value: float | str | None = None
    unit: str | None = None
    period: str
    status: FactStatus
    evidence: FactEvidence | None = None
    reason_code: str | None = None
    reason: str | None = None
```

约束：

- `VERIFIED` 必须有 `value` 和 `evidence`；
- `evidence.period` 必须与事实的 `period` 一致；
- `evidence.value` 必须与事实 `value` 一致；
- `UNAVAILABLE` / `INVALID` 可以没有证据值，但必须有诊断原因；
- `NOT_APPLICABLE` 只能由已映射的特殊 profile 产生，不能由 Agent 或空值推断；
- 前端事实高亮只针对 `VERIFIED` 事实。

### 4.5 RuleResult

```python
class RuleResultStatus(StrEnum):
    HIT = "HIT"
    MISS = "MISS"
    NOT_EVALUATED = "NOT_EVALUATED"
    BLOCKED = "BLOCKED"


class RuleResult(BaseModel):
    rule_id: str
    status: RuleResultStatus
    required_fact_ids: list[str] = Field(default_factory=list)
    related_fact_ids: list[str] = Field(default_factory=list)
    reason_code: str | None = None
    reason: str | None = None
```

已有 `Finding` 继续作为命中异常的展示对象；`RuleResult` 用于表达命中、未命中和未评估的完整规则执行状态，避免只返回异常结果导致前端无法区分“未命中”和“未评估”。

### 4.6 CardStatus 与扩展后的 CompanyCard

```python
class CardStatus(StrEnum):
    OK = "OK"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


class CompanyCard(BaseModel):
    # 现有字段全部保留
    ts_code: str
    period: str
    fact_line: str
    findings: list[Finding]
    attribution: str | None = None
    market_line: str = "市场数据待接入"
    max_severity: Severity | None = None
    max_score: float = 0.0

    # 新增字段使用兼容默认值
    company: CompanyIdentity | None = None
    classification: ClassificationResult | None = None
    card_status: CardStatus = CardStatus.OK
    facts: list[Fact] = Field(default_factory=list)
    rule_results: list[RuleResult] = Field(default_factory=list)
```

### 4.7 Agent 上下文预留

本阶段不实现 Agent 对话接口，但研判卡必须能提供稳定的事实上下文标识：

```python
class AgentFactContext(BaseModel):
    ts_code: str
    period: str
    fact_id: str | None = None
    rule_id: str | None = None
    evidence_id: str | None = None
```

后续右侧问答栏可将 `AgentFactContext` 与研究员问题一起提交。Agent 回答仍是普通文本，不参与研判卡事实高亮，不得反向覆盖 `facts`、`findings` 或 `rule_results`。

## 五、数据流与行业映射

```text
Tushare 财务工具 + Tushare 公司基础资料
          ↓
结构化快照与身份/行业来源记录
          ↓
内部行业标签映射
  已映射 → 特殊 profile
  未映射 → generic 通用 profile
          ↓
事实状态审核
          ↓
规则依赖检查
          ↓
RuleResult + Finding + Evidence
          ↓
兼容 fact_line + 结构化 CompanyCard
```

行业映射只维护外部标签到内部 profile 的少量关系，例如：

```yaml
industry_profiles:
  银行: bank_v1
```

不维护每家公司到行业 profile 的重复映射。Tushare 行业标签不等于内部 profile；映射过程必须是确定性的，Agent 不参与选择。

### 5.1 字段缺失处理

- 特殊 profile 明确声明字段不适用：生成 `NOT_APPLICABLE`，相关规则不执行；
- 普通 profile 或未映射行业未返回字段：生成 `UNAVAILABLE`，依赖该字段的规则为 `NOT_EVALUATED`；
- 工具返回值但硬校验失败：生成 `INVALID`，依赖规则为 `NOT_EVALUATED`；
- 普通事实缺失时卡片可以为 `PARTIAL`；
- 核心身份、报告期或规则上下文缺失时卡片为 `BLOCKED`。

## 六、接口兼容性

本阶段不修改 `web/`。现有 API 的 `CompanyCard` 响应会增加字段，但不改变旧字段，因此当前前端可继续工作。

后续前端可：

- 使用 `facts[].fact_id` 将研判卡事实渲染为超链接式高亮；
- 使用 `facts[].evidence` 获取报告期、来源、字段和原始值；
- 将 `AgentFactContext` 传给右侧 Agent；
- 使用 `rule_results` 区分 `MISS` 与 `NOT_EVALUATED`。

前端不得：

- 从 `fact_line` 正则提取数字作为证据；
- 把 Agent 自由文本中的数字写回研判卡；
- 把 `NOT_EVALUATED` 渲染成“未见异常”。

## 七、测试边界

必须覆盖：

1. 旧 `CompanyCard` 数据不带新增字段时仍可解析；
2. 新增 `facts`、`classification` 和 `rule_results` 能正确序列化；
3. `VERIFIED` 事实缺少证据或报告期不一致时被拒绝；
4. `UNAVAILABLE` 和 `INVALID` 不生成 `MISS`；
5. 已映射特殊 profile 可以产生 `NOT_APPLICABLE`；
6. 未映射行业使用 generic，不声称已确认普通行业；
7. 普通事实缺失时卡片为 `PARTIAL`，其他事实仍保留；
8. 核心上下文缺失时卡片为 `BLOCKED`；
9. 现有前端产品化测试和全量后端测试保持通过；
10. 本次变更不修改 `web/`。

## 八、明确不做

- 不实现 PlatoAcademy 的前端 UI；
- 不修改 TradeEye 当前前端布局；
- 不实现 AI 二次审核作为硬拦截器；
- 不允许 Agent 计算数字、选择来源或替代规则引擎；
- 不为所有行业维护完整规则模板；
- 不从字段缺失直接推断行业；
- 不提供买卖建议。
