# Legacy Alignment Migration Notice

## Notice Status

- Audience: Legacy alignment API client owners and pilot operators
- Publication status: `DRAFT_NOT_DISTRIBUTED`
- Observation environment: `TARGET_PILOT_ENVIRONMENT_UNASSIGNED`
- Observation start: `PENDING_DEPLOYMENT`
- Earliest review date: `PENDING_START_DATE_PLUS_14_DAYS`
- Support owner: `SUPPORT_OWNER_PENDING`

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

The observation window has not started. It begins only after the target
environment, database, workers, retained log source, and named owners are
recorded. It then runs for at least 14 continuous calendar days and at least
five actual operating days.

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

- Observation owner: `OWNER_PENDING`
- Rollback owner: `ROLLBACK_OWNER_PENDING`
- Support owner/contact path: `SUPPORT_OWNER_PENDING`

The notice cannot be distributed as an operational deadline until these roles
and a target environment are assigned.

```text
OBSERVATION_WINDOW_PENDING_DEPLOYMENT
LEGACY_ALIGNMENT_410_NOT_AUTHORIZED
```
