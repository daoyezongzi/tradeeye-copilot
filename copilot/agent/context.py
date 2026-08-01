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
