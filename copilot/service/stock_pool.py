from pathlib import Path
import sqlite3

from pydantic import BaseModel


class StockPoolItem(BaseModel):
    ts_code: str
    name: str | None = None
    industry: str | None = None


class SQLiteStockPoolStore:
    def __init__(
        self,
        path: str | Path,
        initial_codes: list[str] | None = None,
        initial_names: dict[str, str] | None = None,
        initial_industries: dict[str, str] | None = None,
    ):
        self.path = Path(path)
        self.initial_codes = initial_codes or []
        self.initial_names = initial_names or {}
        self.initial_industries = initial_industries or {}

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_pool (
                    ts_code TEXT PRIMARY KEY,
                    name TEXT,
                    industry TEXT,
                    sort_order INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_pool_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            initialized = conn.execute(
                "SELECT value FROM stock_pool_meta WHERE key = 'initialized'"
            ).fetchone()
            if initialized is None:
                count = conn.execute("SELECT COUNT(*) AS count FROM stock_pool").fetchone()["count"]
                if count == 0:
                    conn.executemany(
                        "INSERT INTO stock_pool (ts_code, name, industry, sort_order) VALUES (?, ?, ?, ?)",
                        [
                            (
                                ts_code,
                                self.initial_names.get(ts_code),
                                self.initial_industries.get(ts_code),
                                index,
                            )
                            for index, ts_code in enumerate(self.initial_codes)
                        ],
                    )
                conn.execute(
                    "INSERT INTO stock_pool_meta (key, value) VALUES ('initialized', '1')"
                )

    def list_items(self) -> list[StockPoolItem]:
        self.init_schema()
        with self._connect() as conn:
            rows = conn.execute("SELECT ts_code, name, industry FROM stock_pool ORDER BY sort_order, ts_code").fetchall()
        return [StockPoolItem(ts_code=row["ts_code"], name=row["name"], industry=row["industry"]) for row in rows]

    def upsert_item(self, ts_code: str, name: str | None = None, industry: str | None = None) -> StockPoolItem:
        self.init_schema()
        code = ts_code.strip().upper()
        with self._connect() as conn:
            row = conn.execute("SELECT sort_order FROM stock_pool WHERE ts_code = ?", (code,)).fetchone()
            if row is None:
                next_order = conn.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM stock_pool").fetchone()["next_order"]
                conn.execute(
                    "INSERT INTO stock_pool (ts_code, name, industry, sort_order) VALUES (?, ?, ?, ?)",
                    (code, name or None, industry or None, next_order),
                )
            else:
                conn.execute(
                    "UPDATE stock_pool SET name = ?, industry = ? WHERE ts_code = ?",
                    (name or None, industry or None, code),
                )
        return StockPoolItem(ts_code=code, name=name or None, industry=industry or None)

    def remove_item(self, ts_code: str) -> bool:
        self.init_schema()
        code = ts_code.strip().upper()
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM stock_pool WHERE ts_code = ?", (code,))
        return cursor.rowcount > 0

    def coverage_pool(self) -> list[str]:
        return [item.ts_code for item in self.list_items()]

    def company_names(self) -> dict[str, str]:
        return {item.ts_code: item.name for item in self.list_items() if item.name}

    def company_industries(self) -> dict[str, str]:
        return {item.ts_code: item.industry for item in self.list_items() if item.industry}
