# PR Review Stages

`Dev` is the integration branch. New work should branch from `Dev` and target
`Dev` with focused, reviewable pull requests.

## Completed Integration Baseline

### PR-1 / PR-2: Knowledge ingestion quality baseline

Commit: `d49d9ed feat: add knowledge ingestion quality baseline`

Scope:

- deterministic knowledge retrieval scoring
- term extraction quality fixes
- layout metadata persistence
- optional DocLayout-YOLO ONNX provider
- upload content validation
- pytest coverage for retrieval, extraction, layout, upload size, and file
  signature checks

### PR-3: Database migration baseline

Commit: `bfc61de feat: add database migrations baseline`

Scope:

- Flask-Migrate / Alembic integration
- initial migration for the current v0.1 schema
- migration smoke test for empty SQLite databases
- developer migration notes

### PR-4: Confidence scoring baseline

PR: #1, merged into `Dev`

Scope:

- implement the documented `confidence_score` formula as a pure service
- keep formula inputs normalized to 0-1
- return `confidence_score` on the 0-100 persistence/API contract and
  `normalized_confidence_score` for audit
- add a documented risk-flag to penalty-points mapping helper
- implement documented hard blockers for auto approval
- do not yet choose a final auto-approval threshold or wire the state machine

Tests:

- formula weights
- score clamping
- 0-100 to 0-1 normalization for current term confidence values
- 0-100 risk penalty point normalization
- risk-flag penalty mapping
- mock/local/rule-based provider auto-approval block
- missing evidence, invalid term, conflict, and risk flag blockers

### PR-5: Terminology state machine and auto-approval gate

PR: #2, merged into `Dev`

Scope:

- encode the documented TerminologyCard status set and allowed transitions
- implement the documented auto-approval gate as a pure service
- enforce confidence >= 85 and term/en/zh evidence component thresholds >= 0.80
- require live provider, schema validation, and local rule validation inputs
- route non-auto outcomes to `needs_more_evidence`,
  `pending_quality_control`, or `conflict_detected`
- do not yet add database columns, migrations, or API wiring

Tests:

- all documented allowed transitions
- forbidden transitions such as `rejected -> auto_approved`
- full auto-approval pass case
- low confidence and weak evidence blockers
- missing evidence routing
- conflict routing
- provider, schema, and local-rule blockers

## Active / Next Stacked PRs

### PR-6: TerminologyCard persistence baseline

Branch: `pr6-terminology-card-persistence`

Scope:

- add the v1.0 `TerminologyCard` SQLAlchemy model
- add Alembic migration for `terminology_card`
- persist evidence snapshots, confidence, alignment/status, risk/audit fields,
  feedback count, and approval metadata
- add documented course/personal duplicate-prevention unique constraints
- add query indexes for status, alignment status, terms, scope/owner/course,
  evidence chunk ids, and feedback count
- do not yet wire card creation into APIs or the alignment runner

Tests:

- migration creates the table, key columns, and important indexes
- ORM persistence stores evidence snapshots and audit fields
- course-scope duplicate normalized English terms are rejected

## Review Rules

- Each PR must include tests for the changed behavior.
- Migration changes must include an upgrade smoke test.
- Model-provider changes must keep rule-based fallback behavior tested.
- Major decisions such as OCR provider choice, auth policy, and auto-approval
  thresholds need user confirmation before implementation.
