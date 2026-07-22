# Legacy Alignment Observation Window

## Activation Status

- Task: `9C.5O.1`
- Baseline: `22f9976dc94ef448682cca5bb54a99bde2dc320e`
- Environment-readiness task: `9C.5O.2`
- Target environment name: `pilot-internal-local`
- Current state: `PREPARED`
- Start date: `PENDING_OBSERVATION_START`
- Target end date: `PENDING_START_DATE_PLUS_14_DAYS`
- Actual target operating days: `0`
- Required target operating days: `5`

```text
LEGACY_ALIGNMENT_OBSERVATION_ENVIRONMENT_READY
OBSERVATION_WINDOW_PENDING_START
LIMITED_OBSERVABILITY
EXTERNAL_CONSUMER_VISIBILITY_LIMITED
```

The target is the concrete `pilot-internal-local` controlled-pilot environment
declared in `docs/pilot_environment_declaration.md`. It has an identified
database, worker modes, owners, and evidence procedures. It is not currently
running an observation window, and no local test or preparation step counts as
Day 1.

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
| Deployment environment | Stable target name | `pilot-internal-local` |
| Database type | SQLite or PostgreSQL as actually deployed | SQLite |
| Database identity | Non-secret stable instance/file identifier | `project-root/backend/lexibridge.db` |
| Initial snapshot time | Retained UTC timestamp | required at observation start |
| Formal worker | Process/service identity and mode | `pilot-internal-formal-1`, Formal mode |
| Legacy worker | Process/service identity or confirmed stopped state | `pilot-internal-legacy-1`, isolated/on demand |
| Application log source | Retained stream/path and retention period | declared local sink; activation verification pending |
| Access/gateway logs | Source and query owner, or explicit unavailable decision | `UNAVAILABLE` |

Do not record database credentials, tokens, filesystem secrets, request
payloads, prompts, outputs, or private evidence in this declaration.

## Ownership

| Role | Responsibility | Current owner |
|---|---|---|
| Observation owner | Daily metrics, caller attribution, evidence retention | Project Maintainer |
| Rollback owner | Freeze rollback decision and execution | Project Maintainer |
| Support owner | Migration questions and caller communication | Project Maintainer |

The Project Maintainer owns the single-person controlled Pilot. A later
multi-person or hosted environment requires named operational contacts before
it enters the observation scope.

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
| Legacy POST | timestamp, caller ID/role, result, status, sync/async, creation counts | payload-free application event `legacy_alignment_request` | available; retained sink starts with window |
| Legacy history GET | timestamp, caller ID/role, route, status | payload-free application event `legacy_alignment_request` | available; retained sink starts with window |
| AlignmentRun creation | timestamp, caller/source, count | request creation count and internal creation event | available |
| Legacy BackgroundJob creation | timestamp, caller/source, count | request creation count and internal creation event | available |
| Queue state | queued, running, retrying, failed, oldest active age | `legacy_alignment_runtime.py status` and database snapshot | available; manual collection |
| Legacy worker | claim, start, completion, retry, failure, worker ID | `BackgroundJobEvent` plus worker process inventory | available; process correlation required |
| Formal run count | run count and terminal distribution | Formal WorkflowRun database snapshot | available |
| Formal Legacy POST count | `legacy_alignment_requests` | Formal frontend E2E/network artifact | available per operating-day run |
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

The environment is ready for a separately authorized start operation. Change
the state to `ACTIVE` only after all items below are recorded:

- target environment and authoritative database identity;
- Formal and Legacy worker process inventory;
- observation, rollback, and support owners;
- retained application-log source and retention period;
- initial Legacy queue snapshot and lifecycle-integrity review;
- confirmed Formal health and zero production frontend Legacy POST;
- migration notice distribution record;
- exact UTC start timestamp and calculated target end date.

Environment assignment is complete. Start-time log retention, snapshots,
notice distribution, process records, and timestamp remain pending. Until then:

```text
OBSERVATION_WINDOW_PENDING_START
LEGACY_ALIGNMENT_410_NOT_AUTHORIZED
```
