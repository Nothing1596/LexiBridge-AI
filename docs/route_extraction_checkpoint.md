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
