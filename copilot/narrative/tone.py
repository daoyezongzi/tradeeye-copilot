import json
from typing import Protocol

from pydantic import BaseModel, ValidationError

from copilot.llm.client import ChatMessage
from copilot.models import Evidence, Finding, Severity


class ToneComparisonResult(BaseModel):
    weakened: bool
    reason: str
    evidence: str


class ChatClient(Protocol):
    def chat(self, messages: list[ChatMessage], temperature: float = 0.2) -> str | None: ...


def _build_prompt(current_period: str, prior_period: str, current_text: str, prior_text: str) -> str:
    return (
        "你是买方研究员的财报措辞对比助手。只判断管理层语气是否转弱，不给投资建议。\n"
        "请输出严格 JSON：{\"weakened\": true/false, \"reason\": \"一句原因\", \"evidence\": \"原文中的短语\"}\n"
        f"上期报告期：{prior_period}\n{prior_text}\n\n"
        f"本期报告期：{current_period}\n{current_text}"
    )


def compare_management_tone(
    llm: ChatClient,
    ts_code: str,
    current_period: str,
    prior_period: str,
    current_text: str,
    prior_text: str,
) -> Finding | None:
    prompt = _build_prompt(current_period, prior_period, current_text, prior_text)
    content = llm.chat([ChatMessage(role="user", content=prompt)], temperature=0.0)
    if content is None:
        return None
    try:
        result = ToneComparisonResult.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValidationError):
        return None
    if not result.weakened:
        return None
    return Finding(
        rule_id="management_tone_weakened",
        severity=Severity.YELLOW,
        title="管理层展望语气退坡",
        detail=f"管理层措辞较上期转弱：{result.reason}",
        evidence=[
            Evidence(source="pdf.management_discussion", field="current_text", period=current_period, value=result.evidence),
            Evidence(source="pdf.management_discussion", field="prior_text", period=prior_period, value=prior_text[:120]),
        ],
        score=25.0,
    )
