# Agent Frontend Chat Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the TradeEye Agent floating chat panel, extend the backend chat contract with safe action suggestions, and wire confirmed actions to existing data refresh flows.

**Architecture:** The backend remains read-only for Agent tools: it only returns validated `actions` in the chat response. The frontend is split into `agent-panel.js` for floating-window UI state and rendering, and `agent-chat.js` for session/action orchestration; `app.js` only wires existing APIs and card selection into these modules.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, pytest; browser-native HTML/CSS/JS; Node 24 built-in `node:test` and `node:assert` with no frontend dependencies.

---

## Files and Responsibilities

- Modify `copilot/agent/contracts.py`: add `AgentAction`, action parameter models, and `actions` to `AgentChatResult`.
- Modify `copilot/agent/context.py`: update `SYSTEM_PROMPT` to allow action suggestions in JSON output.
- Modify `copilot/agent/pipeline.py`: parse, validate, and cap actions without executing them.
- Modify `copilot/api/app.py`: expose `agent_ready` in `AppMeta`.
- Modify `copilot/api/real_app.py`: populate `agent_ready`.
- Create `tests/test_agent_actions.py`: backend action validation tests.
- Modify `tests/test_api_agent_routes.py`: API response includes `actions` and meta includes `agent_ready`.
- Create `package.json`: minimal Node test command.
- Create `web/agent-panel.js`: floating panel UI helpers, pure geometry/state functions, DOM rendering.
- Create `web/agent-chat.js`: session/context/action orchestration, pure reducer helpers.
- Create `web/agent-panel.test.mjs`: Node tests for pure panel logic.
- Create `web/agent-chat.test.mjs`: Node tests for pure chat/session/action logic.
- Modify `web/index.html`: load `agent-panel.js` and `agent-chat.js` before `app.js`.
- Modify `web/app.js`: add `api.agentChat`, initialize Agent modules, bind cards, wire action executors, expose evidence opening helper.
- Modify `web/styles.css`: add Agent floating panel styling using existing tokens.

---

### Task 1: Backend Agent action contract

**Files:**
- Modify: `copilot/agent/contracts.py`
- Modify: `copilot/agent/context.py`
- Modify: `copilot/agent/pipeline.py`
- Test: `tests/test_agent_actions.py`

- [ ] **Step 1: Write failing backend action tests**

Create `tests/test_agent_actions.py`:

```python
from copilot.agent.pipeline import AgentService
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
    def __init__(self, card):
        self.card = card

    def get_company_card(self, ts_code, period):
        return self.card


class FakeStore:
    def __init__(self):
        self.messages = []
        self.session = type(
            "Session",
            (),
            {"session_id": "session-1", "ts_code": "000001.SZ", "period": "20250630"},
        )()

    def create_or_get_session(self, ts_code, period):
        self.session.ts_code = ts_code
        self.session.period = period
        return self.session

    def get_session(self, session_id):
        return self.session if session_id == self.session.session_id else None

    def list_recent_messages(self, session_id, rounds=20):
        return []

    def append_message(self, session_id, role, content, references=None):
        self.messages.append((session_id, role, content, references or []))
        return type("Message", (), {"message_id": f"message-{len(self.messages)}"})()


def make_card(make_snapshot):
    return build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])


def make_service(make_snapshot, response):
    return AgentService(
        store=FakeStore(),
        llm=FakeLLM(response),
        provider=FakeCardProvider(make_card(make_snapshot)),
    )


def test_agent_chat_returns_valid_actions(make_snapshot):
    service = make_service(
        make_snapshot,
        '{"answer":"建议重抽。","references":[],"actions":[{"action":"refetch_company","params":{"ts_code":"000001.SZ","period":"20250630"},"reason":"研究员要求重新抓取"},{"action":"rescan_disclosure_day","params":{"date":"20250821"},"reason":"研究员要求重扫披露日"}]}',
    )

    result = service.answer_question("000001.SZ", "20250630", "再抓一遍数据")

    assert [action.action for action in result.actions] == ["refetch_company", "rescan_disclosure_day"]
    assert result.actions[0].params == {"ts_code": "000001.SZ", "period": "20250630"}
    assert result.actions[0].reason == "研究员要求重新抓取"
    assert result.actions[1].params == {"date": "20250821"}


def test_agent_chat_drops_unknown_or_invalid_actions(make_snapshot):
    service = make_service(
        make_snapshot,
        '{"answer":"已回答。","references":[],"actions":[{"action":"write_review_label","params":{"label":"TP"},"reason":"不允许"},{"action":"refetch_company","params":{"ts_code":"000001.SZ"},"reason":"缺 period"},{"action":"rescan_disclosure_day","params":{"date":"2025-08-21"},"reason":"日期格式错误"}]}',
    )

    result = service.answer_question("000001.SZ", "20250630", "帮我处理")

    assert result.actions == []
    assert result.answer == "已回答。"


def test_agent_chat_caps_actions_at_two(make_snapshot):
    service = make_service(
        make_snapshot,
        '{"answer":"三个动作只保留两个。","references":[],"actions":[{"action":"refetch_company","params":{"ts_code":"000001.SZ","period":"20250630"},"reason":"第一"},{"action":"rescan_disclosure_day","params":{"date":"20250821"},"reason":"第二"},{"action":"refetch_company","params":{"ts_code":"000002.SZ","period":"20250630"},"reason":"第三"}]}',
    )

    result = service.answer_question("000001.SZ", "20250630", "多给几个动作")

    assert len(result.actions) == 2
    assert [action.reason for action in result.actions] == ["第一", "第二"]


def test_agent_prompt_mentions_actions(make_snapshot):
    service = make_service(
        make_snapshot,
        '{"answer":"不需要重抓。","references":[],"actions":[]}',
    )

    service.answer_question("000001.SZ", "20250630", "有什么异常？")

    system_prompt = service.llm.calls[0][0].content
    assert "actions" in system_prompt
    assert "refetch_company" in system_prompt
    assert "rescan_disclosure_day" in system_prompt
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_agent_actions.py -q
```

Expected: failures because `AgentChatResult` has no `actions` field and prompt does not mention actions.

- [ ] **Step 3: Implement contract models**

Modify `copilot/agent/contracts.py` to:

```python
import re
from typing import Literal

from pydantic import BaseModel, Field, model_serializer, model_validator


_TS_CODE_RE = re.compile(r"^\d{6}\.(SZ|SH|BJ)$")
_PERIOD_RE = re.compile(r"^\d{8}$")
_DATE_RE = re.compile(r"^\d{8}$")


class AgentReference(BaseModel):
    fact_id: str | None = None
    evidence_id: str | None = None

    @model_serializer
    def serialize(self) -> dict:
        return {key: value for key, value in self.__dict__.items() if value is not None}

    @model_validator(mode="after")
    def validate_reference(self) -> "AgentReference":
        if self.fact_id is None and self.evidence_id is None:
            raise ValueError("reference requires fact_id or evidence_id")
        return self


class RefetchCompanyParams(BaseModel):
    ts_code: str
    period: str

    @model_validator(mode="after")
    def validate_params(self) -> "RefetchCompanyParams":
        if not _TS_CODE_RE.match(self.ts_code):
            raise ValueError("ts_code must look like 000001.SZ")
        if not _PERIOD_RE.match(self.period):
            raise ValueError("period must be YYYYMMDD")
        return self


class RescanDisclosureDayParams(BaseModel):
    date: str

    @model_validator(mode="after")
    def validate_params(self) -> "RescanDisclosureDayParams":
        if not _DATE_RE.match(self.date):
            raise ValueError("date must be YYYYMMDD")
        return self


class AgentAction(BaseModel):
    action: Literal["refetch_company", "rescan_disclosure_day"]
    params: dict
    reason: str

    @model_validator(mode="after")
    def validate_action(self) -> "AgentAction":
        if not self.reason.strip():
            raise ValueError("action reason required")
        if self.action == "refetch_company":
            self.params = RefetchCompanyParams(**self.params).model_dump()
        elif self.action == "rescan_disclosure_day":
            self.params = RescanDisclosureDayParams(**self.params).model_dump()
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
    actions: list[AgentAction] = Field(default_factory=list)
```

- [ ] **Step 4: Update prompt**

Modify `copilot/agent/context.py` `SYSTEM_PROMPT` output format to include actions:

```python
SYSTEM_PROMPT = """你是 TradeEye 财报研究助手,面向研究员。
规则:
- 只使用提供的事实和工具查询结果回答问题,不得自行计算、编造或猜测财务数字。
- 引用来源时使用 tushare 表名、报告期和字段,例如"根据 tushare.income 20250630 的 revenue"。
- 使用中文回答,简洁;不知道就说不知道。
- 你可以提出动作建议,但不能执行动作。只有在卡不存在、数据明显过期、或研究员明确要求重新抓取/重扫时,才在 actions 中给出建议;能用现有数据回答时 actions 必须为空数组。
- actions 最多 2 条。允许的 action 只有:
  - refetch_company: params 为 {"ts_code":"000001.SZ","period":"20250630"}
  - rescan_disclosure_day: params 为 {"date":"20250821"}
输出格式(必须输出一个 JSON 对象):
{"answer": "回答文本", "references": [{"fact_id": "..."} 或 {"evidence_id": "..."}], "actions": [{"action":"refetch_company","params":{"ts_code":"000001.SZ","period":"20250630"},"reason":"一句话说明为什么建议执行"}]}
references 只能引用提供的 fact_id 或 evidence_id。actions 只是建议,不会由你执行。"""
```

- [ ] **Step 5: Parse actions in pipeline**

Modify `copilot/agent/pipeline.py` imports and helper functions:

```python
from pydantic import ValidationError

from copilot.agent.contracts import AgentAction, AgentChatResult, AgentReference
```

Add after `_parse_references`:

```python
def _parse_actions(payload: dict, limit: int = 2) -> list[AgentAction]:
    raw = payload.get("actions")
    if not isinstance(raw, list):
        return []
    kept: list[AgentAction] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            kept.append(AgentAction(**item))
        except ValidationError:
            continue
        if len(kept) >= limit:
            break
    return kept
```

Then in `answer_question`, before `return AgentChatResult(...)`:

```python
actions = _parse_actions(payload)
```

And include it in the result:

```python
return AgentChatResult(
    session_id=session.session_id,
    answer=answer,
    references=references,
    message_id=assistant_message.message_id,
    actions=actions,
)
```

- [ ] **Step 6: Run backend action tests**

Run:

```bash
pytest tests/test_agent_actions.py -q
```

Expected: `4 passed`.

- [ ] **Step 7: Run existing agent tests**

Run:

```bash
pytest tests/test_agent_pipeline.py tests/test_agent_references.py tests/test_agent_tools.py tests/test_api_agent_routes.py -q
```

Expected: all pass.

- [ ] **Step 8: Self-review Task 1**

Check:

```bash
grep -R "write_review_label\|eval\|review" -n copilot/agent tests/test_agent_actions.py || true
pytest tests/test_agent_actions.py tests/test_agent_pipeline.py tests/test_api_agent_routes.py -q
```

Expected: grep only shows no Agent action that writes review labels; pytest passes.

- [ ] **Step 9: Commit Task 1**

```bash
git add copilot/agent/contracts.py copilot/agent/context.py copilot/agent/pipeline.py tests/test_agent_actions.py
git commit -m "$(cat <<'EOF'
feat: add Agent action suggestions

Agent remains read-only: it can return validated action suggestions, but confirmed
execution stays in the frontend against existing analysis endpoints.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Agent readiness in meta and API response coverage

**Files:**
- Modify: `copilot/api/app.py`
- Modify: `copilot/api/real_app.py`
- Modify: `tests/test_api_agent_routes.py`
- Create: `tests/test_api_meta.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_api_meta.py`:

```python
from fastapi.testclient import TestClient

from copilot.api.app import AppMeta, create_app


class FakeService:
    def get_company_card(self, ts_code, period):
        return None

    def get_daily_summary(self, date):
        return None

    def get_evidence(self, ts_code, period, rule_id):
        return []

    def get_quarterly_review(self):
        return None

    def get_meta(self):
        return AppMeta(
            coverage_count=1,
            company_names={"000001.SZ": "平安银行"},
            tushare_ready=True,
            feishu_ready=False,
            agent_ready=False,
        )

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

    def send_feishu_disclosure_day(self, date):
        return None

    def list_notify_logs(self, limit=20):
        return []

    def list_review_labels(self):
        return []

    def save_review_label(self, request):
        return None

    def delete_review_label(self, ts_code, period, rule_id):
        return None

    def get_review_metrics(self):
        return None


def test_meta_includes_agent_ready():
    client = TestClient(create_app(FakeService(), agent_service=object()))

    payload = client.get("/api/meta").json()

    assert payload["agent_ready"] is False
```

Append to `tests/test_api_agent_routes.py`:

```python

def test_agent_chat_response_includes_actions(make_snapshot):
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])

    class FakeAgent:
        def answer_question(self, ts_code, period, question, session_id=None):
            return AgentChatResult(
                session_id="session-1",
                answer="建议重抽。",
                references=[],
                message_id="message-1",
                actions=[
                    {"action": "refetch_company", "params": {"ts_code": ts_code, "period": period}, "reason": "研究员要求"}
                ],
            )

    service = FakeFullService()
    service.get_company_card = lambda ts_code, period: card
    client = TestClient(create_app(service, agent_service=FakeAgent()))

    response = client.post(
        "/api/agent/chat",
        json={"ts_code": "000001.SZ", "period": "20250630", "question": "再抓一遍"},
    )

    assert response.status_code == 200
    assert response.json()["actions"] == [
        {
            "action": "refetch_company",
            "params": {"ts_code": "000001.SZ", "period": "20250630"},
            "reason": "研究员要求",
        }
    ]
```

- [ ] **Step 2: Run tests to verify failure**

```bash
pytest tests/test_api_meta.py tests/test_api_agent_routes.py::test_agent_chat_response_includes_actions -q
```

Expected: failures because `AppMeta` lacks `agent_ready` or route serialization lacks actions until Task 1 is done.

- [ ] **Step 3: Update AppMeta**

Modify `copilot/api/app.py`:

```python
class AppMeta(BaseModel):
    coverage_count: int
    company_names: dict[str, str]
    tushare_ready: bool
    feishu_ready: bool
    agent_ready: bool = False
```

- [ ] **Step 4: Populate real app meta**

Modify `copilot/api/real_app.py` `get_meta`:

```python
    def get_meta(self):
        return AppMeta(
            coverage_count=len(self.settings.eval.coverage_pool),
            company_names=self.settings.eval.company_names,
            tushare_ready=self.analyzer is not None,
            feishu_ready=bool(self.settings.notify.feishu_webhook),
            agent_ready=self.agent_service is not None,
        )
```

- [ ] **Step 5: Run API tests**

```bash
pytest tests/test_api_meta.py tests/test_api_agent_routes.py -q
```

Expected: all pass.

- [ ] **Step 6: Self-review Task 2**

```bash
pytest tests/test_api_meta.py tests/test_api_agent_routes.py tests/test_config.py -q
```

Expected: all pass; no existing fake meta is broken by required fields because `agent_ready` has default `False`.

- [ ] **Step 7: Commit Task 2**

```bash
git add copilot/api/app.py copilot/api/real_app.py tests/test_api_meta.py tests/test_api_agent_routes.py
git commit -m "$(cat <<'EOF'
feat: expose Agent readiness in app meta

The frontend needs to disable the chat panel before the first prompt when Agent
is not configured, so app metadata now reports Agent availability explicitly.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Frontend test foundation and pure panel logic

**Files:**
- Create: `package.json`
- Create: `web/agent-panel.js`
- Create: `web/agent-panel.test.mjs`

- [ ] **Step 1: Add Node test foundation**

Create `package.json`:

```json
{
  "type": "module",
  "scripts": {
    "test": "node --test web/"
  }
}
```

- [ ] **Step 2: Write failing panel pure-logic tests**

Create `web/agent-panel.test.mjs`:

```javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  clampPanelState,
  defaultPanelState,
  isNearRightDock,
  readPanelState,
  shouldAutoScroll,
  writePanelState,
} from "./agent-panel.js";

test("isNearRightDock returns true within threshold", () => {
  assert.equal(isNearRightDock({ left: 956, width: 320, viewportWidth: 1280, threshold: 24 }), true);
  assert.equal(isNearRightDock({ left: 900, width: 320, viewportWidth: 1280, threshold: 24 }), false);
});

test("clampPanelState keeps floating window visible and sized", () => {
  const state = clampPanelState(
    { mode: "floating", open: true, left: -500, top: -200, width: 999, height: 99 },
    { width: 1280, height: 720 },
  );

  assert.equal(state.width, 560);
  assert.equal(state.height, 360);
  assert.equal(state.left, 0);
  assert.equal(state.top, 0);
});

test("clampPanelState clamps docked width only", () => {
  const state = clampPanelState(
    { mode: "docked", open: true, left: 12, top: 12, width: 999, height: 999 },
    { width: 1280, height: 720 },
  );

  assert.equal(state.mode, "docked");
  assert.equal(state.width, 560);
  assert.equal(state.height, defaultPanelState.height);
});

test("readPanelState falls back to defaults for invalid JSON", () => {
  const storage = new Map([["tradeeye.agentPanel", "not json"]]);

  assert.deepEqual(readPanelState({ getItem: (key) => storage.get(key) }), defaultPanelState);
});

test("writePanelState serializes stable state", () => {
  const storage = new Map();

  writePanelState(
    { setItem: (key, value) => storage.set(key, value) },
    { mode: "floating", open: true, left: 12, top: 24, width: 420, height: 500 },
  );

  assert.equal(
    storage.get("tradeeye.agentPanel"),
    JSON.stringify({ mode: "floating", open: true, left: 12, top: 24, width: 420, height: 500 }),
  );
});

test("shouldAutoScroll only returns true near bottom", () => {
  assert.equal(shouldAutoScroll({ scrollHeight: 1000, scrollTop: 760, clientHeight: 220 }), true);
  assert.equal(shouldAutoScroll({ scrollHeight: 1000, scrollTop: 600, clientHeight: 220 }), false);
});
```

- [ ] **Step 3: Run tests to verify failure**

```bash
npm test -- web/agent-panel.test.mjs
```

Expected: failure because `web/agent-panel.js` does not exist.

- [ ] **Step 4: Implement pure panel logic and minimal export**

Create `web/agent-panel.js` with the pure exports at top:

```javascript
const STORAGE_KEY = "tradeeye.agentPanel";
const MIN_WIDTH = 320;
const MAX_WIDTH = 560;
const MIN_HEIGHT = 360;
const MAX_HEIGHT = 720;
const DOCK_THRESHOLD = 24;
const VISIBLE_MIN_WIDTH = 120;
const VISIBLE_MIN_HEIGHT = 80;

export const defaultPanelState = {
  mode: "docked",
  open: false,
  left: 0,
  top: 72,
  width: 400,
  height: 520,
};

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

export function isNearRightDock({ left, width, viewportWidth, threshold = DOCK_THRESHOLD }) {
  return viewportWidth - (left + width) <= threshold;
}

export function clampPanelState(state, viewport) {
  const merged = { ...defaultPanelState, ...state };
  const width = clamp(Number(merged.width) || defaultPanelState.width, MIN_WIDTH, MAX_WIDTH);
  if (merged.mode === "docked") {
    return { ...defaultPanelState, ...merged, mode: "docked", width, height: defaultPanelState.height };
  }

  const height = clamp(Number(merged.height) || defaultPanelState.height, MIN_HEIGHT, Math.min(MAX_HEIGHT, viewport.height));
  const maxLeft = Math.max(0, viewport.width - VISIBLE_MIN_WIDTH);
  const maxTop = Math.max(0, viewport.height - VISIBLE_MIN_HEIGHT);
  return {
    ...defaultPanelState,
    ...merged,
    mode: "floating",
    width,
    height,
    left: clamp(Number(merged.left) || 0, 0, maxLeft),
    top: clamp(Number(merged.top) || 0, 0, maxTop),
  };
}

export function readPanelState(storage = window.localStorage) {
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return { ...defaultPanelState };
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return { ...defaultPanelState };
    return { ...defaultPanelState, ...parsed };
  } catch {
    return { ...defaultPanelState };
  }
}

export function writePanelState(storage = window.localStorage, state) {
  storage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      mode: state.mode,
      open: Boolean(state.open),
      left: Number(state.left),
      top: Number(state.top),
      width: Number(state.width),
      height: Number(state.height),
    }),
  );
}

export function shouldAutoScroll({ scrollHeight, scrollTop, clientHeight }, threshold = 40) {
  return scrollHeight - scrollTop - clientHeight < threshold;
}

export function createAgentPanel() {
  throw new Error("createAgentPanel DOM implementation is added in Task 5");
}

if (typeof window !== "undefined") {
  window.TradeEyeAgentPanel = { createAgentPanel };
}
```

- [ ] **Step 5: Run panel tests**

```bash
npm test -- web/agent-panel.test.mjs
```

Expected: all pass.

- [ ] **Step 6: Self-review Task 3**

```bash
npm test -- web/agent-panel.test.mjs
node -e "import('./web/agent-panel.js').then(m=>console.log(Object.keys(m).sort().join(',')))"
```

Expected: tests pass; exports include pure helpers and `createAgentPanel`.

- [ ] **Step 7: Commit Task 3**

```bash
git add package.json web/agent-panel.js web/agent-panel.test.mjs
git commit -m "$(cat <<'EOF'
test: add Agent panel logic tests

The floating panel needs deterministic geometry before DOM wiring, so the
clamp, docking, persistence, and scroll decisions are covered with Node tests.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Frontend chat/session pure logic

**Files:**
- Create: `web/agent-chat.js`
- Create: `web/agent-chat.test.mjs`

- [ ] **Step 1: Write failing chat pure-logic tests**

Create `web/agent-chat.test.mjs`:

```javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  actionLabel,
  createChatState,
  reduceBindCard,
  reduceChatResult,
  routeAction,
} from "./agent-chat.js";

test("bindCard starts a current group and clears session on card change", () => {
  let state = createChatState();
  state = reduceBindCard(state, { ts_code: "000001.SZ", period: "20250630", severity: "YELLOW" });
  state = reduceChatResult(state, { session_id: "session-1" });
  state = reduceBindCard(state, { ts_code: "603026.SH", period: "20250630", severity: "RED" });

  assert.equal(state.sessionId, null);
  assert.equal(state.currentKey, "603026.SH:20250630");
  assert.equal(state.groups[0].status, "past");
  assert.equal(state.groups[1].status, "current");
});

test("bindCard reuses group and session when card is unchanged", () => {
  let state = createChatState();
  state = reduceBindCard(state, { ts_code: "000001.SZ", period: "20250630", severity: "YELLOW" });
  state = reduceChatResult(state, { session_id: "session-1" });
  state = reduceBindCard(state, { ts_code: "000001.SZ", period: "20250630", severity: "YELLOW" });

  assert.equal(state.sessionId, "session-1");
  assert.equal(state.groups.length, 1);
});

test("reduceChatResult stores latest session id", () => {
  const state = reduceChatResult(createChatState(), { session_id: "session-2" });

  assert.equal(state.sessionId, "session-2");
});

test("routeAction dispatches refetch_company", async () => {
  const calls = [];
  await routeAction(
    { action: "refetch_company", params: { ts_code: "000001.SZ", period: "20250630" } },
    { refetchCompany: async (...args) => calls.push(args), rescanDisclosureDay: async () => calls.push(["bad"]) },
  );

  assert.deepEqual(calls, [["000001.SZ", "20250630"]]);
});

test("routeAction dispatches rescan_disclosure_day", async () => {
  const calls = [];
  await routeAction(
    { action: "rescan_disclosure_day", params: { date: "20250821" } },
    { refetchCompany: async () => calls.push(["bad"]), rescanDisclosureDay: async (...args) => calls.push(args) },
  );

  assert.deepEqual(calls, [["20250821"]]);
});

test("actionLabel returns readable Chinese labels", () => {
  assert.equal(actionLabel({ action: "refetch_company" }), "重新抓取单票研判卡");
  assert.equal(actionLabel({ action: "rescan_disclosure_day" }), "重扫披露日");
});
```

- [ ] **Step 2: Run tests to verify failure**

```bash
npm test -- web/agent-chat.test.mjs
```

Expected: failure because `web/agent-chat.js` does not exist.

- [ ] **Step 3: Implement pure chat logic**

Create `web/agent-chat.js`:

```javascript
export function createChatState() {
  return { sessionId: null, currentKey: null, currentCard: null, groups: [] };
}

function cardKey(card) {
  return card ? `${card.ts_code}:${card.period}` : null;
}

export function reduceBindCard(state, card) {
  const key = cardKey(card);
  if (!key) {
    return { ...state, sessionId: null, currentKey: null, currentCard: null };
  }
  if (state.currentKey === key) {
    return { ...state, currentCard: card };
  }
  const groups = state.groups.map((group) => ({ ...group, status: "past" }));
  groups.push({ key, card, status: "current" });
  return { sessionId: null, currentKey: key, currentCard: card, groups };
}

export function reduceChatResult(state, result) {
  return { ...state, sessionId: result.session_id || state.sessionId };
}

export function actionLabel(action) {
  if (action.action === "refetch_company") return "重新抓取单票研判卡";
  if (action.action === "rescan_disclosure_day") return "重扫披露日";
  return "执行动作";
}

export async function routeAction(action, executors) {
  if (action.action === "refetch_company") {
    await executors.refetchCompany(action.params.ts_code, action.params.period);
    return;
  }
  if (action.action === "rescan_disclosure_day") {
    await executors.rescanDisclosureDay(action.params.date);
    return;
  }
  throw new Error(`未知动作: ${action.action}`);
}

export function createAgentChat({ panel, api, executors }) {
  let state = createChatState();

  function bindCard(card) {
    const before = state.currentKey;
    state = reduceBindCard(state, card);
    if (!card) {
      panel.setContext(null);
      return;
    }
    if (before !== state.currentKey) {
      panel.startGroup(card);
    }
    panel.setContext(card);
  }

  async function send(question, retrying = false) {
    if (!state.currentCard) {
      panel.appendSystem("请先选择一张研判卡。");
      return;
    }
    const pending = panel.setPending(true);
    try {
      const result = await api.agentChat(
        state.currentCard.ts_code,
        state.currentCard.period,
        question,
        state.sessionId,
      );
      state = reduceChatResult(state, result);
      panel.replacePending(pending, result.answer, result.references || []);
      for (const action of result.actions || []) {
        panel.appendAction(action);
      }
    } catch (error) {
      if (!retrying && String(error.message || "").includes("session 与公司/报告期不匹配")) {
        state = { ...state, sessionId: null };
        panel.replacePending(pending, "会话已重置，正在重试…", []);
        await send(question, true);
        return;
      }
      panel.replacePending(pending, error.message || "Agent 调用失败", [], { retryQuestion: question });
    } finally {
      panel.setPending(false);
    }
  }

  async function executeAction(action, actionNode) {
    panel.setActionRunning(actionNode, true);
    try {
      await routeAction(action, executors);
      panel.setActionDone(actionNode);
      panel.appendSystem(`已执行：${actionLabel(action)}`);
    } catch (error) {
      panel.setActionRunning(actionNode, false);
      panel.appendSystem(error.message || "动作执行失败", true);
    }
  }

  panel.onSend(send);
  panel.onAction(executeAction);

  return { bindCard, clearCard: () => bindCard(null), send };
}

if (typeof window !== "undefined") {
  window.TradeEyeAgentChat = { createAgentChat };
}
```

- [ ] **Step 4: Run chat tests**

```bash
npm test -- web/agent-chat.test.mjs
```

Expected: all pass.

- [ ] **Step 5: Run all frontend tests so far**

```bash
npm test
```

Expected: panel and chat pure tests pass.

- [ ] **Step 6: Self-review Task 4**

```bash
node -e "import('./web/agent-chat.js').then(m=>console.log(Object.keys(m).sort().join(',')))"
npm test
```

Expected: exports include `createAgentChat`; tests pass.

- [ ] **Step 7: Commit Task 4**

```bash
git add web/agent-chat.js web/agent-chat.test.mjs
git commit -m "$(cat <<'EOF'
test: add Agent chat state tests

Card binding, session reuse, and action routing are isolated as deterministic
logic before wiring the browser UI.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Floating panel DOM implementation and styles

**Files:**
- Modify: `web/agent-panel.js`
- Modify: `web/styles.css`

- [ ] **Step 1: Replace placeholder DOM implementation**

In `web/agent-panel.js`, replace `createAgentPanel` with the DOM implementation below and keep all pure exports from Task 3 unchanged:

```javascript
function textNode(text) {
  return document.createTextNode(text == null ? "" : String(text));
}

function formatCard(card) {
  return `${card.ts_code} · ${card.period}`;
}

function createMessage(role, text, references = [], options = {}) {
  const node = document.createElement("div");
  node.className = `agent-message agent-message--${role}`;
  const body = document.createElement("div");
  body.className = "agent-message__body";
  for (const [index, part] of String(text || "").split("\n").entries()) {
    if (index > 0) body.append(document.createElement("br"));
    body.append(textNode(part));
  }
  node.append(body);

  if (references.length > 0) {
    const refs = document.createElement("div");
    refs.className = "agent-message__refs";
    for (const reference of references) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "agent-ref";
      chip.textContent = reference.fact_id || reference.evidence_id;
      chip.dataset.factId = reference.fact_id || "";
      chip.dataset.evidenceId = reference.evidence_id || "";
      chip.setAttribute("aria-label", `查看 ${chip.textContent} 的证据`);
      refs.append(chip);
    }
    node.append(refs);
  }

  if (options.retryQuestion) {
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "outlined agent-message__retry";
    retry.textContent = "重试";
    retry.dataset.retryQuestion = options.retryQuestion;
    node.append(retry);
  }
  return node;
}

function viewportSize() {
  return { width: window.innerWidth, height: window.innerHeight };
}

export function createAgentPanel({ mount = document.body, onSend = null, onAction = null, onReference = null } = {}) {
  let sendHandler = onSend;
  let actionHandler = onAction;
  let referenceHandler = onReference;
  let state = clampPanelState(readPanelState(), viewportSize());
  let currentGroup = null;
  let pendingCount = 0;

  const root = document.createElement("section");
  root.className = "agent-panel";
  root.setAttribute("role", "complementary");
  root.setAttribute("aria-label", "Agent 问答");

  const snap = document.createElement("div");
  snap.className = "agent-panel__snap";
  snap.hidden = true;

  const head = document.createElement("div");
  head.className = "agent-panel__head";
  head.tabIndex = 0;
  head.innerHTML = '<span class="brand-mark" aria-hidden="true"></span><strong>Agent 问答</strong><span class="agent-panel__spacer"></span>';

  const dockButton = document.createElement("button");
  dockButton.type = "button";
  dockButton.className = "text agent-panel__dock";
  dockButton.textContent = "停靠";
  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "text agent-panel__close";
  closeButton.textContent = "关闭";
  head.append(dockButton, closeButton);

  const context = document.createElement("div");
  context.className = "agent-context";
  context.textContent = "未选择研判卡";

  const log = document.createElement("div");
  log.className = "agent-log";
  log.setAttribute("aria-live", "polite");

  const form = document.createElement("form");
  form.className = "agent-input";
  const input = document.createElement("textarea");
  input.rows = 2;
  input.placeholder = "请先选择一张研判卡";
  input.disabled = true;
  const send = document.createElement("button");
  send.type = "submit";
  send.textContent = "发送";
  send.disabled = true;
  form.append(input, send);

  const resize = document.createElement("div");
  resize.className = "agent-panel__resize";
  resize.tabIndex = 0;
  resize.setAttribute("role", "separator");
  resize.setAttribute("aria-orientation", "vertical");
  resize.setAttribute("aria-label", "调整 Agent 面板宽度");

  const fab = document.createElement("button");
  fab.type = "button";
  fab.className = "agent-fab";
  fab.innerHTML = '<span class="brand-mark" aria-hidden="true"></span><span>Agent</span>';
  fab.setAttribute("aria-expanded", String(state.open));

  root.append(resize, head, context, log, form);
  mount.append(root, snap, fab);

  function persist() {
    writePanelState(window.localStorage, state);
  }

  function applyState() {
    root.classList.toggle("agent-panel--floating", state.mode === "floating");
    root.classList.toggle("agent-panel--docked", state.mode === "docked");
    root.hidden = !state.open;
    fab.hidden = state.open;
    fab.setAttribute("aria-expanded", String(state.open));
    if (state.mode === "docked") {
      root.style.top = "calc(52px + var(--space-4))";
      root.style.right = "var(--space-4)";
      root.style.bottom = "var(--space-4)";
      root.style.left = "auto";
      root.style.width = `${state.width}px`;
      root.style.height = "auto";
    } else {
      root.style.top = `${state.top}px`;
      root.style.left = `${state.left}px`;
      root.style.right = "auto";
      root.style.bottom = "auto";
      root.style.width = `${state.width}px`;
      root.style.height = `${state.height}px`;
    }
    persist();
  }

  function appendToCurrent(node) {
    const atBottom = shouldAutoScroll(log);
    const target = currentGroup?.body || log;
    target.append(node);
    if (atBottom) log.scrollTop = log.scrollHeight;
    return node;
  }

  function updateInputHeight() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question || !sendHandler) return;
    appendToCurrent(createMessage("user", question));
    input.value = "";
    updateInputHeight();
    sendHandler(question);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  input.addEventListener("input", updateInputHeight);

  log.addEventListener("click", (event) => {
    const retry = event.target.closest("[data-retry-question]");
    if (retry && sendHandler) {
      sendHandler(retry.dataset.retryQuestion);
      return;
    }
    const ref = event.target.closest(".agent-ref");
    if (ref && referenceHandler) {
      referenceHandler({ fact_id: ref.dataset.factId || null, evidence_id: ref.dataset.evidenceId || null });
    }
  });

  fab.addEventListener("click", () => {
    state = { ...state, open: true };
    applyState();
  });
  closeButton.addEventListener("click", () => {
    state = { ...state, open: false };
    applyState();
  });
  dockButton.addEventListener("click", () => {
    state = { ...state, mode: "docked" };
    applyState();
  });

  function startDrag(event) {
    if (event.button !== 0) return;
    const startX = event.clientX;
    const startY = event.clientY;
    const rect = root.getBoundingClientRect();
    const base = { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
    state = { ...state, mode: "floating", left: base.left, top: base.top, height: base.height };
    applyState();

    function move(moveEvent) {
      const next = { ...state, left: base.left + moveEvent.clientX - startX, top: base.top + moveEvent.clientY - startY };
      snap.hidden = !isNearRightDock({ left: next.left, width: next.width, viewportWidth: window.innerWidth });
      state = clampPanelState(next, viewportSize());
      applyState();
    }
    function up() {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      snap.hidden = true;
      if (isNearRightDock({ left: state.left, width: state.width, viewportWidth: window.innerWidth })) {
        state = { ...state, mode: "docked" };
        applyState();
      }
    }
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }
  head.addEventListener("mousedown", startDrag);

  function startResize(event) {
    if (event.button !== 0) return;
    event.preventDefault();
    const startX = event.clientX;
    const baseWidth = root.getBoundingClientRect().width;
    function move(moveEvent) {
      const delta = state.mode === "docked" ? startX - moveEvent.clientX : moveEvent.clientX - startX;
      state = clampPanelState({ ...state, width: baseWidth + delta }, viewportSize());
      applyState();
    }
    function up() {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    }
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }
  resize.addEventListener("mousedown", startResize);

  window.addEventListener("resize", () => {
    state = clampPanelState(state, viewportSize());
    applyState();
  });

  applyState();

  return {
    open() { state = { ...state, open: true }; applyState(); },
    close() { state = { ...state, open: false }; applyState(); },
    onSend(handler) { sendHandler = handler; },
    onAction(handler) { actionHandler = handler; },
    onReference(handler) { referenceHandler = handler; },
    startGroup(card) {
      for (const group of log.querySelectorAll(".agent-group")) {
        group.classList.remove("agent-group--current");
        group.classList.add("agent-group--past");
        const badge = group.querySelector(".agent-group__badge");
        if (badge) badge.textContent = "已切走";
      }
      const group = document.createElement("section");
      group.className = "agent-group agent-group--current";
      const headNode = document.createElement("div");
      headNode.className = "agent-group__head";
      const title = document.createElement("span");
      title.className = "agent-group__title";
      title.textContent = formatCard(card);
      const badge = document.createElement("span");
      badge.className = "agent-group__badge";
      badge.textContent = "当前";
      headNode.append(title, badge);
      const body = document.createElement("div");
      body.className = "agent-group__body";
      group.append(headNode, body);
      log.append(group);
      currentGroup = { node: group, body };
      log.scrollTop = log.scrollHeight;
    },
    setContext(card) {
      if (!card) {
        context.textContent = "未选择研判卡";
        input.placeholder = "请先选择一张研判卡";
        input.disabled = true;
        send.disabled = true;
        return;
      }
      context.textContent = `当前：${formatCard(card)}`;
      input.placeholder = "向 Agent 提问…";
      input.disabled = false;
      send.disabled = false;
    },
    appendMessage(role, text, references = [], options = {}) { return appendToCurrent(createMessage(role, text, references, options)); },
    appendSystem(text, isError = false) { return appendToCurrent(createMessage(isError ? "error" : "system", text)); },
    appendAction(action) {
      const node = document.createElement("div");
      node.className = "agent-action";
      node.innerHTML = `<div class="agent-action__eyebrow">建议动作</div><strong></strong><p></p>`;
      node.querySelector("strong").textContent = action.action === "refetch_company" ? "重新抓取单票研判卡" : "重扫披露日";
      node.querySelector("p").textContent = action.reason || "Agent 建议执行此动作。";
      const row = document.createElement("div");
      row.className = "agent-action__buttons";
      const confirm = document.createElement("button");
      confirm.type = "button";
      confirm.textContent = "确认执行";
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "outlined";
      cancel.textContent = "取消";
      row.append(confirm, cancel);
      node.append(row);
      confirm.addEventListener("click", () => actionHandler?.(action, node));
      cancel.addEventListener("click", () => node.remove());
      return appendToCurrent(node);
    },
    setPending(active) {
      pendingCount += active ? 1 : -1;
      const disabled = pendingCount > 0;
      send.disabled = disabled || input.disabled;
      if (active) {
        return appendToCurrent(createMessage("assistant", "正在思考…"));
      }
      return null;
    },
    replacePending(node, text, references = [], options = {}) {
      if (!node) return this.appendMessage("assistant", text, references, options);
      node.replaceWith(createMessage(options.retryQuestion ? "error" : "assistant", text, references, options));
    },
    setDisabled(disabled, message = "Agent 未配置") {
      input.disabled = disabled;
      send.disabled = disabled;
      input.placeholder = disabled ? message : "向 Agent 提问…";
    },
    setActionRunning(node, running) {
      for (const button of node.querySelectorAll("button")) button.disabled = running;
      node.classList.toggle("agent-action--running", running);
    },
    setActionDone(node) {
      for (const button of node.querySelectorAll("button")) button.disabled = true;
      node.classList.remove("agent-action--running");
      node.classList.add("agent-action--done");
      const first = node.querySelector("button");
      if (first) first.textContent = "已执行";
    },
  };
}
```

- [ ] **Step 2: Add panel styles**

Append to `web/styles.css`:

```css
/* ---------- Agent 浮层问答 ---------- */
.agent-panel {
  position: fixed;
  z-index: 20;
  display: flex;
  flex-direction: column;
  background: color-mix(in srgb, var(--md-sys-color-surface) 88%, transparent);
  backdrop-filter: blur(16px) saturate(150%);
  -webkit-backdrop-filter: blur(16px) saturate(150%);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-3);
  overflow: hidden;
}

.agent-panel__snap {
  position: fixed;
  top: calc(52px + var(--space-4));
  right: 0;
  bottom: var(--space-4);
  width: 3px;
  z-index: 19;
  background: var(--clay);
  border-radius: var(--radius-sm) 0 0 var(--radius-sm);
}

.agent-panel__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
  cursor: grab;
  user-select: none;
}

.agent-panel__head strong { font-family: var(--serif); font-size: 17px; }
.agent-panel__spacer { flex: 1; }
.agent-panel__resize { position: absolute; left: 0; top: 0; bottom: 0; width: 6px; cursor: ew-resize; }
.agent-panel--floating .agent-panel__resize { right: 0; left: auto; }

.agent-context {
  margin: var(--space-3) var(--space-4) 0;
  padding: var(--space-2) var(--space-3);
  border-left: 3px solid var(--clay);
  border-radius: var(--radius-sm);
  background: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface-variant);
  font-family: var(--mono);
  font-size: 12px;
}

.agent-log {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-3) var(--space-4);
}

.agent-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  padding-left: var(--space-3);
  border-left: 2px solid var(--md-sys-color-outline-variant);
}

.agent-group--current { border-left-color: var(--clay); }
.agent-group__head { display: flex; align-items: baseline; gap: var(--space-2); }
.agent-group__title { font-family: var(--mono); font-size: 12px; color: var(--md-sys-color-on-surface); }
.agent-group__badge { padding: 1px var(--space-2); border-radius: var(--radius-sm); background: var(--md-sys-color-secondary-container); color: var(--md-sys-color-on-secondary-container); font-size: 11px; }
.agent-group--current .agent-group__badge { background: var(--md-sys-color-primary); color: var(--md-sys-color-on-primary); }
.agent-group__body { display: flex; flex-direction: column; gap: var(--space-2); }

.agent-message { max-width: 88%; display: flex; flex-direction: column; gap: var(--space-1); }
.agent-message--user { align-self: flex-end; margin-left: auto; }
.agent-message--assistant, .agent-message--error, .agent-message--system { align-self: flex-start; }
.agent-message__body { padding: var(--space-2) var(--space-3); border-radius: var(--radius-lg); line-height: 1.55; font-size: 13px; }
.agent-message--user .agent-message__body { background: var(--md-sys-color-primary); color: var(--md-sys-color-on-primary); border-radius: var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg); }
.agent-message--assistant .agent-message__body { background: var(--md-sys-color-surface); border: 1px solid var(--md-sys-color-outline-variant); border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--radius-sm); }
.agent-message--system .agent-message__body { background: var(--md-sys-color-surface-container-low); color: var(--md-sys-color-on-surface-variant); border: 1px solid var(--md-sys-color-outline-variant); }
.agent-message--error .agent-message__body { background: var(--sev-red-soft); color: var(--sev-red); border: 1px solid color-mix(in srgb, var(--sev-red) 30%, transparent); }
.agent-group--past .agent-message__body { background: var(--md-sys-color-surface-container-low); color: var(--md-sys-color-on-surface-muted); }

.agent-message__refs { display: flex; flex-wrap: wrap; gap: var(--space-1); }
.agent-ref { padding: 1px var(--space-2); border: 1px solid var(--md-sys-color-outline); border-radius: var(--radius-sm); background: var(--md-sys-color-surface); color: var(--md-sys-color-on-surface-variant); font-family: var(--mono); font-size: 11px; }
.agent-message__retry { align-self: flex-start; }

.agent-action { align-self: flex-start; max-width: 88%; padding: var(--space-3); border: 1px solid var(--clay); border-radius: var(--radius-lg); background: var(--md-sys-color-surface); box-shadow: var(--shadow-1); }
.agent-action__eyebrow { margin-bottom: var(--space-1); color: var(--md-sys-color-on-surface-muted); font-size: 11px; }
.agent-action p { margin: var(--space-1) 0 var(--space-2); color: var(--md-sys-color-on-surface-variant); font-size: 13px; }
.agent-action__buttons { display: flex; gap: var(--space-2); }
.agent-action--running { opacity: 0.72; }
.agent-action--done { border-color: var(--md-sys-color-outline-variant); }

.agent-input { display: flex; gap: var(--space-2); align-items: flex-end; padding: var(--space-3) var(--space-4); border-top: 1px solid var(--md-sys-color-outline-variant); }
.agent-input textarea { flex: 1; min-height: 42px; max-height: 120px; resize: none; }

.agent-fab { position: fixed; right: var(--space-5); bottom: var(--space-5); z-index: 18; display: flex; align-items: center; gap: var(--space-2); border-radius: 999px; box-shadow: var(--shadow-3); }

@media (prefers-reduced-motion: no-preference) {
  .agent-message--assistant .agent-message__body { transition: background var(--ease), color var(--ease); }
}
```

- [ ] **Step 3: Run frontend tests**

```bash
npm test
```

Expected: pure tests still pass.

- [ ] **Step 4: Syntax-check browser modules**

```bash
node --check web/agent-panel.js
node --check web/agent-chat.js
```

Expected: no syntax errors.

- [ ] **Step 5: Self-review Task 5**

```bash
grep -n "TODO\|TBD\|opacity: .52\|\.innerHTML" web/agent-panel.js web/styles.css || true
npm test
```

Expected: no TODO/TBD/opacity `.52`; `.innerHTML` appears only for static trusted markup in `agent-panel.js`; tests pass.

- [ ] **Step 6: Commit Task 5**

```bash
git add web/agent-panel.js web/styles.css
git commit -m "$(cat <<'EOF'
feat: add floating Agent chat panel UI

The panel preserves the main workspace width by floating above content, while
supporting right docking, drag-away, snap-back, and card-grouped history.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Wire Agent panel into the TradeEye app

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`

- [ ] **Step 1: Load new scripts**

Modify `web/index.html` before `app.js`:

```html
  <script type="module" src="/agent-panel.js"></script>
  <script type="module" src="/agent-chat.js"></script>
  <script src="/components.js"></script>
  <script src="/app.js"></script>
```

`app.js` remains a classic script and waits for `window.TradeEyeAgentPanel` / `window.TradeEyeAgentChat` in `boot()` via `waitForAgentModules()` before initializing the panel.

- [ ] **Step 2: Add API method and state fields**

Modify `web/app.js` `state`:

```javascript
const state = {
  meta: { coverage_count: 0, company_names: {}, tushare_ready: false, feishu_ready: false, agent_ready: false },
  bundle: null,
  filter: "all",
  previewDate: null,
  activeJobId: null,
  jobPollTimer: null,
  reviewLabels: {},
  agent: null,
  agentPanel: null,
};
```

Add to `api`:

```javascript
  async agentChat(tsCode, period, question, sessionId = null) {
    const payload = { ts_code: tsCode, period, question };
    if (sessionId) payload.session_id = sessionId;
    return requestJson("/api/agent/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
```

- [ ] **Step 3: Add Agent module wait helper**

Add near utility functions:

```javascript
async function waitForAgentModules() {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (window.TradeEyeAgentPanel?.createAgentPanel && window.TradeEyeAgentChat?.createAgentChat) return;
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  throw new Error("Agent 前端模块未加载");
}
```

- [ ] **Step 4: Add evidence opening helper**

Add near `showEvidence`:

```javascript
async function showAgentReference(reference) {
  if (reference.evidence_id) {
    evidenceContent.textContent = JSON.stringify(reference, null, 2);
    evidenceDialog.showModal();
    return;
  }
  if (reference.fact_id) {
    evidenceContent.textContent = JSON.stringify(reference, null, 2);
    evidenceDialog.showModal();
  }
}
```

This v1 displays the validated reference object because `/api/evidence/{ts_code}/{period}/{rule_id}` is finding-rule based, not `fact_id` based. Do not invent a backend endpoint in this task.

- [ ] **Step 5: Initialize Agent modules**

Add function in `web/app.js`:

```javascript
function initAgentPanel() {
  const panel = window.TradeEyeAgentPanel.createAgentPanel({
    mount: document.body,
    onReference: showAgentReference,
  });
  const chat = window.TradeEyeAgentChat.createAgentChat({
    panel,
    api,
    executors: {
      refetchCompany: async (tsCode, period) => {
        navigate(`#/company/${tsCode}/${period}`);
        await loadCompany(tsCode, period);
      },
      rescanDisclosureDay: async (date) => {
        el("disclosure-date").value = toInputDate(date);
        navigate("#/workbench");
        await loadDisclosureDay(date);
      },
    },
  });
  state.agentPanel = panel;
  state.agent = chat;
  if (!state.meta.agent_ready) {
    panel.setDisabled(true, "Agent 未配置 LLM");
  }
}
```

Modify `boot()` after `await loadMeta();`:

```javascript
  await waitForAgentModules();
  initAgentPanel();
```

- [ ] **Step 6: Bind cards on render and single company load**

In `renderCard(card, options = {})`, after creating `head` click behavior, add binding without breaking expand:

```javascript
  node.addEventListener("click", () => state.agent?.bindCard({ ts_code: card.ts_code, period: card.period, severity: key }));
```

In `loadCompany`, after rendering `result.card`:

```javascript
      state.agent?.bindCard({ ts_code: result.card.ts_code, period: result.card.period, severity: severityKey(result.card) });
```

If `result.card` is absent, do not bind.

- [ ] **Step 7: Run syntax checks**

```bash
node --check web/app.js
node --check web/agent-panel.js
node --check web/agent-chat.js
```

Expected: no syntax errors.

- [ ] **Step 8: Run frontend tests**

```bash
npm test
```

Expected: all pass.

- [ ] **Step 9: Self-review Task 6**

```bash
grep -n "agentChat\|initAgentPanel\|bindCard\|agent_ready" web/app.js web/index.html
node --check web/app.js
npm test
```

Expected: all grep targets present, syntax and tests pass.

- [ ] **Step 10: Commit Task 6**

```bash
git add web/index.html web/app.js
git commit -m "$(cat <<'EOF'
feat: wire Agent chat panel into web app

The existing workspace now binds clicked cards to the Agent panel and confirms
Agent-suggested refresh actions through the existing analysis flows.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Full verification and final self-review

**Files:**
- No planned source changes unless verification finds a concrete bug.

- [ ] **Step 1: Run focused backend tests**

```bash
pytest tests/test_agent_actions.py tests/test_agent_pipeline.py tests/test_agent_references.py tests/test_agent_tools.py tests/test_api_agent_routes.py tests/test_api_meta.py -q
```

Expected: all pass.

- [ ] **Step 2: Run focused frontend tests and syntax checks**

```bash
npm test
node --check web/app.js
node --check web/agent-panel.js
node --check web/agent-chat.js
```

Expected: all pass / no syntax errors.

- [ ] **Step 3: Run full pytest suite**

```bash
pytest -q
```

Expected: all pass.

- [ ] **Step 4: Manual app smoke test**

Run the app with the repository's existing command if available, otherwise use the FastAPI entrypoint used by this project:

```bash
python -m uvicorn copilot.api.real_app:app --reload
```

Open the local app, then verify:

1. Agent pill appears at bottom-right.
2. Opening the panel shows floating docked panel, not a squeezed main layout.
3. Clicking a rendered company card changes context to `ts_code · period` and starts a current group.
4. Sending a question shows user bubble + pending assistant bubble.
5. 503 Agent unavailable disables input if LLM is not configured.
6. If a mocked/real response includes `actions`, action card appears and confirm calls existing progress UI.

Stop the app after smoke test.

- [ ] **Step 5: Final self-review**

```bash
git diff --stat HEAD~6..HEAD
git status --short
grep -R "TODO\|TBD\|/rescan\|StreamingResponse" -n copilot/agent copilot/api web tests package.json || true
grep -R "write_review_label\|review label" -n copilot/agent copilot/api web package.json || true
pytest tests/test_agent_actions.py tests/test_api_agent_routes.py -q
npm test
```

Expected:

- no TODO/TBD;
- no slash command;
- no streaming references;
- no review-label action in production code (negative backend tests may mention rejected review labels);
- tests pass;
- working tree clean after commits.

- [ ] **Step 6: Prepare final report**

Report:

- commit list;
- files changed;
- verification commands and outcomes;
- any known limitations from the spec (`no slash commands`, `no streaming`, `reference chip v1 shows reference object because no fact/evidence endpoint exists`).
