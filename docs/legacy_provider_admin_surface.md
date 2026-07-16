# Legacy Provider Admin Surface Audit

Task: 9C.4H
Baseline commit: `b9b5b0a53b5db6a89911bd659a9ec6c39b0c49dd`
Branch: `audit/legacy-provider-admin-9c4h`
Status: characterization and boundary audit only. No production route was migrated or changed.

## Scope

This audit covers the legacy provider admin surface under `/api/admin/ai/*` and its overlap with the formal alignment-provider governance APIs. It does not cover or migrate `POST /api/alignment/run`; that route remains a separate legacy execution surface that needs its own service boundary.

Unknown legacy provider admin route count after scan: `0`.

## Route Inventory

| Route | Method | Endpoint | Handler lines | Classification | Auth/roles | OpenAPI | Frontend | Seed helper | Writes | Network risk | Recommendation |
|---|---:|---|---:|---|---|---:|---:|---:|---|---|---|
| `/api/admin/ai/providers` | GET | `admin_ai_providers` | 10 | `LEGACY_AGGREGATE_VIEW` | admin only | yes | yes | yes | seed flush only; no commit | no | keep as legacy read view or shim; do not mix with healthcheck |
| `/api/admin/ai/models` | GET | `admin_ai_models` | 7 | `LEGACY_READ_ONLY_VIEW` | admin only | yes | yes | yes | seed flush only; no commit | no | safe read candidate after legacy API decision |
| `/api/admin/ai/prompts` | GET | `admin_ai_prompts` | shared | `LEGACY_READ_ONLY_VIEW` | admin only | yes | yes | yes | seed flush only; no commit | no | split from POST before extraction |
| `/api/admin/ai/prompts` | POST | `admin_ai_prompts` | shared | `LEGACY_MUTATION` | admin only | yes | no direct frontend call found | yes | creates/updates `PromptTemplate`, commits | no | separate mutation/service-boundary task |
| `/api/admin/ai/calls` | GET | `admin_ai_calls` | 6 | `LEGACY_READ_ONLY_VIEW` | admin only | yes | yes | no | none | no | safe read candidate inside legacy read-only group |
| `/api/admin/ai/usage` | GET | `admin_ai_usage` | 6 | `LEGACY_READ_ONLY_VIEW` | admin only | yes | yes | no | none | no | safe read candidate inside legacy read-only group |
| `/api/admin/ai/health` | GET | `admin_ai_health` | 7 | `LEGACY_LOCAL_HEALTH` | admin only | yes | yes | yes | seed flush only; no commit | no | keep with read-only view, not live probe |
| `/api/admin/ai/healthcheck` | POST | `admin_ai_healthcheck` | 16 | `LEGACY_EXTERNAL_HEALTH_RISK` | admin only | yes | no direct frontend call found | yes | commits provider health and may persist env seed | yes when live provider plus `live_probe=true` | service boundary required before extraction |

All routes keep the existing legacy response convention from `api_success`: top-level `status`, `message`, and `data`. None of these legacy admin AI routes returns `request_id` today.

## Formal API Overlap Matrix

| Legacy route | Formal route | Same source | Same fields | Same roles | Same side effects | Frontend replaceable |
|---|---|---:|---:|---:|---:|---:|
| `/api/admin/ai/providers` | `/api/alignment/providers` | partial | no | no; legacy is admin-only, formal allows teacher/admin | no; legacy can seed-flush registry rows | possible only with field mapping |
| `/api/admin/ai/models` | none | no | no | no | no | no direct formal replacement |
| `/api/admin/ai/prompts` GET | none | no | no | no | no | no direct formal replacement |
| `/api/admin/ai/calls` | none | no | no | no | no | no direct formal replacement |
| `/api/admin/ai/usage` | `/api/alignment/providers/<provider_name>/usage` | no; legacy uses `AICallLog`, formal uses alignment provider usage | no | no | no | no |
| `/api/admin/ai/health` | `/api/alignment/providers/<provider_name>/preflight` | no | no | no | no; health may seed-flush legacy registry | no |
| `/api/admin/ai/healthcheck` | `/api/alignment/providers/<provider_name>/preflight` POST | no | no | no | no; healthcheck mutates legacy provider health and can call transport | no |

The legacy surface is not a simple alias of the 9C.4A-9C.4C formal provider governance/preflight surface. It is an active UI contract over legacy provider registry, model registry, prompt templates, AI call logs, usage summaries, and provider health state.

## Registry Seed Side Effects

| Route | Calls `ensure_ai_registry_seed` | GET/POST | Persistent without explicit commit | What can be flushed | Characterized behavior |
|---|---:|---|---:|---|---|
| `/api/admin/ai/providers` | yes | GET | no | `AIProviderConfig`, `AIModelRegistry`, `PromptTemplate` | first request returns seeded rows but they are not persisted after the request without a later commit |
| `/api/admin/ai/models` | yes | GET | no | same | response may include flushed seed rows |
| `/api/admin/ai/prompts` | yes | GET | no | same | response may include flushed prompt defaults |
| `/api/admin/ai/prompts` | yes | POST | yes | same plus target `PromptTemplate` | mutation commits prompt changes and may also persist seed rows |
| `/api/admin/ai/calls` | no | GET | n/a | none | no registry seed |
| `/api/admin/ai/usage` | no | GET | n/a | none | no registry seed |
| `/api/admin/ai/health` | yes | GET | no | same | response may include flushed seed rows |
| `/api/admin/ai/healthcheck` | yes | POST | yes | same plus provider health fields | commits health fields and may persist env-selected seed rows |

This seed behavior is the main reason the legacy read-only views should be extracted separately from prompt mutation and healthcheck. A future cleanup can move seed initialization to startup, migration, or an explicit service, but 9C.4H does not change current behavior.

## Healthcheck Execution Matrix

| Provider type | Credential present | `live_probe` | Transport called | Network risk | Result contract |
|---|---:|---:|---:|---:|---|
| `none` | no | false/true | no | no | unhealthy, local message |
| `mock` | n/a | false/true | no | no | healthy, development-only message |
| `local_heuristic` | n/a | false/true | no | no | healthy, development-only message |
| live provider, missing/placeholder credential | no | false/true | no | no | unhealthy, missing-key message |
| live provider, usable credential | yes | false | no | no | unknown, live probe skipped |
| live provider, usable credential | yes | true | yes, via `provider_from_selection(...).call(...)` | yes | healthy/unhealthy based on provider result |

The test suite verifies the route passes `live_probe=True` through to healthcheck logic for an enabled live provider, using a spy rather than a real network call. The service-level characterization verifies `healthcheck_provider(...)` calls the provider adapter only when `live_probe=True`, mode is `live`, and a non-placeholder credential is present.

## Network And Secret Boundary

No-network coverage exists for:

- all legacy admin AI GET routes;
- unauthorized and role-denied paths;
- local healthcheck paths;
- `live_probe=false`;
- mock/local provider healthcheck;
- service-level live-probe transport intent via spy, without allowing a real connection.

Sentinel used by 9C.4H: `LEXIBRIDGE_SENTINEL_SECRET_9C4H`.

The current legacy serializers do not return API key fields. They do return non-secret operational fields such as `base_url`, token limits, cost estimates, health status, redacted prompt previews, and redacted response previews. A future healthcheck service boundary must keep transport exception text and live provider response summaries sanitized before returning them through `/api/admin/ai/healthcheck`.

## Write-set Matrix

| Route | Provider registry | Model registry | PromptTemplate | AICallLog | Usage | VerificationRun | ProviderPolicy | Preflight | AuditRecord |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| providers GET | possible flush, no commit | possible flush, no commit | possible flush, no commit | 0 | 0 | 0 | 0 | 0 | 0 |
| models GET | possible flush, no commit | possible flush, no commit | possible flush, no commit | 0 | 0 | 0 | 0 | 0 | 0 |
| prompts GET | possible flush, no commit | possible flush, no commit | possible flush, no commit | 0 | 0 | 0 | 0 | 0 | 0 |
| prompts POST | possible committed seed | possible committed seed | create/update commit | 0 | 0 | 0 | 0 | 0 | 0 |
| calls GET | 0 | 0 | 0 | read | 0 | 0 | 0 | 0 | 0 |
| usage GET | 0 | 0 | 0 | read | 0 | 0 | 0 | 0 | 0 |
| health GET | possible flush, no commit | possible flush, no commit | possible flush, no commit | 0 | 0 | 0 | 0 | 0 | 0 |
| healthcheck POST | committed seed possible; health fields commit | committed seed possible | committed seed possible | 0 | 0 | 0 | 0 | 0 | 0 |

No route in `/api/admin/ai/*` writes `AlignmentVerificationRun`, `AlignmentProviderUsageRecord`, `AlignmentProviderPolicy`, `AlignmentProviderPreflightRun`, or `AuditRecord` under current characterization.

## Permissions

All `/api/admin/ai/*` routes are admin-only.

- unauthenticated: 401;
- student: 403;
- teacher: 403;
- admin: allowed.

Course permissions are not consulted by this surface. Provider existence, credential state, and registry details are not exposed to non-admin roles through these routes.

## Frontend And OpenAPI Dependencies

`frontend/index.html` currently calls:

- `/api/admin/ai/providers`
- `/api/admin/ai/models`
- `/api/admin/ai/prompts`
- `/api/admin/ai/calls`
- `/api/admin/ai/usage`
- `/api/admin/ai/health`

No direct frontend call to `/api/admin/ai/healthcheck` was found. The healthcheck route is still listed in OpenAPI and tested, so it cannot be removed or renamed without a compatibility plan.

All `/api/admin/ai/*` routes are present in `docs/openapi.yaml`.

## Deprecation And Migration Suitability

| Route | Suitability |
|---|---|
| `/api/admin/ai/providers` GET | `KEEP_LEGACY_SHIM` or extract with read-only legacy group after frontend/formal API mapping |
| `/api/admin/ai/models` GET | `KEEP_AND_EXTRACT` inside legacy read-only view group |
| `/api/admin/ai/prompts` GET | `KEEP_AND_EXTRACT` only after splitting from POST |
| `/api/admin/ai/prompts` POST | `SERVICE_BOUNDARY_FIRST` |
| `/api/admin/ai/calls` GET | `KEEP_AND_EXTRACT` inside legacy read-only view group |
| `/api/admin/ai/usage` GET | `KEEP_AND_EXTRACT` inside legacy read-only view group |
| `/api/admin/ai/health` GET | `KEEP_AND_EXTRACT` as local health view only |
| `/api/admin/ai/healthcheck` POST | `SERVICE_BOUNDARY_FIRST` because live probe can call transport |

## Complexity Snapshot

| Endpoint | Lines | Direct models | Helper/service calls | Returns | Writes | Network risk | Migration suitability |
|---|---:|---:|---:|---:|---:|---:|---|
| `admin_ai_providers` | 10 | 1 | seed, metadata, serializer | 1 | seed flush only | no | extract only with read-only legacy group |
| `admin_ai_models` | 7 | 1 | seed, serializer | 1 | seed flush only | no | extract only with read-only legacy group |
| `admin_ai_prompts` GET | shared | 1 | seed, serializer | 1 | seed flush only | no | split from POST first |
| `admin_ai_prompts` POST | shared | 1 | seed, validation, serializer | 3 | commit | no | service boundary or separate mutation task |
| `admin_ai_calls` | 6 | 1 | serializer | 1 | 0 | no | read-only extraction candidate |
| `admin_ai_usage` | 6 | 1 | summary serializer | 1 | 0 | no | read-only extraction candidate |
| `admin_ai_health` | 7 | 1 | seed, serializer | 1 | seed flush only | no | read-only extraction candidate |
| `admin_ai_healthcheck` | 16 | 1 | seed, healthcheck service | 1 | commit health/seed | yes in live probe | service boundary first |

## Final Conclusion

Primary conclusion: `SPLIT_READONLY_AND_HEALTHCHECK_FIRST`.

Reasoning:

- The legacy admin AI GET views are active frontend/OpenAPI surface and are not drop-in aliases of formal provider governance APIs.
- Several GET views have a seed-flush side effect but do not commit by themselves.
- `POST /api/admin/ai/prompts` is a mutation sharing the same handler as prompt GET.
- `POST /api/admin/ai/healthcheck` commits provider health fields and can call provider transport in live-probe mode.
- There are no unknown `/api/admin/ai/*` routes after scan.

Next precise slice: split and extract only the safe legacy read-only provider admin views, while leaving prompt mutation and healthcheck in `backend/app.py`. A separate follow-up should then create a service boundary that separates local health summary from live transport probing before moving `/api/admin/ai/healthcheck`.
