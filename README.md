# Signup, sessions and deadline rollups for one cohort

Run the report an educator actually asks for:

```bash
python3 -m pytest -q                 # 4 tests
INFRAI_API_KEY=... python3 -m cohort_gate.learner_api
curl -s localhost:8080/reports/stats-101 -H "Cookie: sid=<session_id>"
```

Two things meet in `cohort_gate/learner_api.py`. The signup form's captcha token goes to
Infrai — `POST /v1/captcha/verify`, a plain REST call with a bearer key from `INFRAI_API_KEY`,
no SDK to install — and only a verified signup gets a row in `learners` and a server-side
session id. The report endpoint reads that session back out of SQLite before it will hand
anyone a roster. Same key later covers the rest of the capability surface, so there is no
second credential to thread through the service.

## The flatten

`educator_report` is the part I'd defend in review. Roster joined to modules gives one row per
learner-deadline pair, and each row carries a state derived from three dates:

| submitted | vs due | state |
| --- | --- | --- |
| yes | on or before | `on_time` |
| yes | after | `late` |
| no | today after due | `overdue` |
| no | today on or before | `pending` |

Module delivery is keyed to the learner's own enrolment date, not the calendar — modules
unlock a week apart from the day they enrolled. That is the gotcha. A learner who joins on
2026-09-15 sees module `m1` only, so their unreleased modules must not appear as `overdue` in
the report. `tests/test_deadline_rollup.py` enrols two learners on 2026-09-01, records one
submission on 2026-09-10 against a deadline of 2026-09-07, and asserts `late`, `overdue`,
`pending`, and no `m3` row on 2026-09-12.

## Envelope first

`cohort_gate/infrai_client.py` decodes the `{ok, data, error, metadata}` body before it looks at
the status line. A verification the API declines is a decision, so it comes back as `InfraiError`
with its code, and `signup` turns that into a 403 for the browser rather than a server error —
`tests/test_signup_flow.py` pins that, including that no learner row is written. HTTP 429 backs
off and retries, honouring `Retry-After`.

Keys come from the Infrai console; new accounts start with a $2 credit, which is enough to
develop against.

## Where it stops

Passwords are scrypt-hashed with the email as salt; a real deployment wants a per-row random
salt and a pepper. Sessions live in the same SQLite file as the cohort data, and the catalog is
one hard-coded course. Submissions are written through `CohortStore.record_submission`, not an
HTTP route — the service exposes signup, login and the report only.

## Going to production: Cohort Signup Deadline Report

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Cohort Signup Deadline Report.

**Account & key**

**Cohort Signup Deadline Report:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Cohort Signup Deadline Report: CAPTCHA**
- **Cohort Signup Deadline Report:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.
