from pathlib import Path
import sqlite3
from time import time

from pydantic import BaseModel


class NotifyLogEvent(BaseModel):
    id: int | None = None
    channel: str
    dedupe_key: str
    sent: bool
    reason: str
    created_at: float


class NotifyLogStore:
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
                CREATE TABLE IF NOT EXISTS notify_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL,
                    sent INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notify_logs_key ON notify_logs(channel, dedupe_key, sent)")

    def already_sent(self, channel: str, dedupe_key: str) -> bool:
        self.init_schema()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM notify_logs WHERE channel = ? AND dedupe_key = ? AND sent = 1 LIMIT 1",
                (channel, dedupe_key),
            ).fetchone()
        return row is not None

    def record_attempt(self, channel: str, dedupe_key: str, sent: bool, reason: str) -> NotifyLogEvent:
        self.init_schema()
        created_at = time()
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO notify_logs (channel, dedupe_key, sent, reason, created_at) VALUES (?, ?, ?, ?, ?)",
                (channel, dedupe_key, 1 if sent else 0, reason, created_at),
            )
            event_id = cursor.lastrowid
        return NotifyLogEvent(id=event_id, channel=channel, dedupe_key=dedupe_key, sent=sent, reason=reason, created_at=created_at)

    def list_recent(self, limit: int = 20) -> list[NotifyLogEvent]:
        self.init_schema()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM notify_logs ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)).fetchall()
        return [
            NotifyLogEvent(
                id=row["id"],
                channel=row["channel"],
                dedupe_key=row["dedupe_key"],
                sent=bool(row["sent"]),
                reason=row["reason"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
