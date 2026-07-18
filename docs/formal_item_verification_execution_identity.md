# Formal Item Verification Execution Identity

Status: `FORMAL_ITEM_EXECUTION_IDEMPOTENCY_SCHEMA_ESTABLISHED`

Scope: SQLite local/small-pilot schema foundation only. The verification
adapter, provider execution, worker, routes, and frontend are not implemented
by this boundary.

## Identity Semantics

`build_formal_item_verification_input_fingerprint(...)` hashes stable JSON
using UTF-8, sorted keys, fixed separators, and SHA-256. Its inputs are formal
workflow/item identity, item key, normalized term and Chinese candidate
values, candidate provenance references, bilingual evidence reference IDs,
source/version/scope, and retrieval version. It rejects structured evidence
objects and never accepts evidence bodies, chunk text, prompt bodies, provider
output, credentials, request IDs, worker IDs, attempts, lease tokens,
timestamps, or random IDs.

`build_formal_item_verification_execution_key(...)` produces:

```text
item-verification-execution-v1:<sha256>
```

The digest adds workflow, provider, model, retrieval, prompt, parser, and
output-schema versions to the safe input fingerprint. The same logical input
and versions produce the same key; a material identity field change produces
a different key.

Audit event identity is separately versioned as
`item-audit-event-v1:<sha256>` over execution key and event type. It is not an
audit UID, request ID, or timestamp.

## Persistence Schema

`DocumentAlignmentItemVerificationExecution` maps one logical execution to
workflow run/item identity and optional draft, preflight, and verification
UIDs. Its table is
`document_alignment_item_verification_executions`.

Recovery statuses are `prepared`, `draft_ready`, `preflight_passed`,
`preflight_blocked`, `provider_started`, `provider_completed`,
`verification_persisted`, `attach_pending`, `attached`, `needs_review`,
`blocked`, and `failed`. Approval, publication, and student visibility are not
execution states.

Database identities:

| Record | Nullable identity | Database rule |
|---|---|---|
| execution mapping | `execution_key` | unique, non-null |
| execution mapping | `preflight_run_uid` | unique when non-null |
| execution mapping | `verification_run_uid` | unique when non-null |
| `AlignmentVerificationRun` | `execution_key` | unique when non-null |
| `AlignmentProviderPreflightRun` | `execution_key` | unique when non-null |
| `AlignmentProviderUsageRecord` | `execution_key` | unique when non-null |
| `AuditRecord` | `event_identity` | unique when non-null |

`draft_card_uid` is intentionally not unique: multiple workflow items may
legitimately reference one protected approved card. The future adapter must
never overwrite or downgrade that card.

## Legacy Compatibility And Upgrade

Existing verification, preflight, usage, and audit rows retain `NULL` in the
new identity columns. No historical identity is guessed and no row is deleted
or rewritten. SQLite permits multiple legacy `NULL` values while rejecting a
duplicate non-null identity.

The local upgrade is additive: `db.create_all()` creates the new table and the
existing SQLite helper adds nullable columns and named unique indexes. Running
the upgrade repeatedly is supported. Conflicting non-null data causes an
explicit unique-index failure; it is never repaired automatically.

This remains:

```text
PILOT_CREATE_ALL_ONLY
FORMAL_MIGRATION_REQUIRED_BEFORE_PRODUCTION
POSTGRESQL_IDEMPOTENCY_CONSTRAINTS_NOT_VERIFIED
```

## Retry Mapping And Non-Guarantees

The future adapter must create or load the execution mapping before side
effects, use `execution_key` for verification/preflight/usage recovery, and
use `event_identity` for bounded logical audit events. Active BackgroundJob
lease fencing must guard every business write.

This schema does not provide provider exactly-once semantics. In particular,
a provider success followed by process or database failure still requires an
explicit recovery policy. It also does not implement card creation, preflight,
verification, attach, usage, audit, worker dispatch, or HTTP behavior.
