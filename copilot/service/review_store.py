from pathlib import Path
import sqlite3
from time import time

from pydantic import BaseModel


class StoredReviewLabel(BaseModel):
    ts_code: str
    period: str
    rule_id: str
    label: str
    notes: str = ""
    severity: str | None = None
    industry: str | None = None
    reviewer: str | None = None
    updated_at: float


class ReviewLabelStore:
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
                CREATE TABLE IF NOT EXISTS review_labels (
                    ts_code TEXT NOT NULL,
                    period TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    severity TEXT,
                    industry TEXT,
                    reviewer TEXT,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (ts_code, period, rule_id)
                )
                """
            )

    def upsert_label(
        self,
        ts_code: str,
        period: str,
        rule_id: str,
        label: str,
        notes: str = "",
        severity: str | None = None,
        industry: str | None = None,
        reviewer: str | None = None,
    ) -> StoredReviewLabel:
        self.init_schema()
        updated_at = time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO review_labels (ts_code, period, rule_id, label, notes, severity, industry, reviewer, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ts_code, period, rule_id) DO UPDATE SET
                    label = excluded.label,
                    notes = excluded.notes,
                    severity = excluded.severity,
                    industry = excluded.industry,
                    reviewer = excluded.reviewer,
                    updated_at = excluded.updated_at
                """,
                (ts_code, period, rule_id, label, notes, severity, industry, reviewer, updated_at),
            )
        return StoredReviewLabel(
            ts_code=ts_code,
            period=period,
            rule_id=rule_id,
            label=label,
            notes=notes,
            severity=severity,
            industry=industry,
            reviewer=reviewer,
            updated_at=updated_at,
        )

    def list_labels(self, ts_code: str | None = None, period: str | None = None) -> list[StoredReviewLabel]:
        self.init_schema()
        clauses = []
        params = []
        if ts_code is not None:
            clauses.append("ts_code = ?")
            params.append(ts_code)
        if period is not None:
            clauses.append("period = ?")
            params.append(period)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM review_labels{where} ORDER BY updated_at DESC",
                params,
            ).fetchall()
        return [StoredReviewLabel(**dict(row)) for row in rows]

    def delete_label(self, ts_code: str, period: str, rule_id: str) -> bool:
        self.init_schema()
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM review_labels WHERE ts_code = ? AND period = ? AND rule_id = ?",
                (ts_code, period, rule_id),
            )
        return cursor.rowcount > 0
