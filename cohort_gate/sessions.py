"""Server-side sessions: the cookie carries an opaque id, the state stays here."""

from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

SESSION_TTL = timedelta(hours=12)


@dataclass(frozen=True)
class Session:
    session_id: str
    email: str
    expires_at: datetime


class SessionStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        connection.execute(
            "CREATE TABLE IF NOT EXISTS sessions ("
            "session_id TEXT PRIMARY KEY, email TEXT NOT NULL, expires_at TEXT NOT NULL)"
        )
        connection.commit()

    def issue(self, email: str, *, now: Optional[datetime] = None) -> Session:
        now = now or datetime.now(timezone.utc)
        session = Session(secrets.token_urlsafe(24), email, now + SESSION_TTL)
        self._connection.execute(
            "INSERT INTO sessions (session_id, email, expires_at) VALUES (?, ?, ?)",
            (session.session_id, session.email, session.expires_at.isoformat()),
        )
        self._connection.commit()
        return session

    def resolve(self, session_id: str, *, now: Optional[datetime] = None) -> Optional[Session]:
        now = now or datetime.now(timezone.utc)
        row = self._connection.execute(
            "SELECT session_id, email, expires_at FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        expires_at = datetime.fromisoformat(row[2])
        if expires_at <= now:
            self.revoke(session_id)
            return None
        return Session(row[0], row[1], expires_at)

    def revoke(self, session_id: str) -> None:
        self._connection.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self._connection.commit()
