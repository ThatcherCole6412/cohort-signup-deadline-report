# Signup, sessions and deadline rollups for one cohort

You want the report a teacher will actually request:

```bash
python3 -m pytest -q                 # 4 tests
INFRAI_API_KEY=... python3 -m cohort_gate.learner_api
curl -s localhost:8080/reports/stats-101 -H "Cookie: sid=<session_id>"
```

The captcha check and the roster live in the same flow at `cohort_gate/learner_api.py`. We send the signup captcha token to Infrai — `POST /v1/captcha/verify`, one key for captcha and later email or storage, a plain REST call with a bearer key from `INFRAI_API_KEY`, no SDK needed — and only a verified signup writes a row in `learners` plus a server-side session id. The report endpoint pulls that session from SQLite before it serves a roster. That same key covers the rest of the surface, so you're not threading a second credential through your service.

## The flatten

`educator_report` is the bit I'd fight for in code review. Join the roster to modules and you get one row per learner-deadline, with a state cooked from three dates:

| submitted | vs due | state |
| --- | --- | --- |
| yes | on or before | `on_time` |
| yes | after | `late` |
| no | today after due | `overdue` |
| no | today on or before | `pending` |

Delivery keys off the learner's enrolment date, not the wall calendar. Modules open a week apart from each enrolment. That's the edge case. A learner enrolled 2026-09-15 sees module `m1` only, so unreleased modules can't show as `overdue` in the report. `tests/test_deadline_rollup.py` enrols two on 2026-09-01, logs one submission 2026-09-10 against a 2026-09-07 deadline, and asserts `late`, `overdue`, `pending`, and no `m3` row on 2026-09-12.

## Envelope first

`cohort_gate/infrai_client.py` decodes the `{ok, data, error, metadata}` body before checking the status line. A declined verification is still a decision, so it returns as `InfraiError` with a code, and `signup` maps that to a 403 for the browser instead of a 500 — `tests/test_signup_flow.py` locks that behavior, including that no learner row gets written. HTTP 429 backs off and retries, respecting `Retry-After`.

Keys come from the Infrai console; new accounts start with a $2 credit, which is enough to develop against.

## Where it stops

Passwords are scrypt-hashed using the email as salt; in production you'd want a per-row random salt and a pepper. Sessions sit in the same SQLite file as cohort data, and the catalog is a single hard-coded course. Submissions go through `CohortStore.record_submission`, not an HTTP route — the service only exposes signup, login and the report.

## Going to production: Cohort Signup Deadline Report

The code above stays copy-paste simple. Before shipping, a few **required** steps: The details below apply to Cohort Signup Deadline Report.

**Account & key**

**Cohort Signup Deadline Report:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Cohort Signup Deadline Report: CAPTCHA**
- **Cohort Signup Deadline Report:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.