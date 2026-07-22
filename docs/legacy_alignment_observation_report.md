# Legacy Alignment Observation Report

## Report Status

- Task: `9C.5O`
- Baseline: `388666a192df9d33044541aaca4ddf42e6aa7bd2`
- Report generated: `2026-07-22`
- Target environment: `PENDING_ASSIGNMENT`
- Target database: `PENDING_ASSIGNMENT`
- Observation start: `PENDING_TARGET_DEPLOYMENT`
- Observation end: `PENDING_14_DAY_WINDOW`
- Actual target-environment active days: `0`
- External consumer status: `UNKNOWN_EXTERNAL_LEGACY_CONSUMER`
- Activation record: `docs/legacy_alignment_observation_window.md`

```text
OBSERVATION_WINDOW_PENDING
OBSERVATION_WINDOW_PENDING_DEPLOYMENT
LEGACY_ALIGNMENT_DEPRECATION_OBSERVATION_INCOMPLETE
LEGACY_ALIGNMENT_410_NOT_AUTHORIZED
```

The required continuous 14-day window with at least five actual operating
days cannot be completed in a single repository task. No gateway, access-log,
or target-environment telemetry was available at this baseline, so this report
does not infer zero external traffic from repository scans or local E2E runs.

## Observation Window

The window starts only after all target pilot environments deploy the
observation telemetry and name an observation owner and rollback owner. It
must run for at least 14 continuous 24-hour periods and cover at least five
actual operating days. Any unexplained Legacy POST or new creation signal
restarts the zero-creation interval after the caller is classified.

| Field | Current value | Exit requirement |
|---|---|---|
| Start time | pending | retained UTC deployment timestamp |
| End time | pending | at least 14 days after start |
| Environment | pending | every target pilot environment |
| Database | pending | every authoritative target database |
| Worker state | local rehearsal only | target process inventory and state |
| Legacy POST metrics | unavailable | attributed request series |
| Legacy GET metrics | unavailable | retained read-usage decision |
| External signal | unavailable | gateway/access-log evidence plus owner review |

## Traffic Telemetry

`LEGACY_ALIGNMENT_OBSERVATION_ENABLED=true` emits payload-free structured
events for:

- `POST /api/alignment/run`;
- `GET /api/alignment/runs` and run detail;
- `GET /api/admin/alignment-runs`;
- `POST /api/documents/upload?sync=true`;
- internal `AlignmentRun` and `alignment_run` job creation signals.

Events retain timestamp, route template, method, status, safe result, caller ID
and role, sync/async mode, and creation counts. They do not retain request
bodies, terms, prompts, outputs, credentials, authorization headers, cookies,
or raw exceptions. Logs are summarized without database writes:

```bash
python scripts/legacy_alignment_observation_report.py \
  --log /path/to/application.jsonl \
  --environment TARGET_ENVIRONMENT \
  --database TARGET_DATABASE_LABEL \
  --window-start START_UTC \
  --window-end END_UTC \
  --active-days N \
  --external-consumer-status UNKNOWN_EXTERNAL_LEGACY_CONSUMER \
  --json-output /path/to/legacy-observation-report.json
```

The report remains `OBSERVATION_WINDOW_PENDING` unless the duration, active
days, zero-creation, and external-consumer evidence gates all pass. Queue,
worker shutdown, rollback, and Formal regression evidence remain separate
retirement gates.

## Current Metrics

| Signal | Target-environment result | Repository/local evidence |
|---|---|---|
| Legacy POST requests | unknown | Formal frontend E2E reports `legacy_alignment_requests=0` |
| Legacy GET history | unknown | production frontend still actively loads `GET /api/alignment/runs` |
| Legacy creation | unknown | Freeze rehearsal blocked one POST with zero run/job creation |
| Internal creation | unknown | telemetry now covers helper and job-factory signals |
| External consumer | unknown | no gateway/access-log source is connected |

Local and test evidence is not counted as an observation day.

## Controlled Freeze Evidence

Command:

```bash
python scripts/run_legacy_alignment_shutdown_rehearsal.py \
  --json-output /private/tmp/lexibridge-9c5o-controlled-freeze.json
```

Result on `2026-07-22`: `PASS` in isolated temporary SQLite.

| Phase | Queued | Running | Retrying | Failed | Result |
|---|---:|---:|---:|---:|---|
| Freeze snapshot | 1 | 1 | 0 | 0 | new HTTP/internal creation blocked |
| Drained snapshot | 0 | 0 | 0 | 1 | queued work completed; stale work safely failed |
| Disabled | 0 | 0 | 0 | 1 | Legacy claim paused |
| Rollback to Active | not a drain metric | not a drain metric | not a drain metric | not a drain metric | Legacy POST restored with HTTP 200 |

This is a non-production rehearsal. Target database counts and process-manager
shutdown remain pending.

## Formal-Only Runtime Evidence

The Formal API and recovery E2E were run with:

```text
LEGACY_ALIGNMENT_RUNTIME_STATE=disabled
LEGACY_ALIGNMENT_ROUTE_ADMISSION_ENABLED=false
```

The normal HTTP worker flow, polling, pagination, permissions, idempotency,
retryable requeue, claim-crash stale reclaim, partial resume, terminal recovery,
and retry exhaustion all passed with zero external dependency requests. The
frozen contracts remained:

- workflow version: `formal-document-alignment-v1`;
- job type: `formal_document_alignment_workflow_v1`;
- idempotency scope: requested by, source UID, workflow version, and key.

```text
FORMAL_ONLY_RUNTIME_CONFIRMED
```

## Remaining Evidence

Before this report can be completed:

1. deploy telemetry in every target pilot environment;
2. name observation and rollback owners;
3. retain 14 continuous days and five actual operating days;
4. attribute every Legacy POST and internal creation signal;
5. capture authoritative queue snapshots before, during, and after drain;
6. rehearse Legacy worker shutdown against the actual process manager;
7. retain zero active Legacy counts for the approved hold period;
8. publish the dated migration notice;
9. keep Formal and readiness gates green throughout the window.

## Local Verification

The following repository-local Gates passed on `2026-07-22`. They verify the
implementation and rehearsal, but do not advance the target observation-day
counts.

| Gate | Result | Artifact or detail |
|---|---|---|
| Targeted observation/freeze/Formal tests | PASS | 43 tests |
| Full pytest | PASS | 1110 tests, 6 existing deprecation warnings |
| Release safety | PASS | no release safety finding |
| Developer check | PASS | tests, migration, and backend smoke |
| Controlled Freeze/drain/rollback | PASS | `/private/tmp/lexibridge-9c5o-controlled-freeze.json` |
| Formal frontend with Legacy Disabled | PASS | `/private/tmp/lexibridge-9c5o-formal-frontend.json`; three Formal POSTs, zero Legacy POSTs |
| Teacher browser E2E | PASS | `/private/tmp/lexibridge-9c5o-teacher.json` |
| Full browser E2E | PASS | `/private/tmp/lexibridge-9c5o-full.json` |
| Browser console/page errors | PASS | zero unexpected errors |
| External provider requests | PASS | zero actual requests |
| Pilot readiness | `READY_WITH_CONDITIONS` | `/private/tmp/lexibridge-9c5o-readiness.json` |
