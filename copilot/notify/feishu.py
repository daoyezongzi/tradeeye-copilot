import httpx

from copilot.models import Severity
from copilot.report.builder import DailySummary
from copilot.service.disclosure_scan import CompanyAnalysisStatus, DisclosureScanResult


def render_daily_summary_text(summary: DailySummary) -> str:
    lines = [
        f"{summary.date} 财报研判 · 覆盖池 {summary.coverage_count} 只",
        f"今日披露 {summary.disclosed_count} 家 | 需优先关注 {summary.red_count} | 留意 {summary.yellow_count} | 未见异常 {summary.ok_count}",
    ]
    for card in summary.cards[:10]:
        if not card.findings:
            lines.append(f"✅ {card.ts_code} 未见异常")
            continue
        top = card.findings[0]
        prefix = "🔴" if card.max_severity == Severity.RED else "🟡"
        lines.append(f"{prefix} {card.ts_code} {top.title}：{top.detail}")
    return "\n".join(lines)


def _display_name(ts_code: str, company_names: dict[str, str]) -> str:
    name = company_names.get(ts_code)
    return f"{ts_code} {name}" if name else ts_code


def _abnormal_cards(summary: DailySummary, severity: Severity) -> list:
    return [card for card in summary.cards if card.max_severity == severity and card.findings]


def _card_line(card, company_names: dict[str, str], prefix: str) -> str:
    top = card.findings[0]
    return f"{prefix} {_display_name(card.ts_code, company_names)}\n- {top.title}：{top.detail}"


def _data_problem_events(scan: DisclosureScanResult):
    problem_statuses = {
        CompanyAnalysisStatus.DATA_NOT_READY,
        CompanyAnalysisStatus.DATA_INCOMPLETE,
        CompanyAnalysisStatus.ERROR,
    }
    return [event for event in scan.events if event.status in problem_statuses]


def render_formal_disclosure_text(summary: DailySummary, scan: DisclosureScanResult, company_names: dict[str, str] | None = None) -> str:
    names = company_names or {}
    red_cards = _abnormal_cards(summary, Severity.RED)
    yellow_cards = _abnormal_cards(summary, Severity.YELLOW)
    data_problems = _data_problem_events(scan)
    lines = [
        f"{summary.date} 财报披露研判 · 覆盖池 {summary.coverage_count} 家",
        "",
        f"今日披露：{summary.disclosed_count} 家",
        f"🔴 红色异常：{len(red_cards)} 家",
        f"🟡 黄色异常：{len(yellow_cards)} 家",
        f"⚪ 未见异常：{summary.ok_count} 家",
        f"⚠️ 数据问题：{len(data_problems)} 家",
    ]
    lines.extend(["", f"【红色异常 · {len(red_cards)}/{len(red_cards)}】"])
    lines.extend([_card_line(card, names, "🔴") for card in red_cards] or ["无"])
    lines.extend(["", f"【黄色异常 · {len(yellow_cards)}/{len(yellow_cards)}】"])
    lines.extend([_card_line(card, names, "🟡") for card in yellow_cards] or ["无"])
    lines.extend(["", f"【数据问题 · {len(data_problems)}】"])
    if data_problems:
        lines.extend(
            f"⚠️ {_display_name(event.ts_code, names)} {event.status.value}：{event.message}"
            for event in data_problems
        )
    else:
        lines.append("无")
    lines.extend(["", "【未见异常】", f"未见异常：{summary.ok_count} 家，不逐条展开。"])
    return "\n".join(lines)


def split_feishu_text(text: str, max_chars: int = 3500) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[list[str]] = [[]]
    current_len = 0
    for line in text.splitlines():
        line_len = len(line) + 1
        if chunks[-1] and current_len + line_len > max_chars - 12:
            chunks.append([])
            current_len = 0
        chunks[-1].append(line)
        current_len += line_len
    total = len(chunks)
    return [f"[{index}/{total}]\n" + "\n".join(lines) for index, lines in enumerate(chunks, start=1)]


class FeishuNotifier:
    def __init__(self, webhook_url: str, http_client: httpx.Client | None = None):
        self.webhook_url = webhook_url
        self.http_client = http_client or httpx.Client(timeout=10)

    def send_text(self, text: str) -> bool:
        payload = {"msg_type": "text", "content": {"text": text}}
        try:
            response = self.http_client.post(self.webhook_url, json=payload)
            response.raise_for_status()
        except httpx.HTTPError:
            return False
        data = response.json()
        return data.get("StatusCode", data.get("code", 0)) == 0

    def send_text_parts(self, parts: list[str]) -> bool:
        return all(self.send_text(part) for part in parts)
