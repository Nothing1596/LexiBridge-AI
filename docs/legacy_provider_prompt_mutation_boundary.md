# Legacy Provider Prompt Mutation Boundary

Task: 9C.4O
Baseline commit: `6aabc47b3c9be79c7ea0e33efc6b2b52c1856878`
Branch: `audit/legacy-provider-prompt-mutation-9c4o`
Status: characterization and boundary audit only. No production route, service, schema, frontend, or OpenAPI behavior was changed.

## Scope

This audit covers only:

- `POST /api/admin/ai/prompts`

It does not migrate the route, extract a service, modify the shared prompt route module, or touch legacy `/api/alignment/run`.

## Registration Contract

`GET /api/admin/ai/prompts` and `POST /api/admin/ai/prompts` are registered as a single Flask rule by `backend/routes/legacy_provider_admin_configuration.py`:

- URL: `/api/admin/ai/prompts`
- Methods: `GET`, `POST`
- Flask endpoint: `admin_ai_prompts`
- Registration function: `register_legacy_provider_admin_configuration_routes(...)`
- GET handler: local `admin_ai_prompts()` function in the configuration route module
- POST handler: delegated to the explicit `prompt_post_handler(user)` callback
- Callback implementation: `backend/app.py::admin_ai_prompts_post_handler(user)`

`backend/app.py` no longer has an `@app.route("/api/admin/ai/prompts")` decorator. It still defines the POST mutation callback and passes it to the configuration route module to preserve the shared endpoint name.

## HTTP Contract

| Field | Current behavior |
|---|---|
| URL | `/api/admin/ai/prompts` |
| Method | `POST` |
| Endpoint | `admin_ai_prompts` |
| Auth | required |
| Roles | admin only |
| Unauthenticated | 401 |
| Student/teacher/reviewer | 403 |
| Success | 200 |
| Success envelope | `status`, `message`, `data` |
| Success `request_id` | absent |
| AuditRecord | none |
| Required by implementation | `prompt_key`, `prompt_version` |
| Required by OpenAPI | `prompt_key`, `prompt_version`, `task_type`, `template_text` |
| Empty JSON object | 400 `VALIDATION_ERROR` |
| Malformed JSON | 400 |
| Empty non-JSON body | 415 |
| Non-object JSON | currently reaches a 500 error path |
| Unknown fields | ignored |
| Network/transport | none |

The OpenAPI required field list is stricter than the implementation. The implementation accepts `task_type` and `template_text` as optional because it falls back to existing values or defaults.

## Handler Location And Complexity

Callback: `backend/app.py::admin_ai_prompts_post_handler(user)`.

Current callback size: 22 lines.

Direct model access:

- `PromptTemplate`

Direct helper/service calls:

- `request.get_json()`
- `api_error(...)`
- `PromptTemplate.query.filter_by(...)`
- `current_time_text()`
- `safe_json_loads(...)`
- `json.dumps(...)`
- `db.session.add(...)`
- `db.session.commit()`
- `api_success(...)`
- `serialize_prompt_template(...)`

The callback contains one explicit commit and no explicit rollback.

## Mutation Operation Matrix

| Operation | How selected | Required fields | Target lookup | Rows created | Rows updated | Commit | Response |
|---|---|---|---|---:|---:|---:|---|
| Upsert prompt template version | no action field; lookup by `prompt_key` + `prompt_version` | implementation requires `prompt_key`, `prompt_version` | first `PromptTemplate` with matching key/version | 1 if absent | 1 if present | yes | serialized prompt without `template_text` |

No separate create, update, activate, deactivate, set-default, reset, archive, or create-version operation exists in the current HTTP contract. `is_active` and `is_default` are direct field assignments on the target prompt row.

## Prompt Model

Current model: `PromptTemplate`.

Fields:

- `id`
- `prompt_key`
- `prompt_version`
- `task_type`
- `language`
- `template_text`
- `json_schema`
- `is_active`
- `is_default`
- `created_by`
- `created_at`
- `updated_at`
- `notes`

Observed model properties:

- No provider relation.
- No model relation.
- No course relation.
- No version history table.
- No explicit uniqueness constraint on `prompt_key` + `prompt_version`.
- No optimistic locking field.
- No seed-row immutability marker.

The effective natural key is `prompt_key` + `prompt_version`, enforced by lookup-before-create rather than a database constraint.

## Validation

Current validation is route-callback local and minimal:

- `prompt_key` is stringified, stripped, and required.
- `prompt_version` is stringified, stripped, and required.
- JSON `null` is stringified to `"None"` and accepted for `prompt_key` or `prompt_version`; this is a legacy runtime quirk, not a recommended production validation rule.
- `task_type` is stringified and stripped; fallback is existing `task_type` or `prompt_key`.
- `language` is stringified and stripped; fallback is existing `language` or `bilingual`.
- `template_text` is stringified and stripped; fallback is existing template text or empty string.
- `json_schema` stores JSON text for dict/list values and stringifies other values.
- `is_active` and `is_default` use Python `bool(...)` coercion.
- `notes` is stringified and stripped.
- Unknown fields are ignored.

There is no current server-side validation for:

- maximum template length;
- placeholder syntax;
- JSON schema shape beyond dict/list/string storage behavior;
- duplicate prompt versions under concurrent writes;
- one-active or one-default policy;
- seed prompt immutability;
- no-op update detection;
- client/server version conflict.

## Legal Template Versus Secret Boundary

Prompt template content is legitimate business data. Current mutation saves `template_text` exactly as the stripped template body and does not treat normal instruction text as a secret.

Secret-like data must be distinguished from legitimate template content. Characterization uses `LEXIBRIDGE_SENTINEL_SECRET_9C4O` only in unknown credential-like fields such as API-key or authorization metadata, not as the prompt body itself.

Current behavior:

- unknown credential-like fields are ignored;
- unknown sentinel metadata is not persisted to `PromptTemplate`;
- the success response does not include unknown fields;
- `serialize_prompt_template(...)` does not return `template_text`;
- no `AuditRecord` is written.

## Versioning

Current version semantics:

- The client supplies `prompt_version`.
- The server does not call `model_version_factory`.
- A missing `prompt_key` + `prompt_version` creates a new row.
- An existing `prompt_key` + `prompt_version` is updated in place.
- Updating a version does not create a historical version.
- Repeating the same key/version request does not create a second row in normal single-session execution.
- Different versions for the same key can coexist as separate rows.
- Version ordering is not enforced by POST.
- GET orders prompts by `prompt_key.asc(), id.desc()`.

There is no optimistic locking, server-generated version, or conflict response for stale edits.

## Active And Default Rules

Current rules:

- `is_active` is assigned directly on the target row.
- `is_default` is assigned directly on the target row.
- Setting a new default does not unset existing defaults.
- Setting a new active prompt does not deactivate older prompt rows.
- Multiple prompts can be active.
- Multiple prompts can be default.

This preserves legacy behavior but leaves product policy undefined.

## Seed Behavior

The shared configuration route runs the registry seed before delegating POST to the app callback:

1. Admin auth succeeds.
2. `ensure_legacy_provider_registry_seed(...)` is called by the route module.
3. Missing provider/model/prompt defaults may be added and flushed.
4. `prompt_post_handler(user)` performs the prompt upsert.
5. The callback commits.

The seed service does not own commit or rollback. A successful prompt mutation commit can also persist missing seed rows flushed earlier in the same request.

## Transaction Matrix

| Path | Seed flush | Prompt create/update | Commit | Explicit rollback | Persistence |
|---|---:|---:|---:|---:|---|
| unauthorized | no | no | no | no | none |
| non-admin | no | no | no | no | none |
| malformed JSON | possible after admin auth | no | no | no | uncommitted seed cleanup remains owned by request/session lifecycle |
| empty JSON object | possible after admin auth | no | no | no | uncommitted seed cleanup remains owned by request/session lifecycle |
| non-object JSON | possible after admin auth | no stable mutation | no | no | current error path returns 500 under no-propagation testing |
| create | yes | create one `PromptTemplate` if missing | yes | no | seed plus prompt can persist |
| update same key/version | yes | update existing `PromptTemplate` in place | yes | no | seed plus prompt update can persist |
| commit failure | yes | pending prompt mutation may exist in session | attempted | no | no handler-level rollback; caller/test must recover scoped session |

The absence of explicit rollback is current legacy behavior and must not be copied into future service design without deliberate policy.

## Write-set

Successful mutation can write:

- missing `AIProviderConfig` seed rows;
- missing `AIModelRegistry` seed rows;
- missing `PromptTemplate` seed rows;
- target `PromptTemplate` row.

Successful mutation does not write:

- `AICallLog`;
- `AlignmentProviderUsageRecord`;
- `AlignmentVerificationRun`;
- `AlignmentProviderPreflightRun`;
- `AlignmentProviderPolicy`;
- `ConceptAlignmentCard`;
- `AuditRecord`.

## Permissions And Actor

The route is admin-only.

Denied users do not trigger seed and do not write prompt rows:

- unauthenticated: 401;
- student: 403;
- teacher: 403;
- reviewer: 403;
- admin: allowed.

For a newly created prompt, `created_by` is set to the current admin user id if it was previously empty. Existing `created_by` is preserved.

## Audit And Logging

No prompt mutation `AuditRecord` is written by the current implementation.

The current response does not include full prompt template text, full request JSON, unknown credential-like fields, traceback, Authorization, Cookie, or API key fields.

## Frontend Dependency

`frontend/index.html` currently calls only:

- `GET /api/admin/ai/prompts`

No direct frontend `POST /api/admin/ai/prompts` call was found in the current single-file frontend. The POST route remains in OpenAPI and tests, so it is still part of the compatibility surface.

## OpenAPI

`docs/openapi.yaml` lists `POST /api/admin/ai/prompts` as "Create or update an AI prompt template".

OpenAPI currently marks these fields as required:

- `prompt_key`
- `prompt_version`
- `task_type`
- `template_text`

Production code only requires:

- `prompt_key`
- `prompt_version`

This is an existing mismatch. Task 9C.4O records it but does not change OpenAPI or production behavior.

## No-network And Secret Safety

Characterization tests block:

- `socket`;
- `urllib`;
- `requests`;
- `httpx`.

Static checks confirm the mutation callback does not call provider adapter, provider transport, legacy healthcheck executor, or provider selection execution. The route does not use real LLMs.

Sentinel: `LEXIBRIDGE_SENTINEL_SECRET_9C4O`.

The sentinel is not returned in API responses and is not persisted when supplied in unknown credential-like metadata fields.

## Concurrency And Consistency Risks

Current risks:

- Two admins can update the same prompt version with last-write-wins behavior.
- Two sessions can concurrently create the same `prompt_key` + `prompt_version` because no explicit database uniqueness constraint is present.
- Duplicate default prompts can exist.
- Duplicate active prompts can exist.
- There is no optimistic locking or version precondition.
- Seed lookup-before-create has the same race profile documented for the seed service.
- Commit failure has no local rollback in the callback.

These risks do not block characterization, but they do block treating this as a simple route-move task.

## Future Boundary Split

Future work should separate:

| Boundary | Responsibility |
|---|---|
| HTTP adapter | auth, JSON parsing, legacy response envelope |
| Prompt validation | required fields, data coercion, JSON schema/template validation |
| Prompt version/default policy | create/update/version semantics, active/default exclusivity if required |
| Prompt mutation service | seed integration, lookup, mutation plan, persistence orchestration |
| Transaction owner | explicit commit/rollback behavior |
| Response mapping | legacy envelope and serializer compatibility |

## Task 9C.4P Policy Decision

Task 9C.4P accepts `docs/adr/ADR-legacy-prompt-mutation-policy.md` as the compatibility policy for the current small pilot.

Policy name: `LEGACY_PROMPT_MUTABLE_REVISION_V1`.

Status: `ACCEPTED_FOR_SMALL_PILOT`.

The policy explicitly treats `POST /api/admin/ai/prompts` as a legacy mutable revision upsert, not as production-grade immutable prompt version control.

## Compatibility Policy Matrix

| Concern | Current compatibility policy | Future production policy |
|---|---|---|
| Identity | `(prompt_key, prompt_version)` after runtime stringification and stripping. Matching is case-sensitive. Provider, model, task type, language, active, and default are not part of identity. | Formalize identity in migration-backed schema, likely with a unique constraint or dedicated prompt identity/version tables. |
| Version mutability | `LEGACY_MUTABLE_REVISION`: the client supplies an opaque non-empty `prompt_version`; same key/version can be updated in place. | Immutable versions or explicit revision records, with content changes requiring a new version or an explicit revision operation. |
| Upsert | Missing key/version creates one `PromptTemplate`; existing key/version updates the first matching row in place. | Separate create/update/new-version operations with explicit conflict behavior. |
| History | No immutable history is generated; overwritten content is not queryable through this endpoint. | Historical version query semantics and retained immutable revision rows. |
| Duplicate prevention | Sequential repeated requests should not create a second row, but true concurrent creation is not protected by schema. Existing duplicate logical rows are resolved by the current first-row lookup behavior. | `unique(prompt_key, prompt_version)` or equivalent conflict-safe identity enforcement. |
| Concurrency | `SINGLE_WRITER_LAST_COMMIT_WINS`; operationally assumes one admin editor in the small pilot. | Multi-admin concurrency policy with row-version tokens, ETag/If-Match, or equivalent optimistic locking. |
| Lost update | Lost updates are possible; the last successful commit determines stored content. | Detect stale writes and return a conflict response such as HTTP 409. |
| Active/default | Direct row assignment is preserved if fields are supplied. Active/default exclusivity, archive, activate, and deactivate workflows are out of scope. | Define active/default product semantics and enforce with constraints or transactional updates if required. |
| Validation | Runtime compatibility source: `prompt_key` and `prompt_version` are required; other fields follow current fallback/coercion behavior; unknown fields are ignored. | Versioned API contract with stricter validation, length limits, schema validation, and documented error codes. |
| OpenAPI | Runtime contract wins for compatibility. OpenAPI currently overstates required fields by requiring `task_type` and `template_text`; this task does not change OpenAPI. | Align OpenAPI with the chosen production API in a separate contract task. |
| Transaction | Current callback owns one direct commit. Next service must own the transaction instead of the route. | Application service with explicit transaction boundaries and well-defined retry/conflict behavior. |
| Rollback | Current callback has no explicit rollback. Next service must add explicit rollback while preserving external success/error contracts. | Standardized rollback and error mapping across mutation services. |
| Audit | No `AuditRecord` is written today. | Add safe prompt mutation audit events only through a separate audit contract task. |
| Migration | No schema change; SQLite/additive migration limitations remain. | Formal migration framework before adding uniqueness, immutable history, locking tokens, or active/default constraints. |

## Service Extraction Input

The next safe implementation task is `Task 9C.4Q: Legacy Prompt Mutation Application Service`.

That service should implement:

1. registry seed through the existing seed service;
2. runtime-compatible validation for `prompt_key` and `prompt_version`;
3. lookup by `(prompt_key, prompt_version)`;
4. mutable revision create/update;
5. exactly one commit on success;
6. explicit rollback on failure;
7. a typed result that lets the route preserve the legacy envelope.

It must not implement immutable versions, unique constraints, OpenAPI-only required fields, active/default exclusivity, prompt mutation audit records, provider transport, or `/api/alignment/run` behavior.

## Final Conclusion

Task 9C.4O primary conclusion: `PROMPT_VERSIONING_OR_CONCURRENCY_POLICY_REQUIRED_FIRST`.

Task 9C.4P policy conclusion: `LEGACY_PROMPT_MUTABLE_REVISION_V1` is accepted for the current local/small-pilot compatibility surface.

Reasoning:

- The current operation is an upsert, not a fully specified create/update/version workflow.
- Versioning is client-supplied and updates are in-place.
- Default and active flags are not globally managed.
- No uniqueness or optimistic locking policy is present for prompt key/version updates.
- Commit failure has no handler-level rollback.
- OpenAPI required fields are stricter than the actual implementation.

The next safe step is not route extraction. The next task should extract an application service that implements the accepted mutable-revision policy exactly, including explicit rollback, without adding production-only versioning or concurrency features.
