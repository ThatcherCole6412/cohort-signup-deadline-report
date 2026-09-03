"""Course delivery, learner deadlines, and the educator rollup over both."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import date, timedelta
from typing import Dict, List, Optional

from .models import Course, DeadlineRow, Learner, Module

# One seeded course; modules are delivered relative to the learner's enrolment date.
CATALOG: Dict[str, Course] = {
    "stats-101": Course(
        course_id="stats-101",
        title="Applied Statistics 101",
        modules=[
            Module("m1", "Sampling", date(2026, 9, 7)),
            Module("m2", "Regression", date(2026, 9, 21)),
            Module("m3", "Causal inference", date(2026, 10, 5)),
        ],
    )
}

# Modules unlock one week apart from enrolment, capped by the module's own due date.
UNLOCK_STRIDE = timedelta(days=7)


def hash_password(password: str, email: str) -> str:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=email.encode("utf-8"), n=16384, r=8, p=1
    ).hex()


class CohortStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        connection.executescript(
            "CREATE TABLE IF NOT EXISTS learners ("
            " email TEXT PRIMARY KEY, password_hash TEXT NOT NULL,"
            " course_id TEXT NOT NULL, enrolled_on TEXT NOT NULL);"
            "CREATE TABLE IF NOT EXISTS submissions ("
            " email TEXT NOT NULL, module_id TEXT NOT NULL, submitted_on TEXT NOT NULL,"
            " PRIMARY KEY (email, module_id));"
        )
        connection.commit()

    def enrol(self, learner: Learner) -> None:
        self._connection.execute(
            "INSERT INTO learners (email, password_hash, course_id, enrolled_on)"
            " VALUES (?, ?, ?, ?)",
            (learner.email, learner.password_hash, learner.course_id, learner.enrolled_on.isoformat()),
        )
        self._connection.commit()

    def find(self, email: str) -> Optional[Learner]:
        row = self._connection.execute(
            "SELECT email, password_hash, course_id, enrolled_on FROM learners WHERE email = ?",
            (email,),
        ).fetchone()
        if row is None:
            return None
        return Learner(row[0], row[1], row[2], date.fromisoformat(row[3]))

    def record_submission(self, email: str, module_id: str, submitted_on: date) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO submissions (email, module_id, submitted_on) VALUES (?, ?, ?)",
            (email, module_id, submitted_on.isoformat()),
        )
        self._connection.commit()

    def submissions(self, course_id: str) -> Dict[str, Dict[str, date]]:
        rows = self._connection.execute(
            "SELECT s.email, s.module_id, s.submitted_on FROM submissions s"
            " JOIN learners l ON l.email = s.email WHERE l.course_id = ?",
            (course_id,),
        ).fetchall()
        by_learner: Dict[str, Dict[str, date]] = {}
        for email, module_id, submitted_on in rows:
            by_learner.setdefault(email, {})[module_id] = date.fromisoformat(submitted_on)
        return by_learner

    def roster(self, course_id: str) -> List[Learner]:
        rows = self._connection.execute(
            "SELECT email, password_hash, course_id, enrolled_on FROM learners"
            " WHERE course_id = ? ORDER BY email",
            (course_id,),
        ).fetchall()
        return [Learner(r[0], r[1], r[2], date.fromisoformat(r[3])) for r in rows]


def released_modules(course: Course, enrolled_on: date, today: date) -> List[Module]:
    """A module is delivered once its unlock date has passed."""
    return [
        module
        for index, module in enumerate(course.modules)
        if enrolled_on + UNLOCK_STRIDE * index <= today
    ]


def deadline_state(due_on: date, submitted_on: Optional[date], today: date) -> str:
    if submitted_on is not None:
        return "late" if submitted_on > due_on else "on_time"
    if today > due_on:
        return "overdue"
    return "pending"


def educator_report(store: CohortStore, course_id: str, today: date) -> List[DeadlineRow]:
    """Flatten roster x modules into one row per learner-deadline pair."""
    course = CATALOG[course_id]
    submitted = store.submissions(course_id)
    rows: List[DeadlineRow] = []
    for learner in store.roster(course_id):
        for module in released_modules(course, learner.enrolled_on, today):
            submitted_on = submitted.get(learner.email, {}).get(module.module_id)
            rows.append(
                DeadlineRow(
                    email=learner.email,
                    module_id=module.module_id,
                    due_on=module.due_on,
                    submitted_on=submitted_on,
                    state=deadline_state(module.due_on, submitted_on, today),
                )
            )
    return rows
