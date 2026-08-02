# Agent 后端问答接口设计(研究员人机交互闭环)

**日期**:2026-08-02
**范围**:后端 Agent 问答闭环——会话存储、单票预置上下文问答、跨票/扫描只读工具通道、带来源引用的回答契约
**不包含**:前端 UI(复用 TradeEye 现有界面)、自由文本审核器(挂起为待办)、Agent 对话之外的业务改造

## 一、目标

为研究员提供可用的 Agent 问答闭环,复用已就绪的事实契约(`facts` / `classification` / `rule_results` / `AgentFactContext`):

- Agent 理解研究员问题,回答只基于确定性数据(研判卡、汇总、扫描),不自行计算财务数字;
- 每个回答可附带结构化来源引用(`fact_id` / `evidence_id`),后端硬校验真实性,防幻觉引用;
- 支持多轮追问:一卡一会话,历史消息是唯一上下文来源;
- 跨票问题(覆盖池对比、披露汇总)通过只读工具通道解决;
- 自由文本审核器挂起为待办,不在本次范围。

## 二、现状与复用

已有:

- `copilot/models.py`:`Fact` / `FactEvidence` / `ClassificationResult` / `RuleResult` / `AgentFactContext`;
- `copilot/report/builder.py`:`CompanyCard` 含 `facts` / `classification` / `rule_results` / `card_status`;
- `copilot/llm/client.py`:`LLMClient.chat()` OpenAI 兼容,纯文本输出,失败返回 `None`;
- `copilot/config.py`:`LLMSettings`(base_url / model / api_key);
- 只读查询服务:`ReportCache`(get_company / get_daily)、`AnalyzerService`(scan / daily summary)、`SQLiteStore` 模式;
- 现有无鉴权分析接口 `/api/analyze/*`(Agent 接口沿用同一策略)。

## 三、设计原则

1. **卡是唯一事实源**:Agent 不生成数字;没有研判卡的报告期不得回答财务问题。
2. **确定性优先**:单票问答用预置上下文(数据直接注入,不靠模型检索);跨票用白名单工具,执行结果零改写。
3. **引用硬校验**:回答中的引用必须真实存在于本会话可引用集合,否则丢弃并记日志;回答正文仍是普通文本,不写回 `facts` / `findings`。
4. **一卡一会话**:会话绑定 `(ts_code, period)`,历史消息是唯一上下文来源,不做额外状态机。
5. **稳定性优先**:工具调用采用 JSON 协议而非原生 function calling,白名单 + Pydantic 参数校验 + 有限重试(1 次)。
6. **不修改 `web/`**:只扩展后端模块和 API。

## 四、架构

```
研究员提问 (ts_code, period, question, session_id?)
        ↓
┌─────────────────────────────────────────────┐
│ AgentService (copilot/agent/service.py)      │
│  · 会话查找/创建/历史组装                      │
│  · 预置上下文构建(当前卡 facts/证据/规则)     │
│  · 工具调度(白名单 + JSON 协议 + 重试)        │
│  · 回答契约解析与引用校验                      │
└─────────────────────────────────────────────┘
        ↓ 复用
┌──────────┬─────────────┬──────────────┐
│ LLMClient│ SQLite 会话  │ 现有只读后端   │
│ (现有)   │ 存储(新)     │ ReportCache/  │
│          │             │ Analyzer/    │
│          │             │ SQLiteStore  │
└──────────┴─────────────┴──────────────┘
```

新模块(集中在 `copilot/agent/`):

| 模块 | 职责 |
|---|---|
| `copilot/agent/store.py` | 会话与消息的 SQLite 持久化 |
| `copilot/agent/context.py` | 当前卡结构化数据 → LLM 预置上下文 |
| `copilot/agent/tools.py` | 工具白名单、参数模型、只读执行 |
| `copilot/agent/pipeline.py` | 问答管道:预置上下文 → (工具) → 回答解析 |
| `copilot/agent/references.py` | 引用校验(真实存在、属于本会话) |

API 挂入 `copilot/api/app.py`。

## 五、会话与存储

新增两张表(沿用 `SQLiteStore` 模式,建表在 agent store 初始化时):

**sessions**
| 字段 | 说明 |
|---|---|
| `session_id` | 主键(UUID) |
| `ts_code` | 绑定卡片 |
| `period` | 绑定报告期 |
| `created_at` | 创建时间 |
| `last_active_at` | 最近活跃,用于将来清理 |

**messages**
| 字段 | 说明 |
|---|---|
| `message_id` | 主键 |
| `session_id` | 外键 |
| `role` | `user` / `assistant` / `tool_result` |
| `content` | 文本 |
| `references` | JSON 字符串(assistant 引用 id 列表) |
| `created_at` | 排序依据 |

行为:

- **隐式建会话**:`POST /api/agent/chat` 带 `ts_code` / `period` / `question` / 可选 `session_id`;无 session_id 时按 `(ts_code, period)` 查找或创建,返回 `session_id`。session_id 与 ts_code/period 不匹配时 400 报错。
- **历史保留最近 20 轮**,超出截断(控制 token 成本)。
- 历史消息完整回放给 LLM(单票预置数据 + 历史问答)。

## 六、单票问答流程(批次 1)

```
1. 会话校验/查找/创建
2. 从 ReportCache/服务取当前卡 CompanyCard
   └ 卡不存在 → 400 "该报告期尚未生成研判卡"
3. 组装预置上下文:
   system  : Agent 行为规则(只读、引用证据、不计算数字、JSON 输出模板)
   data    : 当前卡 facts / findings / evidence / classification / rule_results
   history : 最近 N 轮消息
   user    : 研究员问题
4. LLM 一次调用 → 期望 JSON:
   {"answer": "...", "references": [{"fact_id": "..."}, {"evidence_id": "..."}]}
5. 引用校验:每个 id 必须存在于本会话可引用集合
   └ 不存在的丢弃 + 日志;全被丢弃则 answer 照常返回
6. 消息入库(user + assistant),返回 {session_id, answer, references}
```

## 七、工具通道(批次 2)

跨票/扫描问题触发工具调用,最多 2 次 LLM 调用:

```
1. LLM 调用#1 → 期望输出一行 JSON: {"tool": "<白名单名>", "args": {...}}
2. 解析失败 / 工具名不在白名单 / 参数校验失败
   → 带错误信息重试 1 次 → 仍失败返回 422 "无法理解,请换个问法"
3. 合法 → 执行只读查询(确定性,零改写)
4. 结果回填 prompt → LLM 调用#2 → 组织最终回答
```

工具白名单(全部复用现有只读能力):

| 工具 | 参数 | 查询能力 |
|---|---|---|
| `get_company_card` | `ts_code, period` | 任意票研判卡(跨票看卡) |
| `get_daily_summary` | `date` | 披露日汇总(哪几家 RED/YELLOW) |
| `get_disclosure_scan` | `date` | 披露事件列表与状态 |
| `get_session_card` | `(无)` | 当前会话绑定卡(查历史期等补充) |

约束:

- 工具结果中的事实/证据并入本次会话的"可引用集合",回答引用校验一并通过;
- 无写工具;Agent 不产生数据。

## 八、回答契约与错误处理

LLM 输出模板(system prompt 中给出):

```json
{
  "answer": "普通文本,带来源表述",
  "references": [{"fact_id": "revenue"}, {"evidence_id": "000001.SZ:20250630:revenue"}]
}
```

| 场景 | 行为 |
|---|---|
| 会话不存在 / ts_code 不匹配 | 400 明确报错 |
| 卡不存在(单票问题) | 400 "该报告期尚未生成研判卡",不生成数字 |
| 工具 JSON 解析失败 | 重试 1 次,再失败 422 "无法理解,请换个问法" |
| LLM 调用失败(`LLMClient.chat` 返回 None) | 500,前端可重试 |
| 引用不合法 | 丢弃 + 日志,不重试,不阻断回答 |
| 单票回答引用全部被丢弃 | 回答照常返回,无引用列表 |

## 九、LLM 配置(.env)

复用 `LLMSettings`,`load_settings` 增加从环境变量读取:

- `LLM_BASE_URL` → base_url
- `LLM_MODEL` → model
- `ASCEND_API_KEY` → api_key(已有)

config.yaml 保留默认值兜底;换供应商/模型改 `.env` 即可,不动代码。

## 十、API 路由

```
POST /api/agent/chat
  body: {ts_code, period, question, session_id?}
  resp: {session_id, answer, references: [{"fact_id"} | {"evidence_id"}], message_id}
```

无鉴权(与 `/api/analyze/*` 一致);不修改 `web/`。

## 十一、测试边界

1. 会话:创建/复用/ts_code 不匹配 400;
2. 历史保留最近 20 轮;
3. 单票问答:预置上下文包含卡数据;卡不存在报错;
4. 引用校验:合法引用通过、伪造引用被丢弃;
5. 工具:白名单外工具拒绝、参数非法拒绝、执行零改写、JSON 解析失败重试 1 次;
6. LLM 失败返回 500;
7. API 路由契约(请求/响应序列化);
8. 现有全量测试保持通过;`web/` 未修改。

## 十二、批次与待办

- 批次 1(本次):会话存储 + 单票预置问答 + 引用校验;
- 批次 2(本次):工具通道 + 跨票/扫描工具;
- 待办:自由文本审核器(`check_claim`,研究员自由文本判断的对照核验,辅助参考,非硬拦截);前端右侧问答栏(前端同事)。

## 十三、明确不做

- 不修改 `web/` 前端布局;
- 不实现审核器(挂起待办);
- 不允许 Agent 计算数字、选择来源或替代规则引擎;
- 不为 Agent 新增写工具;
- 不实现跨会话状态机(历史消息即上下文)。
