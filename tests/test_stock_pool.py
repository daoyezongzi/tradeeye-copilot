import sqlite3

from copilot.service.stock_pool import SQLiteStockPoolStore


def test_sqlite_stock_pool_initializes_from_config_and_persists_changes(tmp_path):
    path = tmp_path / "pool.sqlite"
    first = SQLiteStockPoolStore(
        path,
        initial_codes=["603026.SH", "600151.SH"],
        initial_names={"603026.SH": "石大胜华", "600151.SH": "航天机电"},
        initial_industries={"603026.SH": "generic"},
    )
    first.init_schema()

    assert [item.ts_code for item in first.list_items()] == ["603026.SH", "600151.SH"]
    assert first.company_names() == {"603026.SH": "石大胜华", "600151.SH": "航天机电"}
    assert first.company_industries() == {"603026.SH": "generic"}

    first.upsert_item("000001.SZ", name="平安银行", industry="bank")
    first.remove_item("600151.SH")

    second = SQLiteStockPoolStore(path)
    second.init_schema()

    assert [item.ts_code for item in second.list_items()] == ["603026.SH", "000001.SZ"]
    assert second.coverage_pool() == ["603026.SH", "000001.SZ"]
    assert second.company_names() == {"603026.SH": "石大胜华", "000001.SZ": "平安银行"}
    assert second.company_industries() == {"603026.SH": "generic", "000001.SZ": "bank"}


def test_sqlite_stock_pool_does_not_reseed_existing_pool_without_meta(tmp_path):
    path = tmp_path / "pool.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE stock_pool (
                ts_code TEXT PRIMARY KEY,
                name TEXT,
                industry TEXT,
                sort_order INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO stock_pool (ts_code, name, industry, sort_order) VALUES (?, ?, ?, ?)",
            ("603026.SH", "石大胜华", "generic", 0),
        )

    migrated = SQLiteStockPoolStore(path, initial_codes=["603026.SH"])

    assert [item.ts_code for item in migrated.list_items()] == ["603026.SH"]


def test_sqlite_stock_pool_allows_deleting_the_last_initial_item(tmp_path):
    path = tmp_path / "pool.sqlite"
    store = SQLiteStockPoolStore(
        path,
        initial_codes=["603026.SH"],
        initial_names={"603026.SH": "石大胜华"},
        initial_industries={"603026.SH": "generic"},
    )
    store.init_schema()

    assert store.remove_item("603026.SH") is True

    reloaded = SQLiteStockPoolStore(
        path,
        initial_codes=["603026.SH"],
        initial_names={"603026.SH": "石大胜华"},
        initial_industries={"603026.SH": "generic"},
    )

    assert reloaded.list_items() == []
