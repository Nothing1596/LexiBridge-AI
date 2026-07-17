# Legacy Alignment Run Boundary

Status: `CHARACTERIZED`
Task: 9C.4S
Baseline: `d82798012c263d54761a42c0ebff57ef9e78f8b2`
Main conclusion: `DEPRECATE_LEGACY_ALIGNMENT_RUN_FIRST`

This document freezes the current behavior of `POST /api/alignment/run`. It
does not describe a new implementation and does not claim the legacy route is
safe to extract as a service.

## Route Registration

| Concern | Current behavior |
|---|---|
| URL | `/api/alignment/run` |
| Method | `POST` |
| Flask endpoint | `run_alignment` |
| Registration | `@app.route("/api/alignment/run", methods=["POST"])` |
| File | `backend/app.py` |
| Handler lines | `10125` through `10284` |
| Handler size | 160 lines including decorator, 159 function lines |
| Duplicate rule | none |
| Route module | none |
| OpenAPI | listed in `docs/openapi.yaml` |
| Frontend | active call in `frontend/index.html::runAlignmentForDocument` |

The route remains a legacy active frontend surface. It is not an alias for
`POST /api/alignment/verify`.

## HTTP Contract

| Concern | Current behavior |
|---|---|
| Authentication | required bearer token |
| Roles | `student`, `teacher`, `admin` |
| Reviewer role | rejected with `PERMISSION_DENIED` |
| Query | `sync=true`, `sync=1`, or `sync=yes` runs synchronous behavior |
| Body | `request.get_json() or {}` |
| Empty body | teacher/admin receive course-scope `PERMISSION_DENIED` before missing-term validation |
| Malformed JSON | Flask 400 before route handling |
| Non-object JSON | unhandled route exception, API 500 under non-propagating Flask config |
| Required runtime fields | `english_term` or `document_id`, after scope/course permission checks |
| Scope | `course` or `personal`, default `course` |
| Unknown fields | ignored except known `courseware_sentence`, `chapter`, `course_id`, `course_name`, `document_id`, `english_term`, `scope_type` |
| Success async status | 200 |
| Success sync direct status | 200 |
| Success sync document status | 200 |
| Success request_id | absent |
| Error request_id | absent for this legacy route |
| AuditRecord | none from the route |

Response envelopes differ by branch:

| Branch | Response shape |
|---|---|
| Async default | `api_success({"alignment_run_id", "job_id", "job_type", "job_status", "run", "job"}, "术语对齐任务已进入后台队列。")` |
| Sync document | raw `jsonify({"status": "success", "message": "文档术语对齐已完成。", "cards": [...]})` |
| Sync direct term | raw `jsonify({"status": "success", "message": "术语证据对齐已完成。", "alignment": ..., "card": ...})` |

## Frontend And OpenAPI

`frontend/index.html` still calls `/api/alignment/run` when a user triggers
document terminology alignment. The frontend expects either:

- an async queued response containing `data.job_id`, followed by
  `loadJobs()` and `loadAlignmentRuns()`;
- or a non-queued success response that still has `status=success`.

OpenAPI lists only a small request schema:

- `document_id`
- `english_term`
- `course_id`
- `scope_type`

Runtime also reads `course_name`, `courseware_sentence`, `chapter`, and the
`sync` query parameter. OpenAPI does not describe the three distinct response
shapes.

## Formal Verification Comparison

| Concern | Legacy `/api/alignment/run` | Formal `/api/alignment/verify` |
|---|---|---|
| Route owner | `backend/app.py` | `backend/routes/alignment_verification.py` |
| Application service | none | `services/alignment_verification_execution.py` |
| Primary run model | `AlignmentRun` | `AlignmentVerificationRun` |
| Card model | `TerminologyCard` | `ConceptAlignmentCard` optional attach |
| Provider policy | not invoked | `evaluate_provider_request(...)` |
| Provider preflight | not invoked | separate readiness route and governance gate |
| Provider usage | no `AlignmentProviderUsageRecord` | one `AlignmentProviderUsageRecord` per verification result |
| Audit | no `AuditRecord` | request/completed/failed/policy/attach events |
| request_id | absent on success and errors | present through audit context |
| Parser | legacy `call_ai_task` JSON validation plus fallback | formal output parser/schema |
| Auto-approve gate | legacy `TerminologyCard` status machine can auto approve live evaluated models | formal provider result cannot auto approve |
| Attach gate | direct `TerminologyCard` create/update | explicit `attach_to_card` plus policy gate |
| Transaction | route/helper owned commits, no explicit route rollback | execution service owns commit/rollback |
| Credential access | legacy provider globals and `ai_selection_from_config` | governed provider registry |
| Network intent | possible for live default provider with API key | guarded by provider policy and disabled external providers |

The two routes are not compatible schemas and do not write the same tables.

## Handler Responsibility Split

| Section | Current location | Reads | Writes | Network risk | Future owner |
|---|---|---:|---:|---:|---|
| HTTP adapter | `run_alignment` | request, auth, course | none | no | route or compatibility adapter |
| Async queue setup | `run_alignment` | document/course/provider metadata | `AlignmentRun`, `BackgroundJob` | no direct network | replacement workflow or compatibility adapter |
| Sync document execution | `run_alignment` + `run_alignment_for_chunks` | `Document`, `DocumentChunk`, evidence | `AlignmentRun`, `TerminologyCard`, optional `UsageRecord` | possible through legacy AI task when provider is real | deprecated or split execution service |
| Sync direct execution | `run_alignment` + `generate_alignment_result` | evidence retrieval, provider metadata | `AlignmentRun`, `TerminologyCard`, `AICallLog`, optional `UsageRecord`, `SystemLog` | possible through live provider | deprecated or split execution service |
| Persistence | route and helpers | many legacy tables | commits in route/helper call chain | no separate safety gate | persistence plan only after deprecation policy |
| Compatibility | route response branches | frontend assumptions | none | no | compatibility policy |

## Provider Selection

The legacy route uses `current_provider_metadata()` and `call_ai_task(...)`.
Those paths use:

- `ensure_ai_registry_seed(...)`;
- `ai_selection_from_config(...)`;
- module-level provider globals such as `AI_PROVIDER`, `DEEPSEEK_API_KEY`,
  `OPENAI_API_KEY`, and base URLs;
- `provider_from_selection(...)`;
- `urllib.request.urlopen(...)` for OpenAI-compatible live providers.

The route does not accept a formal provider selection payload and does not call
the formal provider registry used by `/api/alignment/verify`.

| Condition | Current result |
|---|---|
| No provider configured | local fallback after `AICallLog` error |
| Mock/local provider | local/mock result, requires QC |
| Live provider default with usable key | live transport intent exists |
| Live transport exception | route falls back to local heuristic for sync direct path |
| Provider disabled by formal policy | not checked |
| Preflight not ready | not checked |
| Credential missing | legacy provider error/fallback |

## Policy And Preflight

| Condition | Policy invoked | Preflight invoked | Execution attempted | Result |
|---|---:|---:|---:|---|
| Async default request | no | no | no immediate provider execution | queued `AlignmentRun` and `BackgroundJob` |
| Sync direct no provider | no | no | legacy `call_ai_task` with none provider | fallback card/result |
| Sync document no provider | no | no | local term extraction plus legacy alignment per term | cards/result |
| Live provider default | no | no | legacy live transport intent | fallback if transport spy blocks |
| Formal provider disabled | no | no | not evaluated as formal policy | legacy behavior |

The route bypasses the formal provider governance and preflight chain.

## Evidence And Prompt

Evidence sources:

- direct term path retrieves English and Chinese evidence via
  `retrieve_evidence_results(...)`;
- document path reads `DocumentChunk` rows and extracts terms locally;
- unknown request fields are ignored.

Prompt sources:

- prompt key is `term_alignment`;
- prompt version is `v1`;
- prompt template lookup happens inside legacy `call_ai_task(...)`;
- prompt text is not returned in API responses;
- `AICallLog` stores redacted prompt and response previews for provider calls.

Legal course/evidence text is business data and must not be keyword-redacted as
if it were a credential. Credential-like unknown request metadata is ignored by
the route and was characterized with `LEXIBRIDGE_SENTINEL_SECRET_9C4S`.

## Parser And Result Semantics

Legacy sync direct execution:

- calls `call_ai_task(task_type="term_alignment", ...)`;
- validates the provider result with `validate_ai_json(...)`;
- on any provider failure, catches the exception in `generate_alignment_result`
  and uses a local heuristic fallback;
- finalizes result through `finalize_alignment_result(...)`;
- writes `TerminologyCard` using `create_or_update_card_from_alignment(...)`.

This is not the formal output parser/schema chain. It can create or update
`TerminologyCard` and can auto approve only through the older
`can_use_model_for_auto_approval(...)` and status machine rules when a live,
evaluated model is configured. Formal verification never auto approves a card.

## Execution Matrix

| Path | Provider/policy/preflight | Execution | HTTP/result |
|---|---|---|---|
| Unauthenticated | none | none | 401 `AUTH_REQUIRED` |
| Reviewer | none | none | 403 `PERMISSION_DENIED` |
| Student course request | none | none | 403 `PERMISSION_DENIED` |
| Teacher empty body | none | none | 403 before missing-term validation |
| Invalid scope | none | none | 400 `VALIDATION_ERROR` |
| Malformed JSON | none | none | Flask 400 |
| Non-object JSON | none | none | API 500 when exceptions do not propagate |
| Async direct term | no formal gates | no immediate provider execution | queued `AlignmentRun` and `BackgroundJob` |
| Sync direct term | no formal gates | legacy evidence + `call_ai_task` + fallback | raw success with `alignment` and `card` |
| Sync document | no formal gates | legacy term extraction + card generation | raw success with `cards` |
| Live default provider | no formal gates | live transport intent before fallback | raw success if transport exception is caught |
| Repeated async request | none | no idempotency | new `AlignmentRun` and new `BackgroundJob` |

## Transport Intent

Characterization blocks `socket.socket` and `urllib.request.urlopen`.

Findings:

- async default request has zero socket/urlopen calls;
- sync direct request with default none/local provider has zero socket/urlopen
  calls but does select a legacy provider adapter;
- sync document request under default none/local provider has zero socket/urlopen
  calls;
- when a live provider is made the default and an API key is present, the route
  reaches `urllib.request.urlopen(...)` through the legacy provider adapter. The
  test stops before a real connection.

This is the strongest reason not to extract the current route as a normal
application service.

## Credential Flow

| Source | Current behavior |
|---|---|
| Request body credential-like unknown fields | ignored |
| Module globals | `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, base URL globals can be read |
| Environment | `env_provider_selection(os.environ)` participates in seed and selection |
| Provider adapter | receives API key when live provider is selected |
| Transport | Authorization header is built inside `OpenAICompatibleProvider` |
| API response | sentinel not returned in characterization |
| AuditRecord | no legacy route audit |
| AICallLog | redacted previews; live transport exception path did not persist sentinel |
| AlignmentRun/TerminologyCard | sentinel not persisted in characterized fields |

## Write-set Matrix

| Path | AlignmentRun | BackgroundJob | TerminologyCard | AICallLog | UsageRecord | VerificationRun | ProviderUsage | Preflight | Audit | Commit | Rollback |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Unauthorized | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Validation/permission failure | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Async direct term | +1 queued | +1 queued | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| Sync direct term course | +1 completed | 0 | +1/update | +1 under none/local provider failure | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| Sync direct term personal | +1 completed | 0 | +1/update | +1 under none/local provider failure | +1 | 0 | 0 | 0 | 0 | 1 | 0 |
| Sync document | +1 completed | 0 | +N/update | possible per term | optional personal usage | 0 | 0 | 0 | possible parse-risk audit only | 1 | helper exceptions only |
| Repeated async request | +1 each request | +1 each request | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 each | 0 |
| Commit failure | unhandled 500 | maybe pending before rollback | pending before rollback | pending before rollback | pending before rollback | 0 | 0 | 0 | 0 | commit raises | no explicit handler rollback |

## Transaction

The route owns direct `db.session.commit()` calls in each branch. It does not
contain an explicit rollback. Helper functions can raise after mutating the
session. Commit failure currently maps to an API 500 only when Flask error
handling is allowed to catch the exception; tests must manually roll back the
session afterward.

The formal verification service differs: it owns explicit rollback in known
failure paths and records typed audit outcomes.

## Usage And Audit

| Concern | Legacy `/api/alignment/run` |
|---|---|
| `AlignmentProviderUsageRecord` | never written by characterized paths |
| Legacy `UsageRecord` | written for personal sync alignment/card paths |
| `AuditRecord` | not written by normal async/direct sync paths |
| Provider usage audit | not written |
| Request audit | not written |
| Card attach audit | not written |
| `request_id` | not attached |

Parse-quality risk propagation inside `create_or_update_card_from_alignment`
can write parse-risk audit records for specific document input risks, but the
route does not create alignment-run audit events.

## Repeated Requests

The route has no idempotency key. Repeating the same async direct-term request
creates another `AlignmentRun` and another `BackgroundJob`. Sync direct requests
can update the same `TerminologyCard` through the legacy normalized term lookup.

## Complexity Metrics

| Metric | Value |
|---|---:|
| Handler lines including decorator | 160 |
| Direct legacy model classes in handler | 5 (`AlignmentRun`, `BackgroundJob` via helper, `Document`, `DocumentChunk`, `Course`) |
| Direct helper/service calls | 12+ |
| Return shapes | 3 success shapes plus multiple error shapes |
| Commit points in handler | 3 |
| Explicit rollback points in handler | 0 |
| Provider execution points | indirect through `generate_alignment_result` and `run_alignment_for_chunks` |
| Credential read points | indirect through provider selection globals/env |
| Formal policy points | 0 |
| Formal preflight points | 0 |
| Formal parser points | 0 |
| `AlignmentVerificationRun` writes | 0 |
| Legacy card mutation points | sync direct and sync document |

## Main Conclusion

`DEPRECATE_LEGACY_ALIGNMENT_RUN_FIRST`

Rationale:

- the frontend still calls the route, so immediate deletion would break the UI;
- the route writes a legacy data model and has three response shapes;
- it bypasses formal provider policy, provider usage, audit, request-id, parser,
  and attach gates;
- it can reach live provider transport intent if legacy provider configuration
  is made live;
- directly extracting it as a service would preserve a weaker duplicate
  execution path beside the formal verification API.

## Next Step

Create a deprecation and compatibility policy before any extraction:

1. decide whether frontend document alignment should continue using the legacy
   async `AlignmentRun`/`BackgroundJob` flow or move to a safer replacement;
2. if retained temporarily, disable or gate sync execution and legacy live
   transport separately;
3. define a compatibility response for clients before changing the route;
4. only after that decide whether remaining read-only `/api/alignment/runs*`
   routes should be extracted or replaced.

Do not move the current handler into a service unchanged.
