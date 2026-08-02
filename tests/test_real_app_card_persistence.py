from copilot.api.real_app import RealReportService
from copilot.api.real_app import RealReportService
from copilot.context import Context
from copilot.report.builder import build_company_card
from copilot.service.report_cache import ReportCache
from copilot.store.sqlite import SQLiteStore


def test_sqlite_store_round_trips_company_card(make_snapshot, tmp_path):
    store = SQLiteStore(tmp_path / "app.sqlite")
    store.init_schema()
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])

    store.upsert_company_card(card)

    assert store.get_company_card("000001.SZ", "20250630") == card


def test_real_report_service_loads_card_from_store_after_cache_miss(make_snapshot, tmp_path):
    store = SQLiteStore(tmp_path / "app.sqlite")
    store.init_schema()
    card = build_company_card(Context(ts_code="000001.SZ", current=make_snapshot()), [])
    store.upsert_company_card(card)

    service = RealReportService.__new__(RealReportService)
    service.store = store
    service.cache = ReportCache()

    loaded = service.get_company_card("000001.SZ", "20250630")

    assert loaded == card
    assert service.cache.get_company("000001.SZ", "20250630") == card
