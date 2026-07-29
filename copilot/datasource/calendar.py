from pydantic import BaseModel
import pandas as pd


class DisclosureEvent(BaseModel):
    ts_code: str
    ann_date: str
    period: str


def _clean_date(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(value)


def normalize_disclosure_events(frame: pd.DataFrame, coverage_pool: set[str]) -> list[DisclosureEvent]:
    events: list[DisclosureEvent] = []
    for _, row in frame.iterrows():
        ts_code = str(row["ts_code"])
        if ts_code not in coverage_pool:
            continue
        ann_date = _clean_date(row.get("ann_date")) or _clean_date(row.get("pre_date"))
        period = _clean_date(row.get("end_date"))
        if ann_date is None or period is None:
            continue
        events.append(DisclosureEvent(ts_code=ts_code, ann_date=ann_date, period=period))
    return events


class TushareDisclosureCalendarClient:
    def __init__(self, pro_api):
        self.pro_api = pro_api

    def fetch_events(self, date: str, coverage_pool: set[str]) -> list[DisclosureEvent]:
        frame = self.pro_api.disclosure_date(ann_date=date)
        if frame is None:
            frame = pd.DataFrame()
        return normalize_disclosure_events(frame, coverage_pool)
