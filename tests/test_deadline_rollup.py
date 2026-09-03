"""The educator report is the decision worth pinning down."""

from __future__ import annotations

import sqlite3
from datetime import date

from cohort_gate.cohort import CATALOG, CohortStore, educator_report, released_modules
from cohort_gate.models import Learner


def make_store() -> CohortStore:
    return CohortStore(sqlite3.connect(":memory:"))


def test_report_marks_overdue_late_and_pending():
    store = make_store()
    store.enrol(Learner("ada@example.edu", "x", "stats-101", date(2026, 9, 1)))
    store.enrol(Learner("bo@example.edu", "x", "stats-101", date(2026, 9, 1)))
    store.record_submission("ada@example.edu", "m1", date(2026, 9, 10))

    today = date(2026, 9, 12)
    rows = {(r.email, r.module_id): r.state for r in educator_report(store, "stats-101", today)}

    # m1 was due 2026-09-07: ada handed in on the 10th, bo never did.
    assert rows[("ada@example.edu", "m1")] == "late"
    assert rows[("bo@example.edu", "m1")] == "overdue"
    # m2 is due 2026-09-21 and still open.
    assert rows[("ada@example.edu", "m2")] == "pending"
    # m3 unlocks two strides after enrolment (2026-09-15), so it is not on the report yet.
    assert ("ada@example.edu", "m3") not in rows


def test_delivery_follows_enrolment_date_not_calendar():
    course = CATALOG["stats-101"]
    late_joiner = released_modules(course, date(2026, 9, 15), date(2026, 9, 16))
    assert [m.module_id for m in late_joiner] == ["m1"]
