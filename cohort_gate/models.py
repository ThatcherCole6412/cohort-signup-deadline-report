"""Typed request models for the two endpoints this service exposes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional


class InvalidRequest(ValueError):
    """The request body did not match the model."""


def _require_str(body: Dict[str, Any], field: str) -> str:
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        raise InvalidRequest(f"{field} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class SignupRequest:
    email: str
    password: str
    captcha_token: str
    widget_record_id: str
    ip: str
    course_id: str

    @staticmethod
    def parse(body: Dict[str, Any]) -> "SignupRequest":
        email = _require_str(body, "email")
        if "@" not in email:
            raise InvalidRequest("email must contain @")
        return SignupRequest(
            email=email.lower(),
            password=_require_str(body, "password"),
            captcha_token=_require_str(body, "captcha_token"),
            widget_record_id=(
                _require_str(body, "widget_record_id")
                if body.get("widget_record_id") is not None
                else _require_str(body, "captcha_token")
            ),
            ip=_require_str(body, "ip"),
            course_id=_require_str(body, "course_id"),
        )


@dataclass(frozen=True)
class LoginRequest:
    email: str
    password: str

    @staticmethod
    def parse(body: Dict[str, Any]) -> "LoginRequest":
        return LoginRequest(
            email=_require_str(body, "email").lower(),
            password=_require_str(body, "password"),
        )


@dataclass(frozen=True)
class Module:
    module_id: str
    title: str
    due_on: date


@dataclass(frozen=True)
class Course:
    course_id: str
    title: str
    modules: List[Module]


@dataclass(frozen=True)
class Learner:
    email: str
    password_hash: str
    course_id: str
    enrolled_on: date


@dataclass(frozen=True)
class DeadlineRow:
    """One row of the educator report: a learner against one module deadline."""

    email: str
    module_id: str
    due_on: date
    submitted_on: Optional[date]
    state: str
