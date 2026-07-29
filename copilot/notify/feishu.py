import httpx

from copilot.models import Severity
from copilot.report.builder import DailySummary


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
