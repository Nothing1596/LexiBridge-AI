# Route Extraction Checkpoint

Updated: 2026-07-15

This document records the real repository state at the Task 9C.3C checkpoint. It is a cumulative checkpoint for previously verified route extraction and pilot hardening work; it does not pretend that Tasks 9C.1, 9C.2, 9C.2.1, 9C.3A, and 9C.3B were committed independently.

## Git Baseline

- Pre-checkpoint commit: `09c49e2fae0a8cf4de8c1b22100d4d6d0d591bcc`
- Pre-checkpoint branch: `dev`
- Checkpoint commit: the commit containing this file; record the exact SHA with `git rev-parse HEAD` after committing. A commit cannot include its own SHA in tracked content without creating a self-reference.
- Checkpoint purpose: establish a reproducible route-refactor baseline before any provider governance route extraction.

## Working Tree Inventory

Task 9C.3C generated `/private/tmp/lexibridge-checkpoint-inventory.json` before committing.

- Pre-stage modified tracked files at task start: 7
- Pre-stage untracked candidate files at task start: 371
- Final staged files in checkpoint inventory: 380
- Total classified files: 380
- Unknown files: 0
- Files selected for staging: 380
- Categories:
  - configuration: 10
  - documentation: 121
  - source: 126
  - frontend_asset: 2
  - tests: 121

Ignored local runtime files were not selected for staging, including `.env`, `backend/lexibridge.db`, `__pycache__`, and `.pytest_cache`.

## Historical Release Artifact

The historical `lexibridge AI/` artifact is not part of current source. It was a historical release/backup copy and is not required to build, test, run, or verify the current project.

- Original artifact manifest: 31 files, 9,850,040 bytes.
- Remaining files available at recovery time: 13 files, 9,584,911 bytes.
- Missing files cannot be restored from the current environment.
- Remaining content has been preserved outside the Git repository at:
  `$HOME/Documents/LexiBridge-AI-Archives/route-refactor-pre-checkpoint-20260714-INCOMPLETE`
- Archive status: `INCOMPLETE_SOURCE_ARCHIVED_FOR_PRESERVATION_ONLY`.
- The archive, manifests, zip files, databases, temporary files, and release copies must not be committed.
- The durable archive gate accepts this incomplete historical archive because the current effective source tree has no dependency on it.

## Route Layer Snapshot

- `backend/app.py` line count: 16,475
- Direct `@app.route` handlers remaining in `backend/app.py`: 147
- Extracted route modules: 4
- Extracted routes: 15
- `RouteCoreDependencies` fields: 9
- Circular imports detected by tests: no
- Duplicate endpoints detected by tests: no

## Extracted Route Modules

| Module | Routes | Register function | Register parameter count | Domain model fields |
|---|---:|---|---:|---:|
| `backend/routes/teacher_learning_analytics.py` | 3 | `register_teacher_learning_analytics_routes(app, *, core, models)` | 3 | 6 |
| `backend/routes/student_concept_cards.py` | 5 | `register_student_concept_card_routes(app, *, core, models, student_visible_course_names, student_course_access_service, record_student_course_access_audit)` | 6 | 5 |
| `backend/routes/concept_card_review.py` | 4 | `register_concept_card_review_routes(app, *, core, models)` | 3 | 6 |
| `backend/routes/concept_card_feedback.py` | 3 | `register_concept_card_feedback_routes(app, *, core, models)` | 3 | 6 |

All four modules use explicit `app.add_url_rule` registration to preserve existing URL, method, endpoint, request/response, audit, permission, visibility, review-policy, triage, and export contracts. Blueprint migration and app factory work remain deferred.

## RouteCoreDependencies Boundary

`backend/routes/shared.py` contains the shared route foundation. `RouteCoreDependencies` currently carries:

- `db`
- `audit_record_model`
- `audit_record_service`
- `current_time_text`
- `require_current_user`
- `get_route_audit_context`
- `attach_request_id_to_response`
- `api_success_with_audit_context`
- `api_error_with_audit_context`

It must remain limited to cross-domain route infrastructure. It must not grow into a service locator, include Flask `app`, store request-specific mutable state, include all models, or include domain services such as provider governance, review policy, feedback, or student card services.

## Remaining Route Domains

`backend/app.py` still owns most initialization and legacy route groups. Current direct route handler groups include:

| Domain | Approx. direct handlers | Risk | Notes |
|---|---:|---|---|
| Auth | 7 | high | Session, password reset, current-user contracts. |
| Courses and membership | 3 | medium | Course membership and legacy course routes remain coupled to app globals. |
| Upload/documents | 4 | high | File handling, parse-quality gate, knowledge source creation, audit. |
| Knowledge governance | 20 | high | Source/chunk/version lifecycle and indexing/rebuild helpers. |
| Alignment/provider governance | 14 | high | Provider policy, preflight, attach gates, no-network boundary. |
| Student progress/course routes | 5 | medium | Student progress and membership administration routes remain in app.py. |
| Remaining Concept Card/admin/review-policy routes | 6 | high | Draft/admin status and policy management routes remain. |
| Evidence/retrieval/search | 2 | medium | Evidence retrieval and bilingual evidence routes remain. |
| Jobs/storage/health | 6 | medium | Operational routes and worker controls remain. |
| Legacy term/glossary/feedback/pilot | 22 | medium | Legacy compatibility surface remains. |
| Other admin/evaluation/retrieval routes | 56 | high | Mixed admin, retrieval experiment, cost, audit, and production readiness routes. |

## Coupling Assessment

- Initialization order remains coupled through `backend/app.py` model declarations, migration helpers, auth helpers, audit helpers, and route registration.
- Auth/RBAC helpers are still fragmented across app-level helpers and domain services.
- Audit helpers are shared but route-specific audit payload construction still lives near route modules or legacy handlers.
- App factory and Blueprint migration should remain deferred until more route slices have contract tests and clean worktree verification.

## Next Slice Recommendation

Provider governance and preflight routes are a reasonable next route-extraction slice only after this checkpoint is committed and reproduced from a clean worktree. That slice must preserve provider policy gates, disabled external provider behavior, no-network checks, AuditRecord behavior, and OpenAPI parity.

Do not begin provider governance extraction from an uncommitted or unreproducible working tree.

## Task 9C.4A Update

Task 9C.4A extracts only read-only provider governance and preflight GET routes into `backend/routes/provider_governance.py`. It does not extract provider policy mutation, preflight execution, alignment verification execution, replay behavior, provider usage recording, credential management, or transport code.

Migrated routes:

- `GET /api/alignment/providers`
- `GET /api/alignment/providers/<provider_name>/policy`
- `GET /api/alignment/providers/<provider_name>/usage`
- `GET /api/alignment/providers/preflight/<preflight_uid>`
- `GET /api/alignment/providers/<provider_name>/preflight`

Provider routes still in `backend/app.py` after 9C.4A:

- `POST /api/alignment/providers/<provider_name>/policy`
- `POST /api/alignment/providers/<provider_name>/preflight`
- `POST /api/alignment/verify`
- `GET /api/admin/alignment-runs`
- `GET /api/admin/ai/providers`
- other legacy AI provider registry/health endpoints outside the alignment-provider governance group

Post-extraction route snapshot:

- `backend/app.py` line count: 16,385
- Direct `@app.route` handlers remaining in `backend/app.py`: 142
- Extracted route modules: 5
- Extracted routes: 20
- `RouteCoreDependencies` fields: 9
- `register_provider_governance_routes(app, *, core, models)` register parameter count: 3
- `ProviderGovernanceModels` fields: 3

The provider governance route module keeps provider services domain-specific and outside `RouteCoreDependencies`. Its GET handlers are local read paths: they query registry/policy/usage/preflight history and do not run transport, create verification runs, write provider usage, mutate policy, enable external providers, or call external networks.

Next provider slices should be decided from the remaining route list. Reasonable candidates are provider policy mutation or preflight execution, but real provider transport and external calls must remain disabled unless a later task explicitly changes that boundary with tests.

## Task 9C.4B Update

Task 9C.4B extracts only provider policy mutation into `backend/routes/provider_policy.py`. It does not extract provider preflight execution, alignment verification execution, replay behavior, provider usage recording, credential management, environment mutation, or transport code.

Migrated route:

- `POST /api/alignment/providers/<provider_name>/policy`

Provider routes still in `backend/app.py` after 9C.4B:

- `POST /api/alignment/providers/<provider_name>/preflight`
- `POST /api/alignment/verify`
- `GET /api/admin/alignment-runs`
- `GET /api/admin/ai/providers`
- other legacy AI provider registry/health endpoints outside the alignment-provider governance group

Post-extraction route snapshot:

- `backend/app.py` line count: 16,366
- Direct `@app.route` handlers remaining in `backend/app.py`: 141
- Extracted route modules: 6
- Extracted routes: 21
- `RouteCoreDependencies` fields: 9
- `register_provider_policy_routes(app, *, core, models, record_provider_governance_audit)` register parameter count: 4
- `ProviderPolicyModels` fields: 1

The provider policy route module keeps provider policy persistence in `services/provider_governance.py` and keeps the existing provider governance audit adapter explicit. Its POST handler writes only provider policy data and does not run transport, create verification runs, write provider usage, execute preflight, manage credentials, enable real external providers, or call external networks.

The next provider slice should be selected from the remaining route list. Provider preflight execution is the next reasonable candidate, but it should remain separate from alignment verification execution because those paths have different state and audit semantics.

## Task 9C.4C Update

Task 9C.4C extracts only provider preflight execution into `backend/routes/provider_preflight.py`. It does not extract alignment verification execution, provider usage writes, replay execution, credential management, environment mutation, or transport code.

Migrated route:

- `POST /api/alignment/providers/<provider_name>/preflight`

Provider routes still in `backend/app.py` after 9C.4C:

- `POST /api/alignment/verify`
- `GET /api/admin/alignment-runs`
- `GET /api/admin/ai/providers`
- other legacy AI provider registry/health endpoints outside the alignment-provider governance group

Post-extraction route snapshot:

- `backend/app.py` line count: 16,330
- Direct `@app.route` handlers remaining in `backend/app.py`: 140
- Extracted route modules: 7
- Extracted routes: 22
- `RouteCoreDependencies` fields: 9
- `register_provider_preflight_routes(app, *, core, models, record_provider_preflight_audit)` register parameter count: 4
- `ProviderPreflightModels` fields: 2

The provider preflight route module keeps preflight readiness logic in `services/provider_preflight.py` and keeps the existing provider preflight audit adapter explicit. Its POST handler creates only `AlignmentProviderPreflightRun` records and audit records, does not run transport, does not create alignment verification runs, does not write provider usage, does not mutate provider policy, does not manage credentials, and does not call external networks.

The next provider slice should not begin by moving `/api/alignment/verify`. First scan the verification route's state machine, provider usage writes, fake/replay provider behavior, result parsing, attach-to-card gate, audit semantics, and no-network/external-provider gates before deciding the next extraction boundary.

## Task 9C.4D Update

Task 9C.4D does not extract a route. It adds characterization coverage and documents the boundary of `POST /api/alignment/verify` in `docs/alignment_verification_route_boundary.md`.

Current verification route snapshot:

- Route: `POST /api/alignment/verify`
- Endpoint: `verify_alignment_api`
- Handler location: `backend/app.py:12059` through `backend/app.py:12339`
- Handler size: 281 lines including decorator and blanks
- Direct model dependencies: 4 (`ConceptAlignmentCard`, `AlignmentProviderPolicy`, `AlignmentProviderUsageRecord`, `AlignmentVerificationRun`)
- Main write tables: `alignment_verification_run`, `alignment_provider_usage_record`, optional `concept_alignment_card`, and `audit_record`
- Provider modes characterized: `mock-rule-v1`, `fake-llm-v1`, `external-llm-replay-v1`, `deepseek-alignment-v1-disabled`
- Verification route conclusion: `SERVICE_BOUNDARY_REQUIRED_FIRST`

The route handler still owns too much execution orchestration for direct movement into a route module. It sequences initial audit, provider existence checks, card-vs-payload input construction, provider governance, policy-block run creation, provider execution, provider usage recording, optional card attach, completion/failed audit, and rollback behavior. The next step should create or extend a domain service that owns this transaction and returns the existing response contract; only after that service boundary is frozen should route extraction proceed.

Post-9C.4D route snapshot remains:

- `backend/app.py` line count: 16,330
- Direct `@app.route` handlers remaining in `backend/app.py`: 140
- Extracted route modules: 7
- Extracted routes: 22
- `RouteCoreDependencies` fields: 9

Provider routes still in `backend/app.py` after 9C.4D:

- `POST /api/alignment/verify`
- `GET /api/admin/alignment-runs`
- `GET /api/admin/ai/providers`
- other legacy AI provider registry/health endpoints outside the alignment-provider governance group

## Task 9C.4D.1 Update

Task 9C.4D.1 does not extract `POST /api/alignment/verify` into a route module. It creates an application-layer execution service boundary:

- Service module: `backend/services/alignment_verification_execution.py`
- Public entry point: `execute_alignment_verification(...)`
- Request DTO: `AlignmentVerificationExecutionRequest`
- Actor DTO: `AlignmentVerificationActor`
- Context DTO: `AlignmentVerificationExecutionContext`
- Dependency object: `AlignmentVerificationExecutionDependencies`
- Result DTO: `AlignmentVerificationExecutionResult`

The service owns provider existence checks, card-vs-payload input branching, provider governance, `AlignmentVerificationRun`, `AlignmentProviderUsageRecord`, mock/fake/replay/disabled provider dispatch, output parsing through existing services, optional card attach, audit sequencing, and business transaction commit/rollback. It does not import Flask, `backend.app`, route modules, credential resolvers, provider clients, or external transport.

`verify_alignment_api` remains registered in `backend/app.py` with the same URL, method, and endpoint name. It is now a thin HTTP adapter that handles auth, request parsing, request ID/audit context, DTO construction, service invocation, and response mapping.

Post-9C.4D.1 snapshot:

- `backend/app.py` line count: 16,133
- `verify_alignment_api` adapter size: 35 lines including decorator and blanks
- Direct `@app.route` handlers remaining in `backend/app.py`: 140
- Extracted route modules: 7
- Extracted routes: 22
- RouteCoreDependencies fields: 9
- Alignment verification execution service dataclasses: 5

The next safe slice is to move only the thin `/api/alignment/verify` route adapter into a route module. That task must not move or rewrite the execution state machine, usage semantics, attach gate, audit events, or transaction behavior.

## Task 9C.4E Update

Task 9C.4E extracts only the already-thin `POST /api/alignment/verify` HTTP adapter into `backend/routes/alignment_verification.py`.

- New route module: `backend/routes/alignment_verification.py`
- Route count: 1
- Registered route: `POST /api/alignment/verify`
- Flask endpoint: `verify_alignment_api`
- Register signature: `register_alignment_verification_routes(app, *, core, execution_dependencies, execute_fn=execute_alignment_verification)`
- Execution dependency boundary: `AlignmentVerificationExecutionDependencies` remains an explicit verification-domain dependency and is not added to `RouteCoreDependencies`.
- Execution service API: unchanged.
- Business owner: `backend/services/alignment_verification_execution.py`

The route module owns only auth, request parsing with the existing `silent=True` behavior, request ID/audit context, DTO construction, execution service invocation, and response mapping. It does not access `AlignmentVerificationRun`, `AlignmentProviderUsageRecord`, `AlignmentProviderPolicy`, provider transport, credentials, parser internals, card attach logic, or business commit/rollback.

Post-9C.4E snapshot:

- `backend/app.py` line count: 16,075
- Direct `@app.route` handlers remaining in `backend/app.py`: 139
- Extracted route modules: 8
- Extracted routes: 23
- RouteCoreDependencies fields: 9

Remaining provider/admin-adjacent route domains include admin alignment run listing, legacy AI provider/admin views, upload/knowledge/evidence routes, course and policy management routes, and other legacy app routes. The next provider-related slice should be selected from the remaining route inventory and must not re-open external provider execution unless a separate task explicitly hardens that path.

## Task 9C.4F Update

Task 9C.4F does not extract any route. It adds `docs/provider_admin_route_inventory.md` and characterization coverage for the remaining provider/admin-adjacent routes in `backend/app.py`.

Characterized remaining provider/admin routes:

- `GET /api/admin/alignment-runs`
- `GET /api/admin/ai/providers`
- `GET /api/admin/ai/models`
- `GET, POST /api/admin/ai/prompts`
- `GET /api/admin/ai/calls`
- `GET /api/admin/ai/usage`
- `GET /api/admin/ai/health`
- `POST /api/admin/ai/healthcheck`
- `POST /api/alignment/run`
- `GET /api/alignment/runs`
- `GET /api/alignment/runs/<int:run_id>`

Inventory result:

- Unknown provider/admin route count: 0
- `GET /api/admin/alignment-runs`: `READ_ONLY_ADMIN_LISTING`, direct extraction safe
- legacy `/api/admin/ai/*`: active frontend/OpenAPI surface, overlaps formal provider governance but is not an alias; requires deprecation/compatibility or service-boundary work before extraction
- `POST /api/admin/ai/healthcheck`: `HEALTH_EXTERNAL_RISK` because live provider mode plus `live_probe=true` can call provider transport
- `POST /api/alignment/run`: `SERVICE_BOUNDARY_REQUIRED` because it creates legacy `AlignmentRun`, background jobs/cards, usage, and commits
- legacy `/api/alignment/runs*`: active frontend/OpenAPI read paths tied to the older `AlignmentRun` surface

Post-9C.4F snapshot:

- `backend/app.py` line count: 16,075
- Direct `@app.route` handlers remaining in `backend/app.py`: 139
- Extracted route modules: 8
- Extracted routes: 23
- `RouteCoreDependencies` fields: 9

Primary next-slice conclusion: `GO_ADMIN_ALIGNMENT_RUNS_EXTRACTION`.

The next route extraction should be limited to `GET /api/admin/alignment-runs`. It must not include legacy `/api/admin/ai/*`, `/api/alignment/run`, `/api/alignment/runs`, provider healthcheck, prompt mutation, or external provider transport. Legacy provider admin routes need a separate compatibility/deprecation audit before they are moved.
