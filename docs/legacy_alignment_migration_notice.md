# Legacy Alignment Migration Notice

## Notice Status

- Audience: Legacy alignment API client owners and pilot operators
- Publication status: `READY_FOR_DISTRIBUTION`
- Observation environment: `pilot-internal-local`
- Observation start: `PENDING_OBSERVATION_START`
- Earliest review date: `PENDING_START_DATE_PLUS_14_DAYS`
- Support owner: Project Maintainer

This is a migration notice draft. It does not announce retirement, HTTP 410,
or route removal.

## Legacy API Status

`POST /api/alignment/run` remains a deprecated active compatibility surface.
Its URL, method, permissions, request, response, and local compatibility
behavior remain unchanged. External provider execution remains disabled.

The read-only history surfaces remain active and are not part of the POST
retirement decision:

- `GET /api/alignment/runs`;
- `GET /api/alignment/runs/{run_id}`;
- `GET /api/admin/alignment-runs`.

## Supported Replacement

New teacher workflows must use the Formal Document Alignment API:

- `POST /api/document-alignment-runs`;
- `GET /api/document-alignment-runs/{run_uid}`;
- `GET /api/document-alignment-runs/{run_uid}/items`.

Clients must preserve the Formal API's permission, source identity,
Idempotency-Key, polling, and server-side pagination contracts. They must not
fall back to the Legacy POST after a Formal API failure.

## Observation Timeline

The observation window has not started. The target environment, database,
worker modes, and owners are declared. Distribution, retained log activation,
initial snapshots, process records, and the UTC start timestamp must be
recorded before timing begins. The window then runs for at least 14 continuous
calendar days and at least five actual operating days.

No retirement date is set. Any unexplained Legacy creation, incomplete queue
drain, external-consumer uncertainty, rollback, or Formal regression extends
or restarts the observation period.

## Client Action

Known Legacy POST client owners must:

1. identify the client, environment, schedule, and responsible owner;
2. migrate execution to the Formal API;
3. confirm whether Legacy history reads are still required;
4. report any blocked migration before the observation review.

Do not include credentials, tokens, prompts, outputs, or private request
payloads in migration evidence.

## Contacts

- Observation owner: Project Maintainer
- Rollback owner: Project Maintainer
- Support owner/contact path: Project Maintainer pilot coordination channel

The notice is ready to distribute to the controlled Pilot participants. The
owner must record recipients, channel, version, and UTC distribution time. It
must not state a retirement date or imply that the Legacy API is already gone.

```text
LEGACY_ALIGNMENT_OBSERVATION_ENVIRONMENT_READY
OBSERVATION_WINDOW_PENDING_START
LEGACY_ALIGNMENT_410_NOT_AUTHORIZED
```
