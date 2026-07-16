# Legacy Provider Healthcheck Boundary

Task: 9C.4L
Baseline commit: `3f9b6dfb7a3631032ccff07330d801106117ffd4`
Branch: `audit/legacy-provider-healthcheck-9c4l`
Status: characterization only. No route migration and no production behavior change.

## HTTP Contract

- URL: `POST /api/admin/ai/healthcheck`
- Flask endpoint: `admin_ai_healthcheck`
- Handler location: `backend/app.py`
- Handler size: 16 function body lines, 17 lines including the route decorator
- Authentication: required
- Allowed role: `admin`
- Rejected roles: unauthenticated 401, student 403, teacher 403
- Request body: optional JSON object
- Supported field: `live_probe`
- Unknown fields: ignored
- Empty JSON object: accepted
- Malformed JSON: Flask JSON parse error, HTTP 400
- Empty body without JSON content type: Flask unsupported media type, HTTP 415
- Success status: HTTP 200
- Success envelope: legacy `api_success`, top-level `status`, `message`, `data`
- Success `data`: `items`
- `request_id`: not returned by the current success response
- AuditRecord: none
- OpenAPI: listed under `/api/admin/ai/healthcheck`
- Frontend: no direct `frontend/index.html` call found

## Handler Responsibilities

| Segment | Current owner | Reads DB | Writes DB | Network risk | Business rule |
|---|---|---:|---:|---:|---:|
| Authentication and role check | route | token/user | token last-used flush | no | yes |
| Registry seed | `ensure_ai_registry_seed(...)` wrapper and seed service | provider/model/prompt | seed flush | no | yes |
| JSON parsing | route | no | no | no | no |
| Enabled provider loop | route | `AIProviderConfig` | health fields | no | yes |
| Local readiness decision | `services.ai_health.healthcheck_provider(...)` | no | no | no | yes |
| Live transport probe | `services.ai_health.healthcheck_provider(...)` through provider adapter | no | no | yes | yes |
| Commit | route | no | provider health and possible seed rows | no | yes |
| Response mapping | route | no | no | no | no |

The route still owns transaction completion. The seed service does not commit or roll back.

## Local readiness

Local readiness is the part that can be computed without provider transport:

- provider mode `none` returns unhealthy;
- provider mode `mock` returns healthy;
- provider mode `local_heuristic` returns healthy;
- live provider without a credential, or with a placeholder credential, returns unhealthy;
- live provider with a usable credential and `live_probe=false` returns unknown with "live probe skipped";
- `live_probe` omitted behaves like false.

This logic has no network dependency and can be isolated from route HTTP parsing.

## Live transport probe

Live transport probe starts only when all of the following are true:

- the route is called by an admin;
- an enabled provider config is selected;
- the selected provider mode is `live`;
- the selected provider has a non-placeholder credential from the environment/global provider selection;
- request JSON has `live_probe=true`.

The service then calls `provider_from_selection(selection).call(...)` with a `term_alignment` health payload. Characterization uses a spy and blocked socket/HTTP primitives. No test performs a real external request.

Current risk: adapter/provider error `message` is echoed through `healthcheck_provider(...)`. A sentinel in an adapter error message is returned in the healthcheck result. This means live probe redaction is not strong enough for direct route extraction.

## Execution Matrix

| Provider class | Provider status | Credential | `live_probe` | Transport intent | DB writes | HTTP/result |
|---|---|---:|---:|---:|---:|---|
| none | enabled | no | omitted/false/true | no | health fields and possible seed commit | 200, unhealthy |
| mock | enabled | n/a | omitted/false/true | no | health fields | 200, healthy |
| local_heuristic | enabled | n/a | omitted/false/true | no | health fields | 200, healthy |
| live external | enabled | missing/placeholder | false/true | no | health fields | 200, unhealthy missing-key message |
| live external | enabled | usable | false | no | health fields | 200, unknown skipped-live-probe message |
| live external | enabled | usable | true | yes | health fields if route completes | 200 with provider-derived healthy/unhealthy result, or exception if adapter raises outside its contract |
| any | disabled | any | any | no for that provider | none for disabled provider | omitted from `items` |
| unauthenticated | n/a | n/a | any | no | none | 401 |
| non-admin | n/a | n/a | any | no | none for provider health | 403 |
| malformed JSON | after admin auth and seed call | n/a | n/a | no | seed may be flushed but not committed by this path | 400 |
| empty non-JSON body | after admin auth and seed call | n/a | n/a | no | seed may be flushed but not committed by this path | 415 |

## Seed and transaction matrix

| Path | Seed flush | Health write | Call write | Usage write | Audit | Commit | Rollback |
|---|---:|---:|---:|---:|---:|---:|---:|
| unauthorized | no | no | no | no | no | no | no route rollback |
| role denied | no | no | no | no | no | no | no route rollback |
| malformed JSON | yes, after admin auth | no | no | no | no | no | caller/session cleanup required |
| empty non-JSON body | yes, after admin auth | no | no | no | no | no | caller/session cleanup required |
| local-only success | yes | yes | no | no | no | yes | no |
| credential missing | yes | yes | no | no | no | yes | no |
| live probe skipped | yes | yes | no | no | no | yes | no |
| live probe success/error result | yes | yes | no | no | no | yes if no exception escapes | no |
| live probe adapter exception escaping the health helper | yes | partial in session | no | no | no | no | no explicit route rollback |
| database commit exception | yes | partial in session | no | no | no | no | no explicit route rollback |
| AuditRecord exception | n/a | n/a | n/a | n/a | n/a | n/a | n/a, route writes no AuditRecord |

## Write-set

The success path can persist:

- `AIProviderConfig` seed rows;
- `AIModelRegistry` seed rows;
- `PromptTemplate` seed rows;
- `AIProviderConfig.health_status`;
- `AIProviderConfig.last_healthcheck_at`;
- `AIProviderConfig.updated_at`.

Characterization confirms it does not create or modify:

- `AICallLog`;
- `AlignmentProviderUsageRecord`;
- `AlignmentVerificationRun`;
- `AlignmentProviderPreflightRun`;
- `AuditRecord`;
- `ConceptAlignmentCard`.

## Credential flow

Credential source is not `AIProviderConfig`; that model has no API-key column. For live provider names, `ai_selection_from_config(...)` copies module-level environment-derived values such as `DEEPSEEK_API_KEY` or `OPENAI_API_KEY` into the `ProviderSelection` passed to health logic.

The route response does not include the credential when the health logic returns a safe message. The live probe path still passes the credential into the provider adapter. Current adapter error messages can be reflected into the API response, so live probe needs a redaction boundary before it is treated as safe.

## Timeout and error mapping

| Condition | Current mapping |
|---|---|
| no provider configured | result item `health_status=unhealthy` |
| mock/local provider | result item `health_status=healthy` |
| missing live credential | result item `health_status=unhealthy` |
| live credential but probe skipped | result item `health_status=unknown` |
| provider adapter returns success | result item `health_status=healthy` |
| provider adapter returns error | result item `health_status=unhealthy`, `error_code` from adapter |
| provider adapter returns error message with sensitive text | message is currently echoed |
| malformed JSON | HTTP 400 before route response mapping |
| empty non-JSON body | HTTP 415 before route response mapping |

No new timeout or error reason code is introduced by this task.

## Permissions

The route is admin-only. Student and teacher tokens receive 403. Unauthenticated calls receive 401. Provider existence, credential presence, adapter class, base URL, and transport exceptions are not disclosed to unauthenticated or non-admin callers.

## AuditRecord

The current handler does not create `AuditRecord` rows on success or failure. 9C.4L keeps that behavior.

## No-network and transport spy

Tests block `socket`, `urllib`, `requests`, and `httpx` on no-network-safe paths. For the live probe path, tests use a route-level healthcheck spy and a service-level adapter spy. The spy proves transport intent without allowing a real connection.

## Complexity metrics

| Metric | Value |
|---|---:|
| Handler lines including decorator | 17 |
| Function body lines | 16 |
| Direct route model count | 1 |
| Direct service/helper calls | 3: auth, seed, healthcheck |
| Return paths | 2 |
| Explicit commit points | 1 |
| Explicit rollback points | 0 |
| Provider transport call sites in route | 0 |
| Provider transport call sites in health service | 1 |
| Credential copy points | 1 in `ai_selection_from_config(...)` |
| Audit events | 0 |
| Tables possibly written by success path | 3 seed tables plus `AIProviderConfig` health fields |

## Final conclusion

Primary conclusion: `DISABLE_OR_DEPRECATE_LIVE_PROBE_FIRST`.

Reasoning:

- Local readiness and live transport probe are logically separable.
- The route is admin-only and no frontend call was found, but OpenAPI still exposes it.
- The route commits provider health fields and possible seed rows.
- Live probe can call provider adapter/transport when a live provider has a usable credential and `live_probe=true`.
- Current health helper echoes adapter error `message`; a sentinel in that message appears in the result. That is a redaction boundary risk.
- Direct route extraction would preserve a risky live transport behavior without first isolating and sanitizing it.

Next service plan:

1. Disable or deprecate the live probe behavior, or add an explicit redaction gate, before route extraction.
2. Create a local-readiness service that computes registry/config/credential-presence health without transport.
3. Create a separate live-probe service with explicit timeout, redaction, transport spy tests, and no raw adapter message passthrough.
4. Create a small healthcheck application service that owns transaction sequencing and calls local readiness plus optional live probe.
5. Only then move the thin `POST /api/admin/ai/healthcheck` HTTP adapter into a route module.
