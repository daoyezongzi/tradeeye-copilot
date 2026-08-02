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
