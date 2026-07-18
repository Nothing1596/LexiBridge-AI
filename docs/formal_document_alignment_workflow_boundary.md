# Formal Document Alignment Workflow Boundary

Status:
- `CONTRACT_PROPOSED`
- `PROPOSED_FOR_SMALL_PILOT`
- `LEGACY_REPLACEMENT_NOT_IMPLEMENTED`
- `FORMAL_WORKFLOW_MODELS_REQUIRED_FIRST`

Task: 9C.4V
Baseline: `aa20eef49b260f8c70beed754f091f3263c4cfb2`
Workflow: `FORMAL_DOCUMENT_ALIGNMENT_ORCHESTRATION`
Canonical input: `GOVERNED_KNOWLEDGE_SOURCE`
Execution model: `ASYNC_JOB_ORCHESTRATION`
Data policy: `NO_LEGACY_AND_FORMAL_DUAL_WRITE`

This document defines the formal document-alignment workflow contract. It does
not implement routes, services, models, frontend changes, OpenAPI changes, or
database schema. Legacy `POST /api/alignment/run` remains temporary frontend
compatibility with external execution disabled.

## Component Matrix

| Component | Existing artifact | Reuse policy | Writes | Transaction owner |
|---|---|---|---|---|
| Document parse quality | `DocumentParseRecord`, `DocumentParseBlock`, `services/document_parse_quality.py` | reuse parse and quality gate | parse records and audit during ingestion | existing parse/ingestion owners |
| Governed source | `KnowledgeSource`, `KnowledgeChunk`, `services/knowledge_ingestion.py` | canonical input and evidence source | governed source/chunk during ingestion only | ingestion route/job |
| Evidence retrieval | `services/evidence_retrieval.py` | reuse read-only lexical retrieval | none | workflow caller |
| Bilingual evidence | `services/bilingual_evidence_workflow.py` | reuse DTO and bounded evidence package | none | workflow caller |
| Chinese candidates | `services/chinese_term_candidates.py` | reuse deterministic candidate extraction | none | workflow caller |
| Draft card | `services/concept_card_drafts.py`, `ConceptAlignmentCard` | reuse safe `needs_review` draft creation | formal draft card and audit | draft service or workflow item transaction |
| Verification | `services/alignment_verification_execution.py`, `AlignmentVerificationRun` | reuse formal provider governance and parser path | verification run, provider usage, audit, optional attach | verification execution service |
| Provider governance | `services/provider_governance.py`, `services/provider_preflight.py` | required for every provider execution | policy/preflight/usage records through formal services | formal services |
| Teacher review | `services/concept_card_review.py` | final approval owner | review record, card status, audit | review service |
| Queue transport | `BackgroundJob` | transport envelope only | job progress/events | job infrastructure |
| Workflow root | `DocumentAlignmentWorkflowRun` | missing, must be added | formal root status/progress | future workflow service |
| Workflow item | `DocumentAlignmentWorkflowItem` | missing, must be added | item state/references | future workflow service |
| Legacy run | `AlignmentRun`, `TerminologyCard`, `AICallLog`, legacy `UsageRecord` | do not reuse | legacy only while compatibility remains | legacy route/worker |

## Data Flow

```text
POST /api/document-alignment-runs
-> validate Idempotency-Key
-> validate teacher/admin permission
-> load governed KnowledgeSource
-> enforce parse/source/chunk quality gates
-> create DocumentAlignmentWorkflowRun
-> create BackgroundJob transport envelope
-> worker retrieves governed chunks
-> extract candidate concepts
-> retrieve bilingual evidence
-> generate Chinese candidate summary
-> create ConceptAlignmentCard draft
-> run formal provider policy and preflight
-> run formal alignment verification
-> persist DocumentAlignmentWorkflowItem outcome
-> aggregate workflow run status
-> teacher review
-> student sees only approved ConceptAlignmentCard
```

The workflow must not submit a full document prompt to a provider, accept
arbitrary client evidence as trusted, write legacy alignment rows, or auto
approve cards.

## State Transition Matrix

Root states:

| From | To | Trigger | Meaning |
|---|---|---|---|
| none | `queued` | start request accepted | root and BackgroundJob created |
| `queued` | `validating` | worker claimed | source and parse gates are being checked |
| `validating` | `processing` | source and chunks usable | candidate/item processing begins |
| `validating` | `blocked` | source/parse/chunk gate fails | no safe workflow output |
| `processing` | `ready_for_review` | all processable items succeeded | reviewable drafts exist with no item failures |
| `processing` | `completed_with_warnings` | some items succeeded and some blocked/failed | partial success |
| `processing` | `blocked` | all items blocked by domain gates | no reviewable output |
| `queued` | `failed` | infrastructure or persistence failure | unsafe terminal failure |
| `validating` | `failed` | infrastructure or persistence failure | unsafe terminal failure |
| `processing` | `failed` | infrastructure or persistence failure | unsafe terminal failure |

Item states:

| From | To | Trigger | Meaning |
|---|---|---|---|
| none | `candidate` | candidate selected | item identity created |
| `candidate` | `evidence_ready` | governed evidence found | evidence references are usable |
| `evidence_ready` | `draft_created` | safe draft persisted | ConceptAlignmentCard draft exists |
| `draft_created` | `verification_completed` | formal verification run completed | parser and usage/audit path completed |
| `verification_completed` | `needs_review` | output is reviewable | teacher review required |
| any nonterminal | `blocked` | policy/preflight/evidence/domain gate blocks | safe domain block |
| any nonterminal | `failed` | infrastructure/parser/persistence failure | unsafe processing failure |

No workflow state grants student visibility.

## Partial Failure

Partial success is expected. One blocked or failed concept does not fail the
whole document if at least one reviewable item is produced. A source permission
failure, parse quality block, missing governed chunks, or workflow persistence
failure can block or fail the root.

Blocked item reasons include insufficient evidence, provider policy blocked,
provider preflight blocked, no Chinese candidate, duplicate concept collision,
and verification recommendation `insufficient_evidence`.

Failed item reasons include parser failure that cannot be safely represented,
database failure, worker infrastructure failure, and unexpected internal
processing errors.

## Idempotency

The start endpoint requires `Idempotency-Key`. `request_id` is only for trace
and audit correlation and must not be used for idempotency.

Scope:

```text
user_id + knowledge_source_uid + workflow_version + Idempotency-Key
```

Rules:

| Case | Result |
|---|---|
| same key and same canonical payload | return existing run with `idempotency.reused=true` |
| same key and different canonical payload | HTTP 409 with `DOCUMENT_ALIGNMENT_IDEMPOTENCY_CONFLICT` |
| missing key | HTTP 400 with `DOCUMENT_ALIGNMENT_IDEMPOTENCY_REQUIRED` |
| worker retry | use persisted run/item state and deterministic item keys |

## Provider Governance

Provider execution is allowed only through the formal verification execution
path:

```text
provider governance
-> provider policy
-> provider preflight
-> formal alignment verification
-> formal output parser
-> AlignmentProviderUsageRecord
-> AuditRecord
```

The workflow must not call legacy provider helpers, legacy `urllib` transport,
legacy `AICallLog`, legacy `UsageRecord`, legacy provider globals, custom base
URLs, or credential-bearing compatibility config. External providers remain
disabled by default.

## Evidence And Prompt Boundary

Trusted evidence comes only from governed `KnowledgeSource` and
`KnowledgeChunk` rows. Client-submitted evidence is not trusted evidence for
the workflow.

Workflow root and item records store references, counts, safe summaries, risk
labels, and error codes. They do not store full documents, full chunks, full
prompts, raw provider output, credentials, Authorization, Cookie, or raw
exceptions.

Prompt construction remains owned by the formal verification layer.

## Card And Verification Integration

Each processable item creates or reuses a `ConceptAlignmentCard` draft in a
teacher-review state such as `needs_review`. Formal verification may attach to
that card only through the existing attach gate.

The workflow cannot:

- create approved cards;
- publish to students;
- overwrite approved cards;
- bypass teacher review;
- use verification output as an approval decision.

Student-facing APIs continue to read only approved, course-visible cards.

## Data Ownership And Write-Set

Policy: `NO_LEGACY_AND_FORMAL_DUAL_WRITE`.

Formal workflow may write:

- `DocumentAlignmentWorkflowRun`;
- `DocumentAlignmentWorkflowItem`;
- `BackgroundJob` and job events as transport;
- `ConceptAlignmentCard` drafts;
- `AlignmentVerificationRun`;
- `AlignmentProviderUsageRecord`;
- `AuditRecord`.

Formal workflow must not write:

- legacy `AlignmentRun`;
- legacy `TerminologyCard`;
- legacy `AICallLog`;
- legacy `UsageRecord`;
- legacy `/api/alignment/run` compatibility records.

Legacy `/api/alignment/run` must not write formal workflow root/item records.

## Transaction Boundaries

The workflow uses short transactions:

| Transaction | Writes | Notes |
|---|---|---|
| start | workflow root, BackgroundJob, request audit | returns HTTP 202 |
| worker claim | job claimed, root `validating` | no provider call inside transaction |
| per-item | item state, draft reference, verification reference | computation and provider calls happen outside long transactions |
| finalization | root aggregate state, completion audit | terminal status |

The existing verification execution service currently owns its own
commit/rollback. The document workflow must either call it as an isolated
per-item unit or introduce a persistence-plan boundary before orchestration
loops over many items.

## Retry

Retries must be idempotent at root and item level.

| Retry type | Allowed behavior |
|---|---|
| HTTP start retry | returns existing run or idempotency conflict |
| worker crash retry | resumes from persisted root/item state |
| item retry | may retry provider/retrieval failure if item key prevents duplicates |
| non-retryable gate | persists blocked item or blocked root |

Usage is recorded only for actual formal provider calls and must not be double
counted by worker retry.

## Permissions

| Role | Start workflow | Read workflow | See draft details | Student visible output |
|---|---:|---:|---:|---:|
| unauthenticated | no | no | no | no |
| student | no | no | no | approved cards only through student card APIs |
| reviewer | no in V1 | course review summaries only if authorized | review-relevant safe summaries | no direct draft publishing |
| teacher | own/manageable courses | own/manageable courses | yes for course | no direct student publishing |
| admin | yes | yes | yes | no direct student publishing |

Permission checks happen before run/job creation and must not leak cross-course
source existence.

## Audit, Request ID, And Usage

Formal API responses include request IDs. Required audit events:

- `document_alignment_requested`;
- `document_alignment_started`;
- `document_alignment_blocked`;
- `document_alignment_completed`;
- `document_alignment_failed`.

Audit payloads contain safe source UID, run UID, course, counts, provider/model
summary, prompt version, risk summary, and safe errors. Audit payloads do not
contain full documents, full evidence, full prompts, raw output, credentials,
Authorization, or Cookie.

Usage is written only by formal provider execution. Policy blocked, preflight
blocked, insufficient evidence, parse blocked, and local deterministic
non-provider outcomes create no provider usage.

## API Contract

Start:

```text
POST /api/document-alignment-runs
Endpoint: create_document_alignment_run
Required header: Idempotency-Key
Success status: 202
```

Request:

```json
{
  "knowledge_source_uid": "source-uid",
  "workflow_version": "formal-document-alignment-v1",
  "provider": "mock-rule-v1",
  "candidate_limit": 50
}
```

Response:

```json
{
  "status": "success",
  "request_id": "req-123",
  "data": {
    "run_uid": "document-alignment-run-uid",
    "status": "queued",
    "status_url": "/api/document-alignment-runs/document-alignment-run-uid",
    "items_url": "/api/document-alignment-runs/document-alignment-run-uid/items",
    "job_uid": "background-job-uid",
    "idempotency": {
      "reused": false
    }
  }
}
```

Status:

```text
GET /api/document-alignment-runs/{run_uid}
Endpoint: get_document_alignment_run
```

Items:

```text
GET /api/document-alignment-runs/{run_uid}/items
Endpoint: list_document_alignment_run_items
```

Items are paginated and return references and safe summaries only.

## Error Matrix

| Code | Timing | HTTP | Provider execution | Usage |
|---|---|---:|---:|---:|
| `DOCUMENT_ALIGNMENT_SOURCE_NOT_FOUND` | start | 404 | no | no |
| `DOCUMENT_ALIGNMENT_SOURCE_PERMISSION_DENIED` | start | 403 | no | no |
| `DOCUMENT_ALIGNMENT_SOURCE_NOT_GOVERNED` | start | 422 | no | no |
| `DOCUMENT_ALIGNMENT_PARSE_BLOCKED` | start or worker | 422 or terminal blocked | no | no |
| `DOCUMENT_ALIGNMENT_NO_USABLE_CHUNKS` | start or worker | 422 or terminal blocked | no | no |
| `DOCUMENT_ALIGNMENT_IDEMPOTENCY_REQUIRED` | start | 400 | no | no |
| `DOCUMENT_ALIGNMENT_IDEMPOTENCY_CONFLICT` | start | 409 | no | no |
| `DOCUMENT_ALIGNMENT_INVALID_REQUEST` | start | 400 | no | no |
| `DOCUMENT_ALIGNMENT_NO_TERM_CANDIDATES` | worker | terminal blocked | no | no |
| `DOCUMENT_ALIGNMENT_PROVIDER_POLICY_BLOCKED` | item | item blocked | no | no |
| `DOCUMENT_ALIGNMENT_PROVIDER_PREFLIGHT_BLOCKED` | item | item blocked | no | no |
| `DOCUMENT_ALIGNMENT_EVIDENCE_INSUFFICIENT` | item | item blocked | no | no |
| `DOCUMENT_ALIGNMENT_PERSISTENCE_FAILED` | worker | failed | no further execution | no duplicate usage |
| `DOCUMENT_ALIGNMENT_INTERNAL_PROCESSING_FAILED` | worker | failed | no raw exception | no duplicate usage |

## Legacy Replacement Mapping

| Legacy dependency | Replacement contract |
|---|---|
| `POST /api/alignment/run` | `POST /api/document-alignment-runs` |
| `GET /api/alignment/runs` document list refresh | workflow status and item endpoints |
| `BackgroundJob.alignment_run_id` | BackgroundJob transport references workflow root |
| legacy `AlignmentRun` summary | `DocumentAlignmentWorkflowRun` summary |
| legacy `TerminologyCard` write | `ConceptAlignmentCard` draft plus teacher review |
| legacy `AICallLog` | formal `AlignmentVerificationRun` and AuditRecord |
| legacy `UsageRecord` | formal `AlignmentProviderUsageRecord` |
| legacy provider helper | formal provider governance, policy, preflight, verification |

Frontend cutover must replace the document action, polling, result display,
error display, and legacy run list refresh without reusing `/api/alignment/run`.

## Implementation Prerequisites

Next task:

```text
Task 9C.4W: Formal Workflow Models
```

Required before service implementation:

- `DocumentAlignmentWorkflowRun`;
- `DocumentAlignmentWorkflowItem`;
- idempotency key storage or hash fields;
- root/item status fields;
- source/parse/chunk reference fields;
- progress/count fields;
- safe error fields;
- tests proving BackgroundJob is still transport only.

Application service, route, worker, frontend cutover, legacy HTTP 410, and
dead-path removal are later tasks.

## Unique Conclusion

```text
FORMAL_WORKFLOW_MODELS_REQUIRED_FIRST
```

Existing services are reusable building blocks, but existing models cannot
represent the formal document-level workflow root or item-level progress
without overloading BackgroundJob or legacy AlignmentRun. Therefore the next
slice must establish formal workflow models before implementation.
