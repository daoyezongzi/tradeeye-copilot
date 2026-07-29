# Real Data Disclosure Event 设计文档

**日期**：2026-07-29  
**目标**：把 TradeEye Copilot 从 demo scaffold 升级为真实数据驱动的财报披露事件系统。  
**范围**：真实 Tushare 单票分析、披露日汇总、RSS trigger hint、飞书静态推送、前端 API 适配。  
**不含**：昇腾真实端点、飞书交互卡片 callback、后台常驻 scheduler、前端美化。

---

## 一、设计结论

下一阶段采用 **双触发 + 单分析链路**：

```text
稳定触发：Tushare disclosure_date → 覆盖池披露公司 → 批量研判
即时触发：RSS 财报公告 → Tushare probe → 数据就绪后研判
调试入口：ts_code + period → 单票研判
```

所有入口最终都调用同一个 `AnalyzerService.analyze_company(ts_code, period)`，避免单票、披露日、RSS 三套逻辑分叉。

RSS 不替代 Tushare。RSS 只负责发现公告和触发 probe；结构化财务数据仍以 Tushare 四表为准。

---

## 二、产品行为

### 2.1 单票调试入口

用于开发、演示、黄金样本验证。

```text
输入：ts_code + period
输出：CompanyCard
```

示例：

```http
POST /api/analyze/company
Content-Type: application/json

{
  "ts_code": "000001.SZ",
  "period": "20250630"
}
```

行为：

```text
拉本期 / 上季 / 去年同期财务快照
→ 落 SQLite
→ 装配 Context
→ hard checks
→ run rules
→ 存 findings
→ 返回 CompanyCard
```

### 2.2 披露日汇总入口

正式产品主路径之一。它不是每日固定推送，而是“某个披露日内覆盖池实际披露公司的汇总”。

```http
POST /api/analyze/disclosure-day
Content-Type: application/json

{
  "date": "20250821"
}
```

行为：

```text
disclosure_date(date)
→ 过滤 coverage_pool
→ 对命中的 ts_code + period 跑 analyze_company
→ build_daily_summary
→ 缓存最近结果
→ 返回 DailySummary
```

如果当天覆盖池没有披露：

```json
{
  "date": "20250821",
  "coverage_count": 42,
  "disclosed_count": 0,
  "red_count": 0,
  "yellow_count": 0,
  "ok_count": 0,
  "cards": []
}
```

前端显示“覆盖池今日无披露”，飞书默认不发送。

### 2.3 RSS trigger hint

RSS 用于更即时地发现公告，但只作为 trigger hint。

```http
POST /api/rss/poll
```

行为：

```text
拉 RSS entries
→ 财报公告标题识别
→ 匹配 coverage_pool
→ 推断 period
→ 去重写入 DisclosureEvent
→ probe Tushare 四表
→ 有数据：analyze_company
→ 无数据：标记 DATA_PENDING
```

RSS 命中但 Tushare 尚未更新时，不立即推研判飞书。前端展示：

```text
XX股份 2025 半年报公告已出现，等待 Tushare 结构化数据更新
```

后续可以加 retry，但本阶段只做手动 poll + 单次 probe。这样不引入后台 scheduler。

### 2.4 飞书静态推送

本阶段做 webhook 静态推送，不做交互卡片 callback。

披露日推送入口：

```http
POST /api/notify/feishu/disclosure-day/20250821
```

行为：

```text
如果最近已有该 date 的 DailySummary → 使用缓存结果
否则先 analyze_disclosure_day(date)
如果 disclosed_count = 0 → 不发送
如果 FEISHU_WEBHOOK 未配置 → 不发送，返回原因
否则 render_daily_summary_text → FeishuNotifier.send_text
```

返回：

```json
{
  "sent": true,
  "reason": "ok"
}
```

不发送示例：

```json
{
  "sent": false,
  "reason": "no_disclosures"
}
```

```json
{
  "sent": false,
  "reason": "webhook_not_configured"
}
```

---

## 三、前端适配要求

不做美化，只保留清晰接口层，方便后续换前端。

新增三个操作区：

### 3.1 单票研判

字段：

```text
股票代码 ts_code
报告期 period
[生成单票研判]
```

调用：

```javascript
api.analyzeCompany(tsCode, period)
```

### 3.2 披露日汇总

字段：

```text
披露日期 date
[生成披露日汇总]
[发送飞书]
```

调用：

```javascript
api.analyzeDisclosureDay(date)
api.sendFeishuDisclosureDay(date)
```

### 3.3 RSS 触发

按钮：

```text
[轮询 RSS]
```

调用：

```javascript
api.pollRss()
```

展示：

- 已研判 events
- DATA_PENDING events
- ignored entries 数量
- 错误信息

---

## 四、后端组件

### 4.1 `copilot/datasource/tushare_client.py`

职责：

- 从 settings/environment 创建 `tushare.pro_api`
- 不读取、不打印 token 值
- token 缺失时抛出明确错误：`TushareTokenMissing`

接口：

```python
def create_tushare_pro(token: str | None) -> object:
    """Return a tushare pro client or raise TushareTokenMissing."""
```

### 4.2 `copilot/service/analyzer.py`

核心业务服务。

接口：

```python
class AnalyzerService:
    def analyze_company(self, ts_code: str, period: str) -> CompanyAnalysisResult:
        """Analyze one company report period and return status plus optional card."""

    def analyze_disclosure_day(self, date: str) -> DailySummary:
        """Analyze all coverage-pool companies disclosed on one date."""
```

`CompanyAnalysisResult` 区分成功与失败：

```python
class CompanyAnalysisStatus(StrEnum):
    OK = "OK"
    DATA_INCOMPLETE = "DATA_INCOMPLETE"
    DATA_NOT_READY = "DATA_NOT_READY"
    ERROR = "ERROR"
```

成功时包含 `CompanyCard`；失败时包含用户可见 message。

### 4.3 `copilot/service/report_cache.py`

轻量内存缓存，方便 API 和飞书复用最近一次分析结果。

```python
class ReportCache:
    def put_company(self, card: CompanyCard) -> None:
        """Cache the latest company card by ts_code and period."""

    def get_company(self, ts_code: str, period: str) -> CompanyCard | None:
        """Return a cached company card if present."""

    def put_daily(self, summary: DailySummary) -> None:
        """Cache the latest disclosure-day summary by date."""

    def get_daily(self, date: str) -> DailySummary | None:
        """Return a cached disclosure-day summary if present."""
```

本阶段不做持久化 summary；重启后可重新生成。

### 4.4 `copilot/rss/announcements.py`

RSS 解析与公告识别。

职责：

- 解析 RSS XML
- 判断标题是否是财报公告
- 从标题推断报告期类型与 period
- 匹配覆盖池公司
- 生成 `AnnouncementEvent`

财报标题关键词：

```text
年度报告
半年度报告
第一季度报告
第三季度报告
一季报
三季报
年报
半年报
```

排除关键词：

```text
摘要
取消
更正
补充
英文版
```

`摘要` 是否排除的原因：本产品要研判正式财报，不以摘要为准。后续如需补快报/预告，可另加规则。

### 4.5 `copilot/rss/service.py`

RSS poll service。

```python
class RssPollService:
    def poll(self) -> RssPollResult:
        """Fetch configured RSS feeds, classify announcements, and probe Tushare once."""
```

职责：

```text
fetch RSS
→ parse announcements
→ dedupe
→ probe Tushare via AnalyzerService
→ return statuses
```

本阶段不做后台重试队列，只保留事件状态返回，前端可再次点击 poll。

### 4.6 `copilot/api/real_app.py`

真实运行 app。

```bash
uvicorn copilot.api.real_app:app --reload
```

`dev_app.py` 保留 demo 数据，`real_app.py` 用真实 service。

`start_demo.bat` 后续可以改为启动 `real_app.py`，但需要在 `.env` 配好 `TUSHARE_TOKEN`。为避免用户首次体验失败，本阶段可新增：

```text
start_real.bat
```

---

## 五、API 契约

### 5.1 单票分析

```http
POST /api/analyze/company
```

请求：

```json
{
  "ts_code": "000001.SZ",
  "period": "20250630"
}
```

响应成功：

```json
{
  "status": "OK",
  "message": "ok",
  "card": {"ts_code": "000001.SZ", "period": "20250630"}
}
```

响应失败：

```json
{
  "status": "DATA_NOT_READY",
  "message": "Tushare 暂未返回 000001.SZ 20250630 的完整财务快照",
  "card": null
}
```

### 5.2 披露日分析

```http
POST /api/analyze/disclosure-day
```

请求：

```json
{"date": "20250821"}
```

响应：`DailySummary`。

### 5.3 RSS poll

```http
POST /api/rss/poll
```

响应：

```json
{
  "seen_count": 12,
  "matched_count": 2,
  "analyzed_count": 1,
  "pending_count": 1,
  "events": [
    {
      "ts_code": "000001.SZ",
      "title": "平安银行：2025年半年度报告",
      "period": "20250630",
      "status": "ANALYZED"
    }
  ]
}
```

### 5.4 飞书披露日推送

```http
POST /api/notify/feishu/disclosure-day/{date}
```

响应：

```json
{"sent": true, "reason": "ok"}
```

---

## 六、配置

`.env`：

```dotenv
TUSHARE_TOKEN=...
FEISHU_WEBHOOK=...
```

`config.yaml`：

```yaml
eval:
  coverage_pool:
    - 000001.SZ

rss:
  feeds:
    - <用户配置的公告 RSS 地址>
  max_entries: 50
```

密钥只走环境变量。代码只检测变量是否存在，不打印值。

---

## 七、错误与降级

| 场景 | 行为 | 前端显示 |
|---|---|---|
| `TUSHARE_TOKEN` 未配置 | API 返回 503 | “未配置 TUSHARE_TOKEN” |
| 披露日无覆盖池公司 | 返回空 DailySummary | “覆盖池今日无披露” |
| RSS 命中但 Tushare 无数据 | event 标记 `DATA_PENDING` | “等待 Tushare 结构化数据更新” |
| 单票 hard checks 不通过 | `DATA_INCOMPLETE`，不出卡 | 显示缺失字段/校验失败原因 |
| 飞书 webhook 未配置 | `sent=false` | “未配置 FEISHU_WEBHOOK” |
| 飞书发送失败 | `sent=false` | “发送失败，可重试” |

---

## 八、测试策略

### 8.1 单元测试

- Tushare client factory：token 缺失不泄露值
- AnalyzerService：
  - 单票成功
  - 缺字段 DATA_INCOMPLETE
  - Tushare 尚无数据 DATA_NOT_READY
- disclosure day：
  - 无披露返回空 summary
  - 覆盖池过滤正确
- RSS parser：
  - 财报标题识别
  - 摘要/更正排除
  - period 推断
- Feishu notify API：
  - webhook 未配置
  - no disclosures 不发送
  - 有 summary 时发送

### 8.2 集成 smoke

- `start_real.bat` 启动真实 app
- 前端单票输入能返回 card 或明确错误
- 披露日输入能返回 summary
- RSS poll 能返回 event 列表

### 8.3 不做真实密钥测试

自动测试不读取真实 `.env`，使用 fake provider / monkeypatch。

---

## 九、不做事项

本阶段明确不做：

- 昇腾真实端点验证
- LLM 归因真实接入主卡片
- 飞书交互卡片 callback
- 飞书按钮回调
- 后台常驻 scheduler
- 自动 retry daemon
- RSS 替代 Tushare 财务数据
- 前端视觉美化

---

## 十、完成判据

- `pytest -q` 通过。
- `start_demo.bat` 仍可启动 demo。
- `start_real.bat` 可启动真实 app。
- 未配置 `TUSHARE_TOKEN` 时前端/API 给出明确错误。
- 配置 `TUSHARE_TOKEN` 后，单票分析 API 可尝试真实 Tushare 取数。
- 披露日 API 按 `coverage_pool` 过滤。
- RSS poll API 返回 matched / pending / analyzed 状态。
- 飞书披露日推送 API 在 webhook 未配置、无披露、有披露三种情况下行为明确。
- 前端所有新功能通过 `api.*` wrapper 调用后端，方便后续替换 UI。
