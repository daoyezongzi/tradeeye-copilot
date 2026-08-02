from pathlib import Path
import sqlite3

from copilot.models import Finding, PeriodSnapshot
from copilot.report.builder import CompanyCard


class SQLiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS financial_snapshots (
                    ts_code TEXT NOT NULL,
                    period TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (ts_code, period)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS findings (
                    ts_code TEXT NOT NULL,
                    period TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    score REAL NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (ts_code, period, rule_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS company_cards (
                    ts_code TEXT NOT NULL,
                    period TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (ts_code, period)
                )
                """
            )

    def upsert_company_card(self, card: CompanyCard) -> None:
        payload = card.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO company_cards (ts_code, period, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(ts_code, period) DO UPDATE SET payload = excluded.payload
                """,
                (card.ts_code, card.period, payload),
            )

    def get_company_card(self, ts_code: str, period: str) -> CompanyCard | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM company_cards WHERE ts_code = ? AND period = ?",
                (ts_code, period),
            ).fetchone()
        if row is None:
            return None
        return CompanyCard.model_validate_json(row["payload"])

    def upsert_snapshot(self, snapshot: PeriodSnapshot) -> None:
        payload = snapshot.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO financial_snapshots (ts_code, period, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(ts_code, period) DO UPDATE SET payload = excluded.payload
                """,
                (snapshot.ts_code, snapshot.period, payload),
            )

    def get_snapshot(self, ts_code: str, period: str) -> PeriodSnapshot | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM financial_snapshots WHERE ts_code = ? AND period = ?",
                (ts_code, period),
            ).fetchone()
        if row is None:
            return None
        return PeriodSnapshot.model_validate_json(row["payload"])

    def replace_findings(self, ts_code: str, period: str, findings: list[Finding]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM findings WHERE ts_code = ? AND period = ?", (ts_code, period))
            conn.executemany(
                """
                INSERT INTO findings (ts_code, period, rule_id, severity, score, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        ts_code,
                        period,
                        finding.rule_id,
                        finding.severity.value,
                        finding.score,
                        finding.model_dump_json(),
                    )
                    for finding in findings
                ],
            )

    def list_findings(self, ts_code: str, period: str) -> list[Finding]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload FROM findings
                WHERE ts_code = ? AND period = ?
                ORDER BY score DESC, rule_id ASC
                """,
                (ts_code, period),
            ).fetchall()
        return [Finding.model_validate_json(row["payload"]) for row in rows]
