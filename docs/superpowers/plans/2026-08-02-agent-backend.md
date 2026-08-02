# Agent 后端问答接口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为研究员提供 Agent 问答闭环:一卡一会话、单票预置上下文问答、引用硬校验、跨票/扫描只读工具通道。

**Architecture:** 新模块集中在 `copilot/agent/`(store / context / tools / pipeline / references / contracts / exceptions),复用现有 `LLMClient`、`ReportCache`、`SQLiteStore` 模式与只读服务。单票问答一次 LLM 调用(预置上下文);跨票问题走 JSON 工具协议(白名单 + Pydantic 参数校验 + 至多 1 次重试 + 至多 2 次 LLM 调用)。回答契约 `{answer, references}`,引用真实性硬校验后返回。不修改 `web/`。

**Tech Stack:** Python 3.11+, Pydantic v2, FastAPI, sqlite3, pytest, LLMClient(OpenAI 兼容)。

---

## 文件结构

- Create: `copilot/agent/__init__.py`
- Create: `copilot/agent/exceptions.py` — 会话/卡/LLM/工具错误类型
- Create: `copilot/agent/contracts.py` — AgentReference / AgentChatRequest / AgentChatResponse
- Create: `copilot/agent/store.py` — SQLiteAgentStore(sessions / messages)
- Create: `copilot/agent/references.py` — ReferenceValidator(可引用集合 + 过滤)
- Create: `copilot/agent/context.py` — system prompt 模板 + 预置上下文构建
- Create: `copilot/agent/tools.py` — ToolRegistry 白名单与参数校验、collect_references
- Create: `copilot/agent/pipeline.py` — AgentService 问答管道 + JSON 解析
- Modify: `copilot/config.py` — `load_settings` 从 .env 读 LLM_BASE_URL / LLM_MODEL
- Modify: `copilot/api/app.py` — 注册 `POST /api/agent/chat`
- Modify: `copilot/api/real_app.py` — 构造 AgentService 并注入
- Test: `tests/test_agent_store.py`, `tests/test_agent_references.py`, `tests/test_agent_context.py`, `tests/test_agent_pipeline.py`, `tests/test_agent_tools.py`, `tests/test_api_agent_routes.py`
- Modify: `tests/test_config.py` — LLM env 读取测试
- Modify: `docs/development-log.md` — 阶段归档
- Do not modify: `web/`

---

### Task 1: 会话存储 SQLiteAgentStore

**Files:**
- Create: `copilot/agent/__init__.py`
- Create: `copilot/agent/store.py`
- Test: `tests/test_agent_store.py`

- [ ] **Step 1: 写失败测试**

`tests/test_agent_store.py`:

```python
from copilot.agent.store import AgentMessage, AgentSession, SQLiteAgentStore


def make_store(tmp_path):
    store = SQLiteAgentStore(tmp_path / "agent.sqlite")
    store.init_schema()
    return store


def test_create_or_get_session_reuses_same_card(tmp_path):
    store = make_store(tmp_path)

    first = store.create_or_get_session("000001.SZ", "20250630")
    second = store.create_or_get_session("000001.SZ", "20250630")
    other = store.create_or_get_session("000002.SZ", "20250630")

    assert first.session_id == second.session_id
    assert first.session_id != other.session_id
    assert first.ts_code == "000001.SZ"
    assert first.period == "20250630"


def test_get_session_returns_none_for_unknown(tmp_path):
    store = make_store(tmp_path)
    assert store.get_session("missing") is None


def test_append_and_list_messages_keeps_recent_rounds(tmp_path):
    store = make_store(tmp_path)
    session = store.create_or_get_session("000001.SZ", "20250630")

    for i in range(15):
        store.append_message(session.session_id, "user", f"q{i}")
        store.append_message(session.session_id, "assistant", f"a{i}", references=[{"fact_id": "revenue"}])

    recent = store.list_recent_messages(session.session_id, rounds=10)

    assert len(recent) == 20
    assert recent[0].role == "user"
    assert recent[0].content == "q5"
    assert recent[-1].content == "a14"
    assert recent[-1].references == [{"fact_id": "revenue"}]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_agent_store.py -q --basetemp=.pytest_tmp`
Expected: FAIL(ImportError: cannot import name 'SQLiteAgentStore')

- [ ] **Step 3: 实现 store**

`copilot/agent/__init__.py`(空文件)。

`copilot/agent/store.py`:

```python
from datetime import datetime
from pathlib import Path
import json
import sqlite3
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now().isoformat()


class AgentSession(BaseModel):
    session_id: str
    ts_code: str
    period: str
    created_at: str
    last_active_at: str


class AgentMessage(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    references: list[dict] = Field(default_factory=list)
    created_at: str


class SQLiteAgentStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    session_id TEXT PRIMARY KEY,
                    ts_code TEXT NOT NULL,
                    period TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_active_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_sessions_card ON agent_sessions (ts_code, period)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    references TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_messages_session ON agent_messages (session_id, created_at)"
            )

    def create_or_get_session(self, ts_code: str, period: str) -> AgentSession:
        now = _now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_sessions WHERE ts_code = ? AND period = ?",
                (ts_code, period),
            ).fetchone()
            if row is not None:
                conn.execute(
                    "UPDATE agent_sessions SET last_active_at = ? WHERE session_id = ?",
                    (now, row["session_id"]),
                )
                session = AgentSession(**dict(row), last_active_at=now)
            else:
                session = AgentSession(
                    session_id=str(uuid4()),
                    ts_code=ts_code,
                    period=period,
                    created_at=now,
                    last_active_at=now,
                )
                conn.execute(
                    "INSERT INTO agent_sessions (session_id, ts_code, period, created_at, last_active_at) VALUES (?, ?, ?, ?, ?)",
                    (session.session_id, ts_code, period, now, now),
                )
        return session

    def get_session(self, session_id: str) -> AgentSession | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return None if row is None else AgentSession(**dict(row))

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        references: list[dict] | None = None,
    ) -> AgentMessage:
        message = AgentMessage(
            message_id=str(uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            references=references or [],
            created_at=_now(),
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO agent_messages (message_id, session_id, role, content, references, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (message.message_id, session_id, role, content, json.dumps(message.references, ensure_ascii=False), message.created_at),
            )
        return message

    def list_recent_messages(self, session_id: str, rounds: int = 20) -> list[AgentMessage]:
        limit = rounds * 2
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_messages WHERE session_id = ? ORDER BY created_at DESC, message_id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        messages = [
            AgentMessage(
                message_id=row["message_id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                references=json.loads(row["references"]),
                created_at=row["created_at"],
            )
            for row in reversed(rows)
        ]
        return messages
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_agent_store.py -q --basetemp=.pytest_tmp`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add copilot/agent/__init__.py copilot/agent/store.py tests/test_agent_store.py
git commit -m "feat: persist agent sessions and messages"
```

---

### Task 2: 引用校验 ReferenceValidator

**Files:**
- Create: `copilot/agent/references.py`
- Test: `tests/test_agent_references.py`

- [ ] **Step 1: 写失败测试**

`tests/test_agent_references.py`:

```python
from copilot.agent.references import ReferenceValidator


def test_validator_keeps_registered_references():
    validator = ReferenceValidator()
    validator.register(fact_ids=["revenue", "net_profit"], evidence_ids=["000001.SZ:20250630:revenue"])

    kept = validator.filter(
        [
            {"fact_id": "revenue"},
            {"evidence_id": "000001.SZ:20250630:revenue"},
        ]
    )

    assert kept == [
        {"fact_id": "revenue"},
        {"evidence_id": "000001.SZ:20250630:revenue"},
    ]


def test_validator_drops_fake_and_foreign_references():
    validator = ReferenceValidator()
    validator.register(fact_ids=["revenue"], evidence_ids=["000001.SZ:20250630:revenue"])

    kept = validator.filter(
        [
            {"fact_id": "fake_fact"},
            {"evidence_id": "000002.SZ:20250630:revenue"},
            {"fact_id": "revenue", "evidence_id": "000001.SZ:20250630:revenue"},
        ]
    )

    assert kept == [{"fact_id": "revenue", "evidence_id": "000001.SZ:20250630:revenue"}]


def test_validator_ignores_empty():
    validator = ReferenceValidator()
    assert validator.filter([]) == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_agent_references.py -q --basetemp=.pytest_tmp`
Expected: FAIL(ImportError)

- [ ] **Step 3: 实现 references**

`copilot/agent/references.py`:

```python
from collections.abc import Iterable


class ReferenceValidator:
    """校验回答引用是否真实存在且属于本会话可引用集合。"""

    def __init__(self) -> None:
        self._facts: set[str] = set()
        self._evidence: set[str] = set()

    def register(self, fact_ids: Iterable[str] = (), evidence_ids: Iterable[str] = ()) -> None:
        self._facts.update(fact_ids)
        self._evidence.update(evidence_ids)

    def filter(self, references: list[dict]) -> list[dict]:
        kept = []
        for reference in references:
            if not isinstance(reference, dict):
                continue
            fact_id = reference.get("fact_id")
            evidence_id = reference.get("evidence_id")
            if fact_id is not None and fact_id not in self._facts:
                fact_id = None
            if evidence_id is not None and evidence_id not in self._evidence:
                evidence_id = None
            if fact_id is None and evidence_id is None:
                continue
            kept.append({"fact_id": fact_id, "evidence_id": evidence_id})
        return kept
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_agent_references.py -q --basetemp=.pytest_tmp`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add copilot/agent/references.py tests/test_agent_references.py
git commit -m "feat: validate agent answer references"
```

---

### Task 3: 预置上下文与 prompt 模板

**Files:**
- Create: `copilot/agent/context.py`
- Test: `tests/test_agent_context.py`

- [ ] **Step 1: 写失败测试**

`tests/test_agent_context.py`:

```python
from copilot.agent.context import SYSTEM_PROMPT, build_preset_context
from copilot.models import Context
from copilot.report.builder import build_company_card


def test_build_preset_context_includes_card_facts(make_snapshot):
    ctx = Context(ts_code="000001.SZ", current=make_snapshot(revenue=128.4))
    card = build_company_card(ctx, [])

    preset = build_preset_context(card)

    assert '"fact_id": "revenue"' in preset
    assert "128.4" in preset


def test_system_prompt_declares_read_only_and_output_format():
    assert "不得自行计算" in SYSTEM_PROMPT
    assert '"answer"' in SYSTEM_PROMPT
    assert "references" in SYSTEM_PROMPT
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_agent_context.py -q --basetemp=.pytest_tmp`
Expected: FAIL(ImportError)

- [ ] **Step 3: 实现 context**

`copilot/agent/context.py`:

```python
import json

from copilot.report.builder import CompanyCard


SYSTEM_PROMPT = """你是 TradeEye 财报研究助手,面向研究员。
规则:
- 只使用提供的事实和工具查询结果回答问题,不得自行计算、编造或猜测财务数字。
- 引用来源时使用 tushare 表名、报告期和字段,例如"根据 tushare.income 20250630 的 revenue"。
- 使用中文回答,简洁;不知道就说不知道。
输出格式(必须输出一个 JSON 对象):
{"answer": "回答文本", "references": [{"fact_id": "..."} 或 {"evidence_id": "..."}]}
references 只能引用提供的 fact_id 或 evidence_id。"""


def build_preset_context(card: CompanyCard) -> str:
    payload = {
        "ts_code": card.ts_code,
        "period": card.period,
        "facts": [fact.model_dump() for fact in card.facts],
        "findings": [finding.model_dump() for finding in card.findings],
        "classification": card.classification.model_dump() if card.classification is not None else None,
        "rule_results": [result.model_dump() for result in card.rule_results],
    }
    return json.dumps(payload, ensure_ascii=False)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_agent_context.py -q --basetemp=.pytest_tmp`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add copilot/agent/context.py tests/test_agent_context.py
git commit -m "feat: build agent preset context and prompt"
```

---

### Task 4: 问答管道 AgentService(单票闭环)

**Files:**
- Create: `copilot/agent/exceptions.py`
- Create: `copilot/agent/contracts.py`
- Create: `copilot/agent/pipeline.py`
- Test: `tests/test_agent_pipeline.py`

- [ ] **Step 1: 写失败测试**

`tests/test_agent_pipeline.py`:

```python
import pytest

from copilot.agent.contracts import AgentReference
from copilot.agent.exceptions import AgentCardNotFound, AgentLLMError
from copilot.agent.pipeline import AgentService, parse_agent_payload
from copilot.llm.client import ChatMessage
from copilot.models import Context
from copilot.report.builder import build_company_card


class FakeLLM:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[list[ChatMessage]] = []

    def chat(self, messages, temperature=0.2):
        self.calls.append(list(messages))
        return self.response


class FakeCardProvider:
    def __init__(self, cards=None):
        self.cards = cards or {}

    def get_company_card(self, ts_code, period):
        return self.cards.get((ts_code, period))


class FakeStore:
    def __init__(self):
        self.sessions = {}
        self.messages = []

    def create_or_get_session(self, ts_code, period):
        return self.sessions.setdefault(
            (ts_code, period),
            AgentSessionStub(ts_code=ts_code, period=period),
        )

    def get_session(self, session_id):
        for session in self.sessions.values():
            if session.session_id == session_id:
                return session
        return None

    def append_message(self, session_id, role, content, references=None):
        self.messages.append((session_id, role, content, references))

    def list_recent_messages(self, session_id, rounds=20):
        return [m for m in self.messages if m[0] == session_id][-rounds * 2:]


class AgentSessionStub:
    def __init__(self, ts_code, period):
        self.session_id = f"session-{ts_code}-{period}"
        self.ts_code = ts_code
        self.period = period


def make_service(make_snapshot, llm=None, store=None):
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    return (
        AgentService(
            store=store or FakeStore(),
            llm=llm or FakeLLM('{"answer": "ok", "references": [{"fact_id": "revenue"}]}'),
            provider=FakeCardProvider({("000001.SZ", "20250630"): card}),
        ),
        card,
    )


def test_parse_agent_payload_extracts_json_with_surrounding_text():
    payload = parse_agent_payload('prefix\n{"answer": "ok", "references": []}\nsuffix')
    assert payload == {"answer": "ok", "references": []}
    assert parse_agent_payload("not json") is None


def test_single_card_question_returns_answer_with_validated_references(make_snapshot):
    service, card = make_service(make_snapshot)
    result = service.answer_question("000001.SZ", "20250630", "营收多少?")

    assert result.answer == "ok"
    assert result.references == [AgentReference(fact_id="revenue")]
    assert result.session_id == "session-000001.SZ-20250630"
    # user 与 assistant 消息入库
    assert len(service.store.messages) == 2


def test_question_for_missing_card_raises(make_snapshot):
    service, _ = make_service(make_snapshot)
    with pytest.raises(AgentCardNotFound):
        service.answer_question("000001.SZ", "20250630", "营收多少?")


def test_fake_reference_is_dropped(make_snapshot):
    llm = FakeLLM('{"answer": "ok", "references": [{"fact_id": "fake"}, {"fact_id": "revenue"}]}')
    service, _ = make_service(make_snapshot, llm=llm)

    result = service.answer_question("000001.SZ", "20250630", "营收多少?")

    assert result.references == [AgentReference(fact_id="revenue")]


def test_llm_failure_raises_agent_llm_error(make_snapshot):
    llm = FakeLLM(None)
    service, _ = make_service(make_snapshot, llm=llm)

    with pytest.raises(AgentLLMError):
        service.answer_question("000001.SZ", "20250630", "营收多少?")
```

注意:第 3 个测试中的 `service.store.messages` —— `FakeStore.append_message` 把元组存入 `self.messages`,但测试断言 len==2 是对的(1 user + 1 assistant)。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_agent_pipeline.py -q --basetemp=.pytest_tmp`
Expected: FAIL(ImportError)

- [ ] **Step 3: 实现 exceptions 与 contracts**

`copilot/agent/exceptions.py`:

```python
class AgentCardNotFound(RuntimeError):
    pass


class AgentSessionMismatch(RuntimeError):
    pass


class AgentLLMError(RuntimeError):
    pass


class AgentToolError(RuntimeError):
    pass
```

`copilot/agent/contracts.py`:

```python
from pydantic import BaseModel, model_validator


class AgentReference(BaseModel):
    fact_id: str | None = None
    evidence_id: str | None = None

    @model_validator(mode="after")
    def validate_reference(self) -> "AgentReference":
        if self.fact_id is None and self.evidence_id is None:
            raise ValueError("reference requires fact_id or evidence_id")
        return self


class AgentChatRequest(BaseModel):
    ts_code: str
    period: str
    question: str
    session_id: str | None = None


class AgentChatResult(BaseModel):
    session_id: str
    answer: str
    references: list[AgentReference] = []
    message_id: str
```

- [ ] **Step 4: 实现 pipeline**

`copilot/agent/pipeline.py`:

```python
import json
from collections.abc import Iterable
from typing import Protocol

from copilot.agent.context import SYSTEM_PROMPT, build_preset_context
from copilot.agent.contracts import AgentChatResult, AgentReference
from copilot.agent.exceptions import AgentCardNotFound, AgentLLMError, AgentSessionMismatch
from copilot.agent.references import ReferenceValidator
from copilot.agent.store import AgentSession
from copilot.llm.client import ChatMessage
from copilot.report.builder import CompanyCard


class AgentLLM(Protocol):
    def chat(self, messages: list[ChatMessage], temperature: float = 0.2) -> str | None: ...


class CardProvider(Protocol):
    def get_company_card(self, ts_code: str, period: str) -> CompanyCard | None: ...


def parse_agent_payload(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _parse_references(payload: dict) -> list[dict]:
    raw = payload.get("references")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


class AgentService:
    def __init__(self, store, llm: AgentLLM, provider: CardProvider, max_history_rounds: int = 20):
        self.store = store
        self.llm = llm
        self.provider = provider
        self.max_history_rounds = max_history_rounds

    def answer_question(self, ts_code: str, period: str, question: str, session_id: str | None = None) -> AgentChatResult:
        session = self._resolve_session(ts_code, period, session_id)
        card = self.provider.get_company_card(ts_code, period)
        if card is None:
            raise AgentCardNotFound(f"该报告期尚未生成研判卡: {ts_code} {period}")

        preset = build_preset_context(card)
        history = self.store.list_recent_messages(session.session_id, rounds=self.max_history_rounds)
        messages = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="system", content=f"当前研判卡数据(只读):\n{preset}"),
        ]
        messages.extend(ChatMessage(role=message.role, content=message.content) for message in history)
        messages.append(ChatMessage(role="user", content=question))

        text = self.llm.chat(messages)
        if text is None:
            raise AgentLLMError("LLM 调用失败")

        payload = parse_agent_payload(text) or {}
        answer = payload.get("answer")
        if not isinstance(answer, str) or not answer:
            answer = "抱歉,我无法理解你的问题,请换个问法。"

        validator = ReferenceValidator()
        validator.register(
            fact_ids=[fact.fact_id for fact in card.facts],
            evidence_ids=[evidence.evidence_id for fact in card.facts if fact.evidence is not None for evidence in [fact.evidence]],
        )
        references = validator.filter(_parse_references(payload))

        self.store.append_message(session.session_id, "user", question)
        assistant_message = self.store.append_message(
            session.session_id,
            "assistant",
            answer,
            references=[reference.model_dump() for reference in references],
        )
        return AgentChatResult(
            session_id=session.session_id,
            answer=answer,
            references=references,
            message_id=assistant_message.message_id,
        )

    def _resolve_session(self, ts_code: str, period: str, session_id: str | None) -> AgentSession:
        if session_id is None:
            return self.store.create_or_get_session(ts_code, period)
        session = self.store.get_session(session_id)
        if session is None or session.ts_code != ts_code or session.period != period:
            raise AgentSessionMismatch("session 与公司/报告期不匹配")
        return session
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_agent_pipeline.py -q --basetemp=.pytest_tmp`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add copilot/agent/exceptions.py copilot/agent/contracts.py copilot/agent/pipeline.py tests/test_agent_pipeline.py
git commit -m "feat: answer single-card agent questions"
```

---

### Task 5: 工具通道 ToolRegistry

**Files:**
- Create: `copilot/agent/tools.py`
- Test: `tests/test_agent_tools.py`

- [ ] **Step 1: 写失败测试**

`tests/test_agent_tools.py`:

```python
import pytest

from copilot.agent.exceptions import AgentToolError
from copilot.agent.tools import ToolRegistry, collect_references


class FakeProvider:
    def __init__(self):
        self.cards = {}
        self.daily = {}
        self.scan = {}

    def get_company_card(self, ts_code, period):
        return self.cards.get((ts_code, period))

    def get_daily_summary(self, date):
        return self.daily.get(date)

    def get_disclosure_scan(self, date):
        return self.scan.get(date)


def test_unknown_tool_is_rejected():
    registry = ToolRegistry(FakeProvider())

    with pytest.raises(AgentToolError):
        registry.execute("delete_all", {})


def test_invalid_args_are_rejected():
    registry = ToolRegistry(FakeProvider())

    with pytest.raises(AgentToolError):
        registry.execute("get_company_card", {"ts_code": "000001.SZ"})


def test_get_company_card_returns_serializable_payload(make_snapshot):
    provider = FakeProvider()
    card = provider.cards.setdefault(("000001.SZ", "20250630"), None)
    from copilot.models import Context
    from copilot.report.builder import build_company_card

    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    provider.cards[("000001.SZ", "20250630")] = card
    registry = ToolRegistry(provider)

    payload = registry.execute("get_company_card", {"ts_code": "000001.SZ", "period": "20250630"})

    assert payload["ts_code"] == "000001.SZ"
    assert any(fact["fact_id"] == "revenue" for fact in payload["facts"])


def test_collect_references_walks_nested_payload():
    fact_ids, evidence_ids = collect_references(
        {"facts": [{"fact_id": "revenue", "evidence": {"evidence_id": "e1"}}]}
    )

    assert fact_ids == ["revenue"]
    assert evidence_ids == ["e1"]


def test_registry_names_are_whitelisted():
    registry = ToolRegistry(FakeProvider())
    assert set(registry.names()) == {
        "get_company_card",
        "get_daily_summary",
        "get_disclosure_scan",
    }
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_agent_tools.py -q --basetemp=.pytest_tmp`
Expected: FAIL(ImportError)

- [ ] **Step 3: 实现 tools**

`copilot/agent/tools.py`:

```python
from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from copilot.agent.exceptions import AgentToolError
from copilot.report.builder import CompanyCard, DailySummary
from copilot.service.disclosure_scan import DisclosureScanResult


class ReadOnlyProvider(Protocol):
    def get_company_card(self, ts_code: str, period: str) -> CompanyCard | None: ...
    def get_daily_summary(self, date: str) -> DailySummary | None: ...
    def get_disclosure_scan(self, date: str) -> DisclosureScanResult | None: ...


class CompanyCardArgs(BaseModel):
    ts_code: str
    period: str


class DateArgs(BaseModel):
    date: str


class ToolRegistry:
    def __init__(self, provider: ReadOnlyProvider):
        self._tools: dict[str, tuple[type[BaseModel], Callable[[dict], Any]]] = {
            "get_company_card": (
                CompanyCardArgs,
                lambda args: provider.get_company_card(args["ts_code"], args["period"]),
            ),
            "get_daily_summary": (
                DateArgs,
                lambda args: provider.get_daily_summary(args["date"]),
            ),
            "get_disclosure_scan": (
                DateArgs,
                lambda args: provider.get_disclosure_scan(args["date"]),
            ),
        }

    def names(self) -> list[str]:
        return list(self._tools)

    def execute(self, tool: str, args: dict) -> dict:
        entry = self._tools.get(tool)
        if entry is None:
            raise AgentToolError(f"未知工具: {tool}")
        args_model, callable_fn = entry
        try:
            parsed = args_model(**args)
        except ValidationError as exc:
            raise AgentToolError(f"工具参数不合法: {exc}") from exc
        result = callable_fn(parsed.model_dump())
        if result is None:
            raise AgentToolError(f"工具查询无结果: {tool}")
        return result.model_dump()


def collect_references(payload: Any, fact_ids: list[str] | None = None, evidence_ids: list[str] | None = None) -> tuple[list[str], list[str]]:
    """递归收集 payload 中所有 fact_id / evidence_id 值。"""
    if fact_ids is None:
        fact_ids = []
    if evidence_ids is None:
        evidence_ids = []
    if isinstance(payload, dict):
        if isinstance(payload.get("fact_id"), str):
            fact_ids.append(payload["fact_id"])
        if isinstance(payload.get("evidence_id"), str):
            evidence_ids.append(payload["evidence_id"])
        for value in payload.values():
            collect_references(value, fact_ids, evidence_ids)
    elif isinstance(payload, list):
        for item in payload:
            collect_references(item, fact_ids, evidence_ids)
    return fact_ids, evidence_ids
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_agent_tools.py -q --basetemp=.pytest_tmp`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add copilot/agent/tools.py tests/test_agent_tools.py
git commit -m "feat: add whitelisted read-only agent tools"
```

---

### Task 6: 管道接入工具通道

**Files:**
- Modify: `copilot/agent/pipeline.py`
- Modify: `tests/test_agent_pipeline.py`

- [ ] **Step 1: 写失败测试(追加到 test_agent_pipeline.py)**

```python
def test_tool_call_retries_then_answers(make_snapshot):
    from copilot.agent.tools import ToolRegistry

    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    other = build_company_card(Context(ts_code="000002.SZ", current=make_snapshot(ts_code="000002.SZ")), [])
    provider = FakeCardProvider({
        ("000001.SZ", "20250630"): card,
        ("000002.SZ", "20250630"): other,
    })
    store = FakeStore()
    llm = FakeLLM(
        '{"tool": "get_company_card", "args": {"ts_code": "000002.SZ", "period": "20250630"}}'
    )
    llm.response = '{"tool": "get_company_card", "args": {"ts_code": "000002.SZ", "period": "20250630"}}'
    llm.responses = [
        '{"tool": "get_company_card", "args": {"ts_code": "000002.SZ", "period": "20250630"}}',
        '{"answer": "另一家营收是 100", "references": [{"fact_id": "revenue"}]}',
    ]
    llm.chat = lambda messages, temperature=0.2: llm.responses.pop(0)

    service = AgentService(
        store=store,
        llm=llm,
        provider=provider,
        tool_registry=ToolRegistry(provider),
    )

    result = service.answer_question("000001.SZ", "20250630", "000002.SZ 营收多少?")

    assert result.answer == "另一家营收是 100"
    assert result.references == [AgentReference(fact_id="revenue")]
    assert len(llm.responses) == 0
```

注意:FakeLLM 需要支持顺序响应列表,测试里用 `llm.responses` 列表 + 覆盖 `chat`。为保证该测试可用,在测试文件顶部扩展 FakeLLM:

```python
class FakeLLM:
    def __init__(self, response: str):
        self.response = response
        self.responses: list[str] = []
        self.calls: list[list[ChatMessage]] = []

    def chat(self, messages, temperature=0.2):
        self.calls.append(list(messages))
        if self.responses:
            return self.responses.pop(0)
        return self.response
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_agent_pipeline.py -q --basetemp=.pytest_tmp`
Expected: FAIL(`TypeError: AgentService.__init__() got an unexpected keyword argument 'tool_registry'`)

- [ ] **Step 3: 实现工具通道接入 pipeline**

修改 `copilot/agent/pipeline.py`:

- `__init__` 增加 `tool_registry` 参数(`tool_registry=None` 时跳过工具通道):

```python
from copilot.agent.tools import ToolRegistry, collect_references

class AgentService:
    def __init__(self, store, llm: AgentLLM, provider: CardProvider, tool_registry: ToolRegistry | None = None, max_history_rounds: int = 20):
        self.store = store
        self.llm = llm
        self.provider = provider
        self.tool_registry = tool_registry
        self.max_history_rounds = max_history_rounds
```

- `answer_question` 中,把 LLM 调用段替换为带工具循环的调用:

```python
        text = self.llm.chat(messages)
        if text is None:
            raise AgentLLMError("LLM 调用失败")
        payload = parse_agent_payload(text) or {}

        tool_payload = payload.get("tool")
        if tool_payload is not None and self.tool_registry is not None:
            messages, extra_fact_ids, extra_evidence_ids = self._run_tool_once(
                messages, tool_payload
            )
            text = self.llm.chat(messages)
            if text is None:
                raise AgentLLMError("LLM 调用失败")
            payload = parse_agent_payload(text) or {}
        else:
            extra_fact_ids, extra_evidence_ids = [], []

        answer = payload.get("answer")
        if not isinstance(answer, str) or not answer:
            answer = "抱歉,我无法理解你的问题,请换个问法。"

        validator = ReferenceValidator()
        validator.register(
            fact_ids=list({fact.fact_id for fact in card.facts}) + extra_fact_ids,
            evidence_ids=list({evidence.evidence_id for fact in card.facts if fact.evidence is not None for evidence in [fact.evidence]}) + extra_evidence_ids,
        )
        references = validator.filter(_parse_references(payload))
```

新增私有方法(置于 `_resolve_session` 之前):

```python
    def _run_tool_once(self, messages: list[ChatMessage], tool_payload: Any) -> tuple[list[ChatMessage], list[str], list[str]]:
        if not isinstance(tool_payload, dict):
            raise AgentToolError("工具调用格式不合法")
        tool_name = tool_payload.get("tool")
        args = tool_payload.get("args")
        if not isinstance(tool_name, str) or not isinstance(args, dict):
            raise AgentToolError("工具调用格式不合法")
        result_payload = self.tool_registry.execute(tool_name, args)
        fact_ids, evidence_ids = collect_references(result_payload)
        tool_text = (
            f"工具 {tool_name} 查询结果(只读):\n"
            f"{json.dumps(result_payload, ensure_ascii=False)}\n"
            f"请基于结果回答,可引用其中的 fact_id / evidence_id。"
        )
        messages = messages + [ChatMessage(role="user", content=tool_text)]
        return messages, fact_ids, evidence_ids
```

在 `answer_question` 内对工具通道重试 1 次(解析失败时):

```python
        attempts = 0
        while True:
            text = self.llm.chat(messages)
            if text is None:
                raise AgentLLMError("LLM 调用失败")
            payload = parse_agent_payload(text) or {}
            if "tool" not in payload or self.tool_registry is None:
                break
            if attempts >= 1:
                raise AgentToolError("无法理解,请换个问法")
            attempts += 1
            try:
                messages, extra_fact_ids, extra_evidence_ids = self._run_tool_once(messages, payload["tool"])
            except AgentToolError as exc:
                messages = messages + [ChatMessage(role="user", content=f"工具调用失败: {exc},请直接回答或换个问法。")]
                attempts += 1
                if attempts > 1:
                    raise
                continue
```

完整替换 `answer_question` 的 LLM 调用段(从 `text = self.llm.chat(messages)` 到 `references = validator.filter(...)` 之间),并把 `from copilot.agent.exceptions import AgentCardNotFound, AgentLLMError, AgentSessionMismatch` 扩展为包含 `AgentToolError`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_agent_pipeline.py -q --basetemp=.pytest_tmp`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add copilot/agent/pipeline.py tests/test_agent_pipeline.py
git commit -m "feat: route cross-card questions through tool channel"
```

---

### Task 7: 配置 .env 读取 LLM 参数

**Files:**
- Modify: `copilot/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: 写失败测试(追加到 test_config.py)**

```python
def test_load_settings_reads_llm_from_env(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "database:\n  path: tmp/app.sqlite\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("ASCEND_API_KEY", "env-key")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example.com/v1")

    settings = load_settings(config_path, env_path=tmp_path / "missing.env")

    assert settings.llm.base_url == "https://llm.example.com/v1"
    assert settings.llm.model == "test-model"
    assert settings.llm.api_key == "env-key"


def test_load_settings_keeps_llm_defaults_without_env(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "database:\n  path: tmp/app.sqlite\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("ASCEND_API_KEY", raising=False)

    settings = load_settings(config_path, env_path=tmp_path / "missing.env")

    assert settings.llm.base_url == "https://maas.example.com/v1"
    assert settings.llm.model == "ascend-compatible-model"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_config.py -q --basetemp=.pytest_tmp`
Expected: FAIL(base_url 仍是默认值)

- [ ] **Step 3: 实现 load_settings 的 LLM env 注入**

修改 `copilot/config.py` 中 `load_settings`,在现有 `data.setdefault("notify", {})...` 行附近加入:

```python
    llm = data.setdefault("llm", {})
    for key, env_name in (("base_url", "LLM_BASE_URL"), ("model", "LLM_MODEL")):
        env_value = os.getenv(env_name)
        if env_value:
            llm[key] = env_value
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_config.py -q --basetemp=.pytest_tmp`
Expected: 通过(含新增 2 条)

- [ ] **Step 5: Commit**

```bash
git add copilot/config.py tests/test_config.py
git commit -m "feat: read LLM endpoint config from env"
```

---

### Task 8: API 路由 /api/agent/chat

**Files:**
- Modify: `copilot/api/app.py`
- Test: `tests/test_api_agent_routes.py`

- [ ] **Step 1: 写失败测试**

`tests/test_api_agent_routes.py`:

```python
from fastapi.testclient import TestClient

from copilot.agent.contracts import AgentChatResult, AgentReference
from copilot.agent.exceptions import AgentCardNotFound
from copilot.api.app import create_app
from copilot.models import Context
from copilot.report.builder import build_company_card


class FakeAgentService:
    def __init__(self, make_snapshot):
        self.card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])

    def answer_question(self, ts_code, period, question, session_id=None):
        if self.card is None:
            raise AgentCardNotFound("该报告期尚未生成研判卡")
        return AgentChatResult(
            session_id="s1",
            answer="营收 100 亿元。",
            references=[AgentReference(fact_id="revenue")],
            message_id="m1",
        )


def test_agent_chat_route_returns_structured_answer(make_snapshot):
    client = TestClient(create_app(FakeFullService(make_snapshot), agent_service=FakeAgentService(make_snapshot)))

    response = client.post(
        "/api/agent/chat",
        json={"ts_code": "000001.SZ", "period": "20250630", "question": "营收多少?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "s1"
    assert payload["answer"] == "营收 100 亿元。"
    assert payload["references"] == [{"fact_id": "revenue"}]
    assert "message_id" in payload


def test_agent_chat_route_returns_503_without_agent_service(make_snapshot):
    client = TestClient(create_app(FakeFullService(make_snapshot)))

    response = client.post(
        "/api/agent/chat",
        json={"ts_code": "000001.SZ", "period": "20250630", "question": "营收多少?"},
    )

    assert response.status_code == 503


def test_agent_chat_route_returns_400_for_missing_card(make_snapshot):
    class MissingCardService(FakeAgentService):
        def __init__(self, make_snapshot):
            self.card = None

    client = TestClient(create_app(FakeFullService(make_snapshot), agent_service=MissingCardService(make_snapshot)))

    response = client.post(
        "/api/agent/chat",
        json={"ts_code": "000001.SZ", "period": "20250630", "question": "营收多少?"},
    )

    assert response.status_code == 400
```

`tests/test_api_analysis_routes.py` 中的 `FakeFullService` 可复用:在该文件顶部导出,或在本测试中引用。为保持简单,在 `test_api_agent_routes.py` 中复制最小 `FakeFullService`(仅需满足 `create_app` 的类型协议,路由不调用其方法):

```python
class FakeFullService:
    def get_company_card(self, ts_code, period):
        return None

    def get_daily_summary(self, date):
        return None

    def get_evidence(self, ts_code, period, rule_id):
        return []

    def get_quarterly_review(self):
        return None

    def get_meta(self):
        return None

    def analyze_company(self, ts_code, period):
        return None

    def analyze_disclosure_day(self, date):
        return None

    def scan_disclosure_day(self, date):
        return None

    def analyze_disclosure_day_bundle(self, date):
        return None

    def start_disclosure_day_job(self, date, resume_from_job_id=None, owner_id=None):
        return None

    def run_disclosure_day_job(self, job_id):
        return None

    def list_disclosure_day_jobs(self, limit=20, owner_id=None):
        return []

    def get_disclosure_day_job(self, job_id, owner_id=None):
        return None

    def cancel_disclosure_day_job(self, job_id, owner_id=None):
        return None

    def prune_disclosure_day_jobs(self, keep_recent=20):
        return 0

    def run_disclosure_automation(self, date, notify=True):
        return None

    def poll_rss(self):
        return None

    def preview_feishu_disclosure_day(self, date):
        return None

    def notify_feishu_disclosure_day(self, date):
        return None

    def list_notify_logs(self, limit=20):
        return []

    def upsert_review_label(self, label):
        return None

    def list_review_labels(self, ts_code=None, period=None):
        return []

    def delete_review_label(self, ts_code, period, rule_id):
        return False

    def get_review_metrics(self, ts_code=None, period=None):
        return None

    def verify_feishu_callback_token(self, token):
        return True

    def verify_automation_trigger_token(self, token):
        return True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_api_agent_routes.py -q --basetemp=.pytest_tmp`
Expected: FAIL(`TypeError: create_app() got an unexpected keyword argument 'agent_service'`)

- [ ] **Step 3: 实现路由**

修改 `copilot/api/app.py`:

- 导入:

```python
from copilot.agent.contracts import AgentChatRequest, AgentChatResult
from copilot.agent.exceptions import AgentCardNotFound, AgentLLMError, AgentSessionMismatch, AgentToolError
```

- `create_app` 签名与路由:

```python
def create_app(report_service: ReportService, agent_service=None) -> FastAPI:
    ...
    @app.post("/api/agent/chat", response_model=AgentChatResult)
    def agent_chat(request: AgentChatRequest):
        if agent_service is None:
            raise HTTPException(status_code=503, detail="Agent 服务未配置")
        try:
            return agent_service.answer_question(
                request.ts_code,
                request.period,
                request.question,
                session_id=request.session_id,
            )
        except AgentCardNotFound as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except AgentSessionMismatch as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except AgentToolError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except AgentLLMError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_api_agent_routes.py tests/test_api_analysis_routes.py -q --basetemp=.pytest_tmp`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add copilot/api/app.py tests/test_api_agent_routes.py
git commit -m "feat: expose agent chat API"
```

---

### Task 9: real_app 接线与最终验证

**Files:**
- Modify: `copilot/api/real_app.py`
- Modify: `docs/development-log.md`

- [ ] **Step 1: 接线 RealReportService**

修改 `copilot/api/real_app.py`:

- 导入:

```python
from copilot.agent.pipeline import AgentService
from copilot.agent.store import SQLiteAgentStore
from copilot.agent.tools import ToolRegistry
from copilot.llm.client import LLMClient
```

- 在 `RealReportService.__init__` 中,`self.store.init_schema()` 之后添加:

```python
        self.agent_store = SQLiteAgentStore(self.settings.database.path)
        self.agent_store.init_schema()
        self.agent_service = None
        if self.settings.llm.api_key or self.settings.llm.base_url != "https://maas.example.com/v1":
            self.agent_service = AgentService(
                store=self.agent_store,
                llm=LLMClient(
                    base_url=self.settings.llm.base_url,
                    model=self.settings.llm.model,
                    api_key=self.settings.llm.api_key,
                    timeout_seconds=self.settings.llm.timeout_seconds,
                ),
                provider=self,
                tool_registry=ToolRegistry(self),
            )
```

- 文件末尾构造 app 改为:

```python
_service = RealReportService()
app = create_app(_service, agent_service=_service.agent_service)
```

- [ ] **Step 2: 验证接线与全量测试**

Run: `python -m pytest -q --basetemp=.pytest_tmp`
Expected: 全部通过(测试总数以实际结果为准)

Run: `git diff --check`
Expected: 无输出

Run: `git diff --name-only HEAD~10..HEAD -- web`
Expected: 无输出(web/ 未修改)

- [ ] **Step 3: 追加开发日志**

在 `docs/development-log.md` 顶部追加:

```markdown
### 阶段归档:Agent 后端问答接口

研究员问答闭环:一卡一会话的 SQLite 会话存储,单票问题用研判卡预置上下文回答,回答附带事实/证据引用并做真实性硬校验;跨票、披露汇总与扫描状态问题走白名单只读工具通道(JSON 协议,至多 2 次 LLM 调用)。LLM 接入从 .env 读取(LLM_BASE_URL / LLM_MODEL / ASCEND_API_KEY),config.yaml 默认值兜底;`POST /api/agent/chat` 无鉴权,与现有分析接口一致。自由文本审核器挂起为待办,不修改 `web/`。

验证:

```bash
python -m pytest -q --basetemp=.pytest_tmp
git diff --check
```

结果:

```text
<填入实际通过数量>
```
```

- [ ] **Step 4: Commit**

```bash
git add copilot/api/real_app.py docs/development-log.md
git commit -m "feat: wire agent service into real app"
```

---

## 计划自审

### Spec coverage

- 会话存储与一卡一会话:Task 1;
- 单票预置上下文问答:Task 3、Task 4;
- 引用硬校验:Task 2、Task 4;
- 工具通道与白名单:Task 5、Task 6;
- .env LLM 配置:Task 7;
- API 路由:Task 8;
- real_app 接线与验证:Task 9;
- 审核器:待办(计划外)。

### Placeholder scan

各步骤均含完整代码与命令;日志中的测试数量按实际命令输出填写,不构成占位符。

### Type consistency

- `AgentChatResult` / `AgentReference` 在 Task 4 定义,Task 8 复用;
- `AgentCardNotFound` / `AgentLLMError` / `AgentToolError` / `AgentSessionMismatch` 在 Task 4 定义,Task 6/8 复用;
- `ToolRegistry` 在 Task 5 定义,Task 6/9 复用;
- `SQLiteAgentStore` 在 Task 1 定义,Task 9 复用;
- `collect_references` 在 Task 5 定义,Task 6 复用。
