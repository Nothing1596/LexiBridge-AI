# Legacy Alignment Observation Window

## Activation Status

- Task: `9C.5O.1`
- Baseline: `22f9976dc94ef448682cca5bb54a99bde2dc320e`
- Target environment name: `TARGET_PILOT_ENVIRONMENT_UNASSIGNED`
- Current state: `PREPARED`
- Start date: `PENDING_DEPLOYMENT`
- Target end date: `PENDING_START_DATE_PLUS_14_DAYS`
- Actual target operating days: `0`
- Required target operating days: `5`

```text
OBSERVATION_WINDOW_PENDING_DEPLOYMENT
LIMITED_OBSERVABILITY
OWNER_PENDING
```

No target deployment, authoritative database identity, retained access-log
source, or operational owner is available in the repository. The isolated
environment used by tests and rehearsals is named `pilot-local-rehearsal`, but
it is not a target pilot environment and does not count as Day 1.

## State Machine

```text
PREPARED -> ACTIVE -> COMPLETED -> REVIEWED
```

| State | Entry evidence |
|---|---|
| `PREPARED` | Telemetry, report tooling, Freeze/drain rehearsal, and procedures exist |
| `ACTIVE` | Named environment/database/workers/owners, retained logs, initial queue snapshot, and UTC start timestamp |
| `COMPLETED` | At least 14 continuous calendar days and five actual operating days with all required evidence |
| `REVIEWED` | Owners review traffic, queue, worker, external-consumer, rollback, and Formal evidence |

The current state remains `PREPARED`. Deployment alone does not imply
`ACTIVE`; the activation record must contain all required identities and the
initial evidence bundle. This task does not enter `COMPLETED` or `REVIEWED`.

## Environment Declaration

| Scope | Required value | Current value |
|---|---|---|
| Deployment environment | Stable target name | `TARGET_PILOT_ENVIRONMENT_UNASSIGNED` |
| Database type | SQLite or PostgreSQL as actually deployed | `PENDING_DEPLOYMENT` |
| Database identity | Non-secret stable instance/file identifier | `PENDING_DEPLOYMENT` |
| Initial snapshot time | Retained UTC timestamp | `PENDING_DEPLOYMENT` |
| Formal worker | Process/service identity and mode | `PENDING_DEPLOYMENT` |
| Legacy worker | Process/service identity or confirmed stopped state | `PENDING_DEPLOYMENT` |
| Application log source | Retained stream/path and retention period | `PENDING_DEPLOYMENT` |
| Access/gateway logs | Source and query owner, or explicit unavailable decision | `UNAVAILABLE` |

Do not record database credentials, tokens, filesystem secrets, request
payloads, prompts, outputs, or private evidence in this declaration.

## Ownership

| Role | Responsibility | Current owner |
|---|---|---|
| Observation owner | Daily metrics, caller attribution, evidence retention | `OWNER_PENDING` |
| Rollback owner | Freeze rollback decision and execution | `ROLLBACK_OWNER_PENDING` |
| Support owner | Migration questions and caller communication | `SUPPORT_OWNER_PENDING` |

The window cannot become `ACTIVE` until named owners and contact paths are
recorded in an environment-controlled operational record.

## Duration

The target duration is at least 14 continuous calendar days and at least five
actual operating days. When activation evidence exists:

1. record the UTC start timestamp after telemetry and initial snapshots are
   verified;
2. calculate the provisional end as start plus 14 full days;
3. extend the window until five actual operating days are complete;
4. restart the zero-creation interval after any unexplained Legacy creation;
5. never backdate the start to local tests, deployment preparation, or an
   incomplete logging period.

## Metrics And Sources

| Signal | Required dimensions | Current source | Activation status |
|---|---|---|---|
| Legacy POST | timestamp, caller ID/role, result, status, sync/async, creation counts | payload-free application event `legacy_alignment_request` | code ready; target retention pending |
| Legacy history GET | timestamp, caller ID/role, route, status | payload-free application event `legacy_alignment_request` | code ready; target retention pending |
| AlignmentRun creation | timestamp, caller/source, count | request creation count and internal creation event | code ready; target retention pending |
| Legacy BackgroundJob creation | timestamp, caller/source, count | request creation count and internal creation event | code ready; target retention pending |
| Queue state | queued, running, retrying, failed, oldest active age | `legacy_alignment_runtime.py status` and authoritative database snapshot | manual collection pending |
| Legacy worker | claim, start, completion, retry, failure, worker ID | `BackgroundJobEvent` plus worker process inventory | target correlation pending |
| Formal run count | run count and terminal distribution | Formal WorkflowRun database snapshot | target query pending |
| Formal Legacy POST count | `legacy_alignment_requests` | Formal frontend E2E/network artifact | deployment observation pending |
| External consumer signal | gateway/access logs and client-owner confirmation | none connected | unavailable |

Application logging plus database snapshots provide partial evidence. Without
retained target logs and an external access-log source, the current status is
`LIMITED_OBSERVABILITY`; external consumers must remain unknown.

## Collection Cadence

- continuously retain Legacy HTTP and creation events;
- capture queue and worker snapshots at activation, at least daily, before and
  after Freeze/drain actions, and at window exit;
- record Formal run counts and zero-Legacy-POST evidence each operating day;
- review unattributed callers and failed/retrying jobs daily;
- retain the report artifact generated by
  `scripts/legacy_alignment_observation_report.py` without raw payloads.

## Legacy GET Consumer Decision

Decision: **B - retain as a read-only compatibility surface**.

`frontend/index.html` function `loadAlignmentRuns()` calls
`GET /api/alignment/runs` to populate `state.cache.alignmentRuns` for legacy
history display. The Formal API currently supports start, run detail, and item
pagination, but it does not provide an equivalent history-list contract.

The GET route therefore remains active and unchanged. Its migration requires
a separate Formal history API and frontend cutover task. POST retirement must
not remove the list/detail read contracts or historical `AlignmentRun` data.

## Activation Gate

Change the state to `ACTIVE` only after all items below are recorded:

- target environment and authoritative database identity;
- Formal and Legacy worker process inventory;
- observation, rollback, and support owners;
- retained application-log source and retention period;
- initial Legacy queue snapshot and lifecycle-integrity review;
- confirmed Formal health and zero production frontend Legacy POST;
- migration notice distribution record;
- exact UTC start timestamp and calculated target end date.

Until then:

```text
OBSERVATION_WINDOW_PENDING_DEPLOYMENT
LEGACY_ALIGNMENT_410_NOT_AUTHORIZED
```
