# Pilot Environment Declaration

## Environment Identity

- Environment name: `pilot-internal-local`
- Purpose: controlled internal academic pilot and Legacy alignment observation
- Lifecycle: manually started for scheduled pilot sessions and stopped outside
  those sessions
- Deployment class: single-workstation local pilot
- Production status: not production and not production-like staging
- Observation state: `PREPARED`

```text
LEGACY_ALIGNMENT_OBSERVATION_ENVIRONMENT_READY
OBSERVATION_WINDOW_PENDING_START
EXTERNAL_CONSUMER_VISIBILITY_LIMITED
```

This declaration binds the observation preparation to one concrete local
environment. It does not start the 14-day window. The window starts only after
the activation checklist records a retained log sink, initial database and
queue snapshots, notice distribution, process identities, and a UTC start
timestamp.

## Application

| Field | Declared value |
|---|---|
| Product | LexiBridge AI Pilot v1.0 Candidate |
| Branch | `release/pilot-v1-candidate` |
| Environment-readiness baseline | `f04c32c38423192a3088bf32151ae51127eb3b3f` |
| Application runtime | local Flask process, debug disabled for pilot sessions |
| Frontend | same-origin static frontend served by the Flask application |
| Host boundary | Project Maintainer's designated pilot workstation |
| Provider boundary | external/live providers disabled |

The final observation start record must also capture the deployed commit. A
later documentation commit does not silently change the application baseline.

## Database

| Field | Declared value |
|---|---|
| Type | SQLite |
| Stable identity | `project-root/backend/lexibridge.db` |
| Size at readiness check | 1,015,808 bytes |
| Source fingerprint at readiness check | SHA-256 `42a195ab9033124f44f0441dc61c7c1effb5591a6b07db704429c226b5ebcaf0` |
| Readiness check | PASS on 2026-07-22; connectable, no reported integrity or orphan errors |
| Schema state | current local candidate tables present; no Alembic migration framework |
| Backup rehearsal | create, verify, and isolated restore PASS on 2026-07-22 |

The source fingerprint identifies this readiness snapshot only. It is expected
to change after legitimate application writes. Observation evidence must use
the snapshot ID and UTC timestamp rather than expecting a constant hash.

## Worker Processes

| Runtime | Mode | Planned identity | Ownership | Start policy |
|---|---|---|---|---|
| Formal worker | `--mode formal` | `pilot-internal-formal-1` | Project Maintainer | active during pilot sessions |
| Legacy worker | `--mode legacy-alignment` | `pilot-internal-legacy-1` | Project Maintainer | isolated; start only for compatibility work or approved drain |
| Application | Flask local pilot process | `pilot-internal-app-1` | Project Maintainer | active during pilot sessions |

No process supervisor is installed. Process start, stop, identity, and log-file
checks are therefore manual activation evidence and remain a pilot limitation.
The default/standard worker must not be used as a substitute for the declared
Formal and Legacy modes during the observation window.

## Ownership

| Role | Assigned owner | Responsibility |
|---|---|---|
| Observation owner | Project Maintainer | daily metrics, evidence retention, caller classification |
| Rollback owner | Project Maintainer | authorize and execute Active/Freeze rollback |
| Support owner | Project Maintainer | migration notice, pilot support, caller follow-up |
| Process owner | Project Maintainer | application and worker lifecycle |

For a multi-person or externally hosted pilot, these roles must be reassigned
to named operators with a contact path before that environment is added to the
observation scope.

## Logging And Evidence Sources

| Source | Target record | Availability |
|---|---|---|
| Direct HTTP access output | `logs/pilot-internal-local/application.log` | available from Flask/Werkzeug process output when retention is activated |
| Structured application events | same application log | available; payload-free Legacy events implemented |
| Formal worker output | `logs/pilot-internal-local/formal-worker.log` | available when worker is started with retained output |
| Legacy worker output | `logs/pilot-internal-local/legacy-worker.log` | available when worker is started with retained output |
| Job lifecycle | `BackgroundJobEvent` in the declared database | available |
| Queue and workflow state | read-only database snapshots | available |
| Gateway/reverse-proxy logs | none | `NOT_AVAILABLE` |
| Central metrics database | none | `NOT_AVAILABLE` |

Log files are ignored runtime artifacts and must not be committed. At
observation start, the owner must create the sink, verify redaction, record the
path and retention period, and prove that both HTTP and structured Legacy
events are present. A minimum 30-day local retention target covers the 14-day
window and review period.

## Metric Availability Matrix

| Metric | Source | Available | Notes |
|---|---|---|---|
| `POST /api/alignment/run` | structured `legacy_alignment_request` event | Yes | retained file sink must be activated at start |
| `GET /api/alignment/runs` | structured `legacy_alignment_request` event | Yes | list/detail routes remain compatibility reads |
| `AlignmentRun` creation | HTTP creation counts and internal creation event | Yes | payload-free counts only |
| Legacy `BackgroundJob` creation | HTTP creation counts and internal creation event | Yes | filtered to `alignment_run` |
| Legacy queue state | `legacy_alignment_runtime.py status` | Yes | manual timestamped snapshots |
| Legacy worker activity | `BackgroundJobEvent` and Legacy worker log | Yes | process identity must be correlated at start |
| Formal Run creation | `document_alignment_workflow_runs` snapshot | Yes | database count and terminal distribution |
| Formal worker execution | `BackgroundJobEvent`, Formal run state, worker log | Yes | retained worker sink starts with the process |
| Formal `legacy_alignment_requests` | Formal frontend E2E artifact | Yes | collect for each actual operating day |
| External caller network identity | gateway/reverse-proxy access logs | No | `NOT_AVAILABLE`; visibility remains limited |

Every required application/runtime metric is collectable in the declared
environment. The missing gateway source prevents a strong repository-external
consumer conclusion; it does not permit treating external traffic as zero.

## Required Pilot Configuration

The activation record must confirm these non-secret settings without copying
the local `.env` file into evidence:

```text
LEGACY_ALIGNMENT_OBSERVATION_ENABLED=true
LEGACY_ALIGNMENT_RUNTIME_STATE=active
LEGACY_ALIGNMENT_ROUTE_ADMISSION_ENABLED=true
LOG_REDACT_SECRETS=true
AI_PROVIDER_MODE=none
```

Freeze later changes only the Legacy runtime/admission values according to the
approved checklist. It must not change Formal workflow contracts.

## Readiness Boundary

The environment definition, database, worker modes, ownership, backup tools,
and evidence sources are ready for an observation-start operation. Remaining
start-time actions are operational: launch retained logs, capture initial
snapshots, distribute the notice, record process identities, and set the UTC
start timestamp.
