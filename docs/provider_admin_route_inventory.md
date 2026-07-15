# Provider/Admin Route Inventory

Task: 9C.4F
Baseline commit: `cb63cd657929e5c5f15efd6a9adc0e6384a08a86`
Branch: `audit/provider-admin-routes-9c4f`
Status: route inventory and characterization. Task 9C.4G has since extracted `GET /api/admin/alignment-runs`.

## Scope

This document inventories remaining provider/admin-adjacent routes after the 9C.4A through 9C.4E extractions:

- provider governance GET routes live in `backend/routes/provider_governance.py`;
- provider policy mutation lives in `backend/routes/provider_policy.py`;
- provider preflight POST lives in `backend/routes/provider_preflight.py`;
- `POST /api/alignment/verify` lives in `backend/routes/alignment_verification.py` and delegates execution to `backend/services/alignment_verification_execution.py`.

The remaining routes below still live in `backend/app.py`. Unknown route count after this scan: `0`.

## Remaining Route Inventory

| Route | Method | Endpoint | Lines | Classification | Read only | Auth/roles | OpenAPI | Frontend/scripts | Database writes | Network risk | Secret risk | Recommendation |
|---|---:|---|---:|---|---:|---|---:|---|---|---|---|---|
| `/api/admin/alignment-runs` | GET | `admin_alignment_runs` | module | `EXTRACTED_READ_ONLY_ADMIN_LISTING` | yes | admin only | no | README only | none | none | serialized run summaries only | extracted in `backend/routes/admin_alignment_runs.py` |
| `/api/admin/ai/providers` | GET | `admin_ai_providers` | 10 | `LEGACY_ACTIVE` / `READ_ONLY_PROVIDER_VIEW` | mostly | admin only | yes | frontend active | may flush registry seed if missing; no explicit commit | none in GET | provider config fields; no API keys returned | `DEPRECATION_AUDIT_REQUIRED` before extraction |
| `/api/admin/ai/models` | GET | `admin_ai_models` | 7 | `LEGACY_ACTIVE` / `READ_ONLY_PROVIDER_VIEW` | mostly | admin only | yes | frontend active | may flush registry seed if missing; no explicit commit | none | model registry fields; no credentials | `DEPRECATION_AUDIT_REQUIRED` before extraction |
| `/api/admin/ai/prompts` | GET | `admin_ai_prompts` | shared | `LEGACY_ACTIVE` | mostly | admin only | yes | frontend active | may flush registry seed if missing; no explicit commit | none | prompt templates only | split GET from POST before extraction |
| `/api/admin/ai/prompts` | POST | `admin_ai_prompts` | shared | `SERVICE_BOUNDARY_REQUIRED` | no | admin only | yes | frontend active | creates/updates `PromptTemplate`, commits | none | accepts template/schema text; no credentials by contract | service/contract task first |
| `/api/admin/ai/calls` | GET | `admin_ai_calls` | 6 | `READ_ONLY_PROVIDER_VIEW` | yes | admin only | yes | frontend active | none | none | serialized call logs; characterization verifies no sentinel secret | possible later with admin AI group |
| `/api/admin/ai/usage` | GET | `admin_ai_usage` | 6 | `READ_ONLY_PROVIDER_VIEW` | yes | admin only | yes | frontend active | none | none | usage summaries; characterization verifies no sentinel secret | possible later with admin AI group |
| `/api/admin/ai/health` | GET | `admin_ai_health` | 7 | `HEALTH_LOCAL_ONLY` / `LEGACY_ACTIVE` | mostly | admin only | yes | frontend active | may flush registry seed if missing; no explicit commit | none | health/config summary only | deprecation/service boundary first |
| `/api/admin/ai/healthcheck` | POST | `admin_ai_healthcheck` | 16 | `HEALTH_EXTERNAL_RISK` | no | admin only | yes | tested | updates provider health fields, commits | live mode with `live_probe=true` can call provider transport | health result only; must not expose credentials | do not extract until health service/security boundary is explicit |
| `/api/alignment/run` | POST | `run_alignment` | 159 | `EXECUTION_OR_REPLAY` / `SERVICE_BOUNDARY_REQUIRED` | no | student, teacher, admin | yes | frontend active, scripts/tests | creates `AlignmentRun`, background job or cards, records personal usage, commits | current provider metadata and legacy execution path; no live probe in normal characterization | alignment/card payloads | service boundary first |
| `/api/alignment/runs` | GET | `alignment_runs` | 29 | `LEGACY_ACTIVE` | yes | student, teacher, admin | yes | frontend active | none | none | serialized legacy `AlignmentRun` summaries | extract only after legacy alignment-run boundary decision |
| `/api/alignment/runs/<int:run_id>` | GET | `alignment_run_detail` | 16 | `LEGACY_ACTIVE` | yes | student, teacher, admin with owner/course/admin checks | yes | README/docs/tests | none | none | serialized legacy run detail | extract only after legacy alignment-run boundary decision |

## Already Extracted Provider Routes

| Route | Module | Relationship |
|---|---|---|
| `GET /api/alignment/providers` | `backend/routes/provider_governance.py` | Formal provider registry/governance listing. Overlaps with but does not match `/api/admin/ai/providers`. |
| `GET /api/alignment/providers/<provider_name>/policy` | `backend/routes/provider_governance.py` | Formal policy read path. |
| `POST /api/alignment/providers/<provider_name>/policy` | `backend/routes/provider_policy.py` | Formal policy mutation. |
| `GET /api/alignment/providers/<provider_name>/usage` | `backend/routes/provider_governance.py` | Formal alignment-provider usage listing. Different model from legacy `AICallLog` usage. |
| `GET /api/alignment/providers/<provider_name>/preflight` | `backend/routes/provider_governance.py` | Formal preflight history. |
| `POST /api/alignment/providers/<provider_name>/preflight` | `backend/routes/provider_preflight.py` | Formal local preflight execution. |
| `POST /api/alignment/verify` | `backend/routes/alignment_verification.py` | Formal alignment verification execution HTTP adapter. |

## Admin Alignment Runs Contract

- URL/method: `GET /api/admin/alignment-runs`
- Endpoint: `admin_alignment_runs`
- Authentication: required.
- Allowed roles: `admin` only.
- Query parameters: none.
- Request body: none.
- Success status: HTTP 200.
- Error statuses: unauthenticated 401; non-admin roles 403.
- Response top-level fields: `status`, `runs`.
- `request_id`: not returned by the current implementation.
- AuditRecord event: none observed.
- Data source: `AlignmentRun.query.order_by(AlignmentRun.id.desc()).limit(300)`.
- Writes: none.
- Commit/rollback: none.
- Network: none.
- OpenAPI: not currently listed.
- Frontend: no active frontend call found.
- Existing tests before this task: no dedicated contract test found.
- Status: `EXTRACTED_READ_ONLY_ADMIN_LISTING` in `backend/routes/admin_alignment_runs.py`.
- Suitability: extracted as a low-risk, narrow route module. It remains low product value because it is not in OpenAPI/frontend.

## Admin AI Providers Contract

- URL/method: `GET /api/admin/ai/providers`
- Endpoint: `admin_ai_providers`
- Authentication: required.
- Allowed roles: `admin` only.
- Success status: HTTP 200.
- Error statuses: unauthenticated 401; non-admin roles 403.
- Response envelope: `status`, `message`, `data`.
- Response `data`: `items` and `current`.
- `request_id`: not returned by the current implementation.
- AuditRecord event: none observed.
- Data source: `AIProviderConfig` plus `current_provider_metadata()`.
- Writes: calls `ensure_ai_registry_seed(owner_user_id=user.id)`, which can add/flush `AIProviderConfig`, `AIModelRegistry`, and `PromptTemplate` rows when the seed is missing. The GET handler does not explicitly commit.
- Network: none for this GET route.
- Secret redaction: characterization injects sentinel API key values and verifies they do not appear in the response.
- Relationship to formal API: overlaps with `GET /api/alignment/providers`, but schema, role set, storage model, and frontend use differ.
- Suitability: do not directly extract yet; first decide whether this legacy active view remains separate or should be deprecated/bridged to the formal provider governance API.

## Legacy Provider Routes

The `/api/admin/ai/*` group is active in `frontend/index.html` and OpenAPI. It is not the same surface as the 9C.4A formal provider governance API.

- `/api/admin/ai/providers`, `/models`, `/prompts`, and `/health` all call `ensure_ai_registry_seed(...)`.
- `/api/admin/ai/prompts` combines GET and POST in one handler; POST mutates `PromptTemplate`.
- `/api/admin/ai/healthcheck` mutates provider health fields and can reach external provider transport if a live provider is configured and `live_probe=true`.
- `/api/admin/ai/calls` and `/usage` are read-only over `AICallLog`, a legacy AI usage/cost surface distinct from `AlignmentProviderUsageRecord`.

These routes should not be extracted as one group until their compatibility and deprecation boundary is explicit.

## Legacy Alignment Run Routes

`/api/alignment/run` and `/api/alignment/runs*` are legacy alignment run APIs. They are active in the frontend and OpenAPI.

- `POST /api/alignment/run` is an execution route. It can create an `AlignmentRun`, create background jobs, run synchronous document/term alignment, create or update terminology cards, record personal AI usage, and commit.
- `GET /api/alignment/runs` is a role-filtered listing for student/teacher/admin.
- `GET /api/alignment/runs/<int:run_id>` is a role-filtered detail route.

The POST route requires a service boundary before route extraction. The two GET routes should be extracted only after deciding whether this legacy alignment-run surface remains separate from the newer `POST /api/alignment/verify` flow.

## Duplicate And Alias Matrix

| Route A | Route B | Same data | Same schema | Same roles | Same service | Alias candidate |
|---|---|---:|---:|---:|---:|---:|
| `/api/admin/ai/providers` | `/api/alignment/providers` | partial | no | no | no | no |
| `/api/admin/ai/usage` | `/api/alignment/providers/<provider_name>/usage` | no | no | no | no | no |
| `/api/admin/ai/health` | `/api/alignment/providers/<provider_name>/preflight` | no | no | no | no | no |
| `/api/admin/alignment-runs` | `/api/alignment/runs` | partial | no | no | yes, legacy `AlignmentRun` | no |
| `/api/alignment/run` | `/api/alignment/verify` | no | no | no | no | no |

There are overlapping concepts, but no safe drop-in alias was found.

## Write-set Matrix

| Path | VerificationRun | ProviderUsage | ProviderPolicy | Preflight | AlignmentRun | AI registry | Prompt | AICallLog | AuditRecord |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `/api/admin/alignment-runs` GET | 0 | 0 | 0 | 0 | read | 0 | 0 | 0 | 0 |
| `/api/admin/ai/providers` GET | 0 | 0 | 0 | 0 | 0 | possible seed flush | possible seed flush | 0 | 0 |
| `/api/admin/ai/models` GET | 0 | 0 | 0 | 0 | 0 | possible seed flush | possible seed flush | 0 | 0 |
| `/api/admin/ai/prompts` GET | 0 | 0 | 0 | 0 | 0 | possible seed flush | possible seed flush | 0 | 0 |
| `/api/admin/ai/prompts` POST | 0 | 0 | 0 | 0 | 0 | possible seed flush | write/commit | 0 | 0 |
| `/api/admin/ai/calls` GET | 0 | 0 | 0 | 0 | 0 | 0 | 0 | read | 0 |
| `/api/admin/ai/usage` GET | 0 | 0 | 0 | 0 | 0 | 0 | 0 | read | 0 |
| `/api/admin/ai/health` GET | 0 | 0 | 0 | 0 | 0 | possible seed flush | possible seed flush | 0 | 0 |
| `/api/admin/ai/healthcheck` POST | 0 | 0 | 0 | 0 | 0 | health write/commit | 0 | 0 | 0 |
| `/api/alignment/run` POST | 0 | 0 | 0 | 0 | write/commit | 0 | 0 | possible legacy usage side effect | 0 |
| `/api/alignment/runs` GET | 0 | 0 | 0 | 0 | read | 0 | 0 | 0 | 0 |
| `/api/alignment/runs/<id>` GET | 0 | 0 | 0 | 0 | read | 0 | 0 | 0 | 0 |

## Network And Secret Boundary

Characterization tests enforce no-network behavior for the read/list routes and for local `admin_ai_healthcheck` with `live_probe=false`.

Network risk remains in `POST /api/admin/ai/healthcheck` because `services/ai_health.py` calls provider transport when `live_probe=true` and the selected provider mode is `live`. This task does not execute that path.

Sentinel secret: `LEXIBRIDGE_SENTINEL_SECRET_9C4F`

The characterization suite verifies the sentinel does not appear in provider/admin responses covered by the tests. The legacy provider serializers still include legitimate fields such as token limits and token cost field names; those are not credentials.

## Frontend And Script Dependencies

Active frontend dependencies:

- `frontend/index.html` calls `/api/alignment/runs`.
- `frontend/index.html` calls `/api/alignment/run`.
- `frontend/index.html` calls `/api/admin/ai/providers`, `/models`, `/prompts`, `/calls`, `/usage`, and `/health`.

OpenAPI dependencies:

- `/api/alignment/run`, `/api/alignment/runs`, and `/api/alignment/runs/{run_id}` are listed.
- `/api/admin/ai/providers`, `/models`, `/prompts`, `/calls`, `/usage`, `/health`, and `/healthcheck` are listed.
- `/api/admin/alignment-runs` is not listed.

`/api/admin/alignment-runs` appears in README/admin route documentation but no active frontend call was found.

## Complexity Snapshot

| Endpoint | Lines | Direct models | Service/helper calls | Returns | Writes | Network risk | Extraction suitability |
|---|---:|---:|---:|---:|---:|---:|---|
| `admin_alignment_runs` | module | 1 | serializer | 1 | 0 | no | `EXTRACTED_READ_ONLY_ADMIN_LISTING` |
| `admin_ai_providers` | 10 | 1 | seed, metadata, serializer | 1 | possible seed flush | no | `DEPRECATION_AUDIT_REQUIRED` |
| `admin_ai_models` | 7 | 1 | seed, serializer | 1 | possible seed flush | no | `DEPRECATION_AUDIT_REQUIRED` |
| `admin_ai_prompts` | 31 | 1 | seed, validation, serializer | 3 | yes on POST | no | `SERVICE_BOUNDARY_REQUIRED` |
| `admin_ai_calls` | 6 | 1 | serializer | 1 | 0 | no | `DIRECT_EXTRACTION_SAFE` inside legacy group |
| `admin_ai_usage` | 6 | 1 | summary serializer | 1 | 0 | no | `DIRECT_EXTRACTION_SAFE` inside legacy group |
| `admin_ai_health` | 7 | 1 | seed, serializer | 1 | possible seed flush | no | `DEPRECATION_AUDIT_REQUIRED` |
| `admin_ai_healthcheck` | 16 | 1 | seed, healthcheck service | 1 | yes | yes in live-probe mode | `DO_NOT_TOUCH_YET` |
| `run_alignment` | 159 | many | course/auth/job/alignment/card/usage helpers | 14 | yes | provider-dependent | `SERVICE_BOUNDARY_REQUIRED` |
| `alignment_runs` | 29 | 2 | course permission, serializer | 1 | 0 | no | `EXTRACTION_AFTER_LEGACY_BOUNDARY` |
| `alignment_run_detail` | 16 | 2 | course permission, serializer | 4 | 0 | no | `EXTRACTION_AFTER_LEGACY_BOUNDARY` |

## Final Decision

Primary conclusion after Task 9C.4G: `ADMIN_ALIGNMENT_RUNS_EXTRACTED`

Reasoning:

- `GET /api/admin/alignment-runs` is a small admin-only read path.
- It does not write `AlignmentRun`, provider usage, provider policy, preflight, or audit rows.
- It does not call provider transport or access the network.
- It does not return credentials or raw provider secrets.
- It is independent from the active frontend provider admin views.
- Extracting it should not freeze the legacy `/api/admin/ai/*` design.

Task 9C.4G extracted only `GET /api/admin/alignment-runs` into `backend/routes/admin_alignment_runs.py`. It did not include `/api/admin/ai/*`, `/api/alignment/run`, `/api/alignment/runs`, healthcheck, prompt mutation, or any provider transport path.

Secondary follow-up:

- Run a separate legacy provider admin compatibility/deprecation audit before migrating `/api/admin/ai/*`.
- Establish a service boundary before touching `POST /api/alignment/run` or `POST /api/admin/ai/healthcheck`.
