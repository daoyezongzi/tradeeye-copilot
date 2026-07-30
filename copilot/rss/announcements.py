import re
import xml.etree.ElementTree as ET

from pydantic import BaseModel


class AnnouncementEvent(BaseModel):
    ts_code: str
    title: str
    link: str
    period: str
    status: str = "SEEN"


_EXCLUDE_KEYWORDS = ["摘要", "取消", "更正", "补充", "英文版"]


def parse_rss_entries(xml_text: str, max_entries: int) -> list[tuple[str, str]]:
    root = ET.fromstring(xml_text)
    entries: list[tuple[str, str]] = []
    for item in root.findall(".//item")[:max_entries]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title:
            entries.append((title, link))
    return entries


def _infer_year(title: str) -> str | None:
    match = re.search(r"(20\d{2})年", title)
    return match.group(1) if match else None


def _infer_period(title: str) -> str | None:
    year = _infer_year(title)
    if year is None:
        return None
    if "第一季度报告" in title or "一季报" in title:
        return f"{year}0331"
    if "半年度报告" in title or "半年报" in title:
        return f"{year}0630"
    if "第三季度报告" in title or "三季报" in title:
        return f"{year}0930"
    if "年度报告" in title or "年报" in title:
        return f"{year}1231"
    return None


def classify_announcement(title: str, link: str, company_to_ts_code: dict[str, str]) -> AnnouncementEvent | None:
    if any(keyword in title for keyword in _EXCLUDE_KEYWORDS):
        return None
    period = _infer_period(title)
    if period is None:
        return None
    for company_name, ts_code in company_to_ts_code.items():
        if company_name in title:
            return AnnouncementEvent(ts_code=ts_code, title=title, link=link, period=period)
    return None
