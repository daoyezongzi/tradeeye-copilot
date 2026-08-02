# 研判卡持久化读取修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Agent 在服务重启后仍能从 SQLite 读取已生成的 `CompanyCard`，解决 `600151.SH 20250630` 已有数据但被误报“尚未生成研判卡”的问题。

**Architecture:** `CompanyCard` 作为分析产物序列化保存到 SQLite 新增的 cards 表；`RealReportService` 在写入内存 `ReportCache` 的同时写入持久化存储，并在缓存未命中时回读。现有快照和 findings 表继续保留其职责，Agent 查询仍经过 `ReportService`，不直接访问数据库。

**Tech Stack:** Python 3.11+, Pydantic, SQLite, pytest, FastAPI service layer.

---

### Task 1: 为研判卡存储增加失败回归测试

**Files:**
- Modify: `tests/test_store_sqlite.py`
- Modify: `tests/test_report_cache.py`（确认缓存行为不变时补充服务边界测试，若已有覆盖则不改）

- [ ] **Step 1: 写失败测试**

在 `tests/test_store_sqlite.py` 增加 `test_store_round_trips_company_card`：用 `make_snapshot` 构造 `Context` 和 `build_company_card`，调用 `SQLiteStore.upsert_company_card`，再用新的 `get_company_card` 读取，并断言完整 Pydantic 对象相等。

测试应覆盖 `CompanyCard` 的 facts、card_status、findings、rule_results，而不是只断言股票代码和报告期。

- [ ] **Step 2: 运行测试确认失败**

运行：

```bash
python -m pytest tests/test_store_sqlite.py::test_store_round_trips_company_card -q
```

预期：FAIL，原因是 `SQLiteStore` 尚未提供 `upsert_company_card` / `get_company_card`。

- [ ] **Step 3: 提交测试变更**

仅在代码实现前保留失败测试，不提交 git commit，继续下一任务完成红绿循环。

---

### Task 2: 实现 SQLite 研判卡持久化

**Files:**
- Modify: `copilot/store/sqlite.py`
- Test: `tests/test_store_sqlite.py`

- [ ] **Step 1: 增加 cards 表 schema**

在 `SQLiteStore.init_schema()` 中新增：

```sql
CREATE TABLE IF NOT EXISTS company_cards (
    ts_code TEXT NOT NULL,
    period TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (ts_code, period)
)
```

- [ ] **Step 2: 增加写入和读取方法**

在 `SQLiteStore` 中增加：

```python
def upsert_company_card(self, card: CompanyCard) -> None:
    payload = card.model_dump_json()
    with self._connect() as conn:
        conn.execute(
            """
            INSERT INTO company_cards (ts_code, period, payload)
            VALUES (?, ?, ?)
            ON CONFLICT(ts_code, period) DO UPDATE SET payload = excluded.payload
            """,
            (card.ts_code, card.period, payload),
        )

def get_company_card(self, ts_code: str, period: str) -> CompanyCard | None:
    with self._connect() as conn:
        row = conn.execute(
            "SELECT payload FROM company_cards WHERE ts_code = ? AND period = ?",
            (ts_code, period),
        ).fetchone()
    if row is None:
        return None
    return CompanyCard.model_validate_json(row["payload"])
```

导入 `CompanyCard`，保持现有 SQLite 连接和 upsert 风格，不从快照/findings 临时重建卡。

- [ ] **Step 3: 运行存储测试确认绿色**

运行：

```bash
python -m pytest tests/test_store_sqlite.py -q
```

预期：原有测试和新增回归测试全部 PASS。

---

### Task 3: 让 RealReportService 使用持久化卡并在缓存未命中时恢复

**Files:**
- Modify: `copilot/api/real_app.py`
- Create or modify: `tests/test_real_app_card_persistence.py`（优先复用现有测试结构；若现有测试无合适 service fixture，则创建最小单元测试）

- [ ] **Step 1: 写服务边界失败测试**

测试行为：构造一个真实 `SQLiteStore` 和 `ReportCache`，把完整 `CompanyCard` 写入 SQLite；新建一个空 `ReportCache` 的 service double，调用 `get_company_card("000001.SZ", "20250630")`，断言返回原卡并且卡已回填内存缓存。

测试目标是验证“进程重启后的空缓存 → SQLite → Agent provider”路径，而不是测试字典本身。

- [ ] **Step 2: 运行测试确认失败**

运行：

```bash
python -m pytest tests/test_real_app_card_persistence.py -q
```

预期：FAIL，当前 `get_company_card()` 只调用 `self.cache.get_company()`，不会读取 SQLite。

- [ ] **Step 3: 写入卡时同时持久化**

在 `RealReportService.analyze_company()` 中，当前 `result.card is not None` 分支改为先调用 `self.store.upsert_company_card(result.card)`，再 `self.cache.put_company(result.card)`。

在 `_cache_bundle()` 的每张卡循环中同样持久化，然后写缓存：

```python
for card in bundle.summary.cards:
    self.store.upsert_company_card(card)
    self.cache.put_company(card)
```

- [ ] **Step 4: 缓存未命中时从 SQLite 恢复**

将 `get_company_card()` 改为：先查缓存；命中直接返回；未命中调用 `self.store.get_company_card()`；数据库命中后回填 `ReportCache` 并返回；两者都未命中返回 `None`。

不要在 Agent 查询路径自动重新请求 Tushare，避免 Agent 问答产生隐式写操作、延迟和数据漂移。

- [ ] **Step 5: 运行服务边界测试确认绿色**

运行：

```bash
python -m pytest tests/test_real_app_card_persistence.py -q
```

预期：新增测试 PASS。

---

### Task 4: 全量回归和指定数据验证

**Files:**
- No additional production files.

- [ ] **Step 1: 运行相关测试**

```bash
python -m pytest tests/test_store_sqlite.py tests/test_agent_pipeline.py tests/test_api_agent_routes.py tests/test_analyzer_service.py tests/test_disclosure_analysis_bundle.py tests/test_report_cache.py tests/test_real_app_card_persistence.py -q
```

预期：全部 PASS。

- [ ] **Step 2: 检查本地 SQLite 迁移结果**

运行 Python 检查 `company_cards` 表和指定记录：

```bash
python -c "import sqlite3; c=sqlite3.connect('data/tradeeye_copilot.sqlite'); print(c.execute(\"select name from sqlite_master where type='table' and name='company_cards'\").fetchone()); print(c.execute(\"select ts_code, period from company_cards where ts_code='600151.SH' and period='20250630'\").fetchall()); c.close()"
```

预期：表存在；若当前服务尚未重新执行分析，指定卡可能尚未迁移入新表，此时通过现有单票分析或披露扫描写入后再验证。

- [ ] **Step 3: 运行完整测试套件**

```bash
python -m pytest -q
```

预期：退出码 0，0 failed。

- [ ] **Step 4: 检查 diff，确认只包含本 bug 所需改动**

```bash
git diff -- copilot/store/sqlite.py copilot/api/real_app.py tests/test_store_sqlite.py tests/test_real_app_card_persistence.py
```

确认不覆盖用户已有修改，不提交 `.pytest-review-tmp/`。
