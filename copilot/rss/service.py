from typing import Protocol

import httpx
from pydantic import BaseModel, Field

from copilot.rss.announcements import AnnouncementEvent, classify_announcement, parse_rss_entries
from copilot.service.analyzer import CompanyAnalysisResult


class AnalyzerLike(Protocol):
    def analyze_company(self, ts_code: str, period: str) -> CompanyAnalysisResult: ...


class RssPollResult(BaseModel):
    seen_count: int
    matched_count: int
    analyzed_count: int
    pending_count: int
    events: list[AnnouncementEvent]
    ignored_count: int = 0
    errors: list[str] = Field(default_factory=list)


class RssPollService:
    def __init__(
        self,
        feeds: list[str],
        max_entries: int,
        company_to_ts_code: dict[str, str],
        analyzer: AnalyzerLike,
        http_client: httpx.Client | None = None,
    ):
        self.feeds = feeds
        self.max_entries = max_entries
        self.company_to_ts_code = company_to_ts_code
        self.analyzer = analyzer
        self.http_client = http_client or httpx.Client(timeout=10)
        self._seen_keys: set[tuple[str, str, str]] = set()

    def poll(self) -> RssPollResult:
        seen_count = 0
        ignored_count = 0
        errors: list[str] = []
        matched: list[AnnouncementEvent] = []
        for feed in self.feeds:
            try:
                response = self.http_client.get(feed)
                response.raise_for_status()
                entries = parse_rss_entries(response.text, self.max_entries)
            except Exception as exc:
                errors.append(f"{feed}: {exc}")
                continue
            seen_count += len(entries)
            for title, link in entries:
                event = classify_announcement(title, link, self.company_to_ts_code)
                if event is None:
                    ignored_count += 1
                    continue
                key = (event.ts_code, event.period, event.link)
                if key in self._seen_keys:
                    continue
                event.status = "MATCHED"
                self._seen_keys.add(key)
                matched.append(event)
        return RssPollResult(
            seen_count=seen_count,
            matched_count=len(matched),
            analyzed_count=sum(1 for event in matched if event.status == "ANALYZED"),
            pending_count=sum(1 for event in matched if event.status == "DATA_PENDING"),
            events=matched,
            ignored_count=ignored_count,
            errors=errors,
        )
