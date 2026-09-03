"""HTTP surface: signup (captcha -> session), login, and the educator report."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional, Tuple

from .cohort import CATALOG, CohortStore, educator_report, hash_password, released_modules
from .infrai_client import InfraiError, verify_captcha
from .models import InvalidRequest, Learner, LoginRequest, SignupRequest
from .sessions import SessionStore

Reply = Tuple[int, Dict[str, Any]]


class LearnerService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.cohort = CohortStore(connection)
        self.sessions = SessionStore(connection)

    def signup(self, body: Dict[str, Any], today: date) -> Reply:
        try:
            request = SignupRequest.parse(body)
        except InvalidRequest as invalid:
            return 400, {"error": str(invalid)}
        if request.course_id not in CATALOG:
            return 404, {"error": "unknown course"}
        if self.cohort.find(request.email) is not None:
            return 409, {"error": "already enrolled"}

        try:
            check = verify_captcha(
                request.captcha_token,
                request.ip,
                widget_record_id=request.widget_record_id,
            )
        except InfraiError as rejected:
            # A rejected human check is the learner's problem, so it stays a 4xx here.
            return 403, {"error": "captcha rejected", "code": rejected.code}

        self.cohort.enrol(
            Learner(
                email=request.email,
                password_hash=hash_password(request.password, request.email),
                course_id=request.course_id,
                enrolled_on=today,
            )
        )
        session = self.sessions.issue(request.email)
        return 201, {
            "session_id": session.session_id,
            "expires_at": session.expires_at.isoformat(),
            "captcha_score": check.get("score"),
            "modules": [m.module_id for m in released_modules(CATALOG[request.course_id], today, today)],
        }

    def login(self, body: Dict[str, Any]) -> Reply:
        try:
            request = LoginRequest.parse(body)
        except InvalidRequest as invalid:
            return 400, {"error": str(invalid)}
        learner = self.cohort.find(request.email)
        if learner is None or learner.password_hash != hash_password(request.password, request.email):
            return 401, {"error": "bad credentials"}
        session = self.sessions.issue(learner.email)
        return 200, {"session_id": session.session_id, "expires_at": session.expires_at.isoformat()}

    def report(self, course_id: str, session_id: Optional[str], today: date) -> Reply:
        if session_id is None or self.sessions.resolve(session_id) is None:
            return 401, {"error": "no active session"}
        if course_id not in CATALOG:
            return 404, {"error": "unknown course"}
        rows = educator_report(self.cohort, course_id, today)
        return 200, {
            "course_id": course_id,
            "rows": [
                {
                    "email": row.email,
                    "module_id": row.module_id,
                    "due_on": row.due_on.isoformat(),
                    "submitted_on": row.submitted_on.isoformat() if row.submitted_on else None,
                    "state": row.state,
                }
                for row in rows
            ],
        }


def build_handler(service: LearnerService):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, reply: Reply) -> None:
            status, payload = reply
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:  # noqa: N802 - http.server naming
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/signup":
                self._send(service.signup(body, date.today()))
            elif self.path == "/login":
                self._send(service.login(body))
            else:
                self._send((404, {"error": "no such route"}))

        def do_GET(self) -> None:  # noqa: N802 - http.server naming
            if self.path.startswith("/reports/"):
                cookie = self.headers.get("Cookie") or ""
                session_id = None
                for part in cookie.split(";"):
                    name, _, value = part.strip().partition("=")
                    if name == "sid":
                        session_id = value
                self._send(service.report(self.path.rsplit("/", 1)[-1], session_id, date.today()))
            else:
                self._send((404, {"error": "no such route"}))

    return Handler


def main() -> None:
    connection = sqlite3.connect("cohort.db", check_same_thread=False)
    server = HTTPServer(("127.0.0.1", 8080), build_handler(LearnerService(connection)))
    print("listening on http://127.0.0.1:8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
