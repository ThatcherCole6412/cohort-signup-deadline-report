from __future__ import annotations

import sqlite3
from datetime import date

from cohort_gate import learner_api
from cohort_gate.infrai_client import InfraiError
from cohort_gate.learner_api import LearnerService

BODY = {
    "email": "Ada@example.edu",
    "password": "correct horse",
    "captcha_token": "tok_from_widget",
    "ip": "203.0.113.7",
    "course_id": "stats-101",
}


def service(monkeypatch, verify):
    monkeypatch.setattr(learner_api, "verify_captcha", verify)
    return LearnerService(sqlite3.connect(":memory:"))


def test_signup_issues_a_session_and_login_reuses_the_credentials(monkeypatch):
    api = service(monkeypatch, lambda token, ip, **kw: {"score": 0.9, "success": True})

    status, payload = api.signup(dict(BODY), date(2026, 9, 1))
    assert status == 201
    assert api.sessions.resolve(payload["session_id"]).email == "ada@example.edu"

    status, login = api.login({"email": "ada@example.edu", "password": "correct horse"})
    assert status == 200 and login["session_id"] != payload["session_id"]

    status, report = api.report("stats-101", login["session_id"], date(2026, 9, 8))
    assert status == 200 and report["rows"][0]["module_id"] == "m1"


def test_rejected_captcha_stays_a_client_error(monkeypatch):
    def reject(token, ip, **kw):
        raise InfraiError("CAPTCHA_SCORE_TOO_LOW", "score below threshold", 422)

    api = service(monkeypatch, reject)
    status, payload = api.signup(dict(BODY), date(2026, 9, 1))
    assert status == 403 and payload["code"] == "CAPTCHA_SCORE_TOO_LOW"
    assert api.cohort.find("ada@example.edu") is None
