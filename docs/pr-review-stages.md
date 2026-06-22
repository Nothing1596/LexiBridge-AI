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

## Active / Next Stacked PRs

### PR-4: Confidence scoring baseline

Branch: `pr4-confidence-scoring`

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

## Review Rules

- Each PR must include tests for the changed behavior.
- Migration changes must include an upgrade smoke test.
- Model-provider changes must keep rule-based fallback behavior tested.
- Major decisions such as OCR provider choice, auth policy, and auto-approval
  thresholds need user confirmation before implementation.
