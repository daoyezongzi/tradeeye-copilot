import pandas as pd

from copilot.datasource.calendar import DisclosureEvent, normalize_disclosure_events


def test_normalize_disclosure_events_filters_to_coverage_pool():
    frame = pd.DataFrame([
        {"ts_code": "000001.SZ", "ann_date": "20250821", "end_date": "20250630", "pre_date": "20250820"},
        {"ts_code": "600000.SH", "ann_date": "20250821", "end_date": "20250630", "pre_date": "20250820"},
    ])

    events = normalize_disclosure_events(frame, coverage_pool={"000001.SZ"})

    assert events == [DisclosureEvent(ts_code="000001.SZ", ann_date="20250821", period="20250630")]


def test_normalize_disclosure_events_uses_pre_date_when_ann_date_missing():
    frame = pd.DataFrame([
        {"ts_code": "000001.SZ", "ann_date": None, "end_date": "20250630", "pre_date": "20250820"},
    ])

    events = normalize_disclosure_events(frame, coverage_pool={"000001.SZ"})

    assert events[0].ann_date == "20250820"
