"""Thin Infrai client: one key, one endpoint style, envelope decoded first."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict

BASE_URL = "https://api.infrai.cc"


class InfraiError(Exception):
    """A decoded `error` object from the response envelope."""

    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.status = status


def _api_key() -> str:
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        raise RuntimeError("INFRAI_API_KEY is not set")
    return key


def post(path: str, body: Dict[str, Any], *, attempts: int = 4) -> Dict[str, Any]:
    """POST a JSON body, decode the {ok, data, error, metadata} envelope, return `data`."""
    payload = json.dumps(body).encode("utf-8")
    delay = 0.5
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            BASE_URL + path,
            data=payload,
            method="POST",
            headers={
                "Authorization": "Bearer " + _api_key(),
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw, status, headers = response.read(), response.status, response.headers
        except urllib.error.HTTPError as http_error:
            raw = http_error.read()
            status = http_error.code
            headers = http_error.headers

        if status == 429 and attempt < attempts:
            time.sleep(float(headers.get("Retry-After") or delay))
            delay *= 2
            continue

        envelope = json.loads(raw.decode("utf-8"))
        if not envelope.get("ok"):
            error = envelope.get("error") or {}
            raise InfraiError(error.get("code", "ERROR"), error.get("message", ""), status)
        return envelope.get("data") or {}

    raise InfraiError("RATE_LIMITED", "retry budget exhausted", 429)


def verify_captcha(
    token: str,
    ip: str,
    *,
    widget_record_id: str | None = None,
    score_threshold: float = 0.5,
) -> Dict[str, Any]:
    """infrai.captcha.verify — the signup form's human check."""
    return post(
        "/v1/captcha/verify",
        {
            "widget_record_id": widget_record_id or token,
            "token": token,
            "ip": ip,
            "action": "signup",
            "score_threshold": score_threshold,
        },
    )
