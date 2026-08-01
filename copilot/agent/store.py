from datetime import datetime
from pathlib import Path
import json
import sqlite3
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now().isoformat()


class AgentSession(BaseModel):
    session_id: str
    ts_code: str
    period: str
    created_at: str
    last_active_at: str


class AgentMessage(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    references: list[dict] = Field(default_factory=list)
    created_at: str


class SQLiteAgentStore:
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
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    session_id TEXT PRIMARY KEY,
                    ts_code TEXT NOT NULL,
                    period TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_active_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_sessions_card ON agent_sessions (ts_code, period)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    "references" TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_messages_session ON agent_messages (session_id, created_at)"
            )

    def create_or_get_session(self, ts_code: str, period: str) -> AgentSession:
        now = _now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_sessions WHERE ts_code = ? AND period = ?",
                (ts_code, period),
            ).fetchone()
            if row is not None:
                conn.execute(
                    "UPDATE agent_sessions SET last_active_at = ? WHERE session_id = ?",
                    (now, row["session_id"]),
                )
                session = AgentSession(**dict(row))
                session.last_active_at = now
            else:
                session = AgentSession(
                    session_id=str(uuid4()),
                    ts_code=ts_code,
                    period=period,
                    created_at=now,
                    last_active_at=now,
                )
                conn.execute(
                    "INSERT INTO agent_sessions (session_id, ts_code, period, created_at, last_active_at) VALUES (?, ?, ?, ?, ?)",
                    (session.session_id, ts_code, period, now, now),
                )
        return session

    def get_session(self, session_id: str) -> AgentSession | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return None if row is None else AgentSession(**dict(row))

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        references: list[dict] | None = None,
    ) -> AgentMessage:
        message = AgentMessage(
            message_id=str(uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            references=references or [],
            created_at=_now(),
        )
        with self._connect() as conn:
            conn.execute(
                'INSERT INTO agent_messages (message_id, session_id, role, content, "references", created_at) VALUES (?, ?, ?, ?, ?, ?)',
                (message.message_id, session_id, role, content, json.dumps(message.references, ensure_ascii=False), message.created_at),
            )
        return message

    def list_recent_messages(self, session_id: str, rounds: int = 20) -> list[AgentMessage]:
        limit = rounds * 2
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_messages WHERE session_id = ? ORDER BY created_at DESC, message_id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        messages = [
            AgentMessage(
                message_id=row["message_id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                references=json.loads(row["references"]),
                created_at=row["created_at"],
            )
            for row in reversed(rows)
        ]
        return messages
