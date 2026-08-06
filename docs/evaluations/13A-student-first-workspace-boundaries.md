# Task 13A — Student-First Workspace, Role and Content Boundary Contract

## Executive conclusion

Technical status: `STUDENT_FIRST_WORKSPACE_BOUNDARY_CONTRACT_CLOSED`

Quality status: `STUDENT_FIRST_WORKSPACE_BOUNDARY_BASELINE_ESTABLISHED`

Baseline main commit: `99f2651a146b44f152aa3d72f995abfe518c643d`; Task 12J-B commit `1de2fb76ae88c6a5f907a75ad166957f1befaf5b` is an ancestor.

Task 13A establishes the product contract without changing parsing, retrieval, Chinese candidate identification, pairing, qualification, readiness, Prompt, Provider transport, or frozen V2 data.

## Production before / after

Before:

`Formal run/item → ConceptAlignmentCard → teacher-labelled review queue → review record → readiness → draft → approved student card`

The storage workflow was reusable, but product concepts were conflated: course implied official semantics in the student UI, review was presented as an Instructor duty, `teacher/admin` was hard-coded on review routes, and there was no common five-dimensional student-result contract.

After:

`Personal or Managed workspace → shared AlignmentResult serializer → private/non-official Student result`

and, independently:

`Managed AlignmentResult anomaly/official request → Reviewer Console (existing review objects/routes) → governed official draft/publication`

The machine result, personal learning contract, and official publication path are now explicitly separate.

## Reused objects

The implementation reuses `Course`, `CourseMember`, `DocumentAlignmentWorkflowRun`, `DocumentAlignmentWorkflowItem`, `ConceptAlignmentCard`, `ConceptCardReviewRecord`, `StudentConceptCardState`, and `AuditRecord`. `TerminologyCard` remains legacy. No schema or migration was created.

## Route and navigation changes

- Existing concept-card review endpoints admit `reviewer` while retaining `teacher` as documented transitional compatibility.
- Reviewer access still requires course review permission; generic card detail enforces the same boundary.
- Instructor navigation no longer contains Concept Review and its dashboard is English-only and English-course focused.
- Reviewer navigation exposes the existing page as Reviewer Console.
- Student review/draft protection and published-card behavior are unchanged.

## Serializer and state contract

`student-first-boundaries@1.0.0` provides enums, legal-state validation, role capabilities, workspace-membership DTO validation, shared Student result serialization, generated-hint isolation, and a contract-only PersonalLearningRecord projection.

READY, REVIEW_REQUIRED, and NOT_READY are not publication decisions. REVIEW_REQUIRED remains student-viewable; NOT_READY cannot expose a canonical Chinese term.

## Task 12J-B reclassification

Task 12J-B is retained intact as bilingual anomaly and official-content infrastructure. Product-facing labels call it Reviewer Console. Existing internal `teacher_*` function/module names are not duplicated or destructively renamed.

## Translation boundary

Translation/glossary/Ollama data is accepted only when explicitly marked generated/no-evidence/GENERATED_HINT. It is removed from evidence-backed candidates and cannot become canonical output for NOT_READY or official content.

## Known limitations and Task 13B prerequisites

- There is no durable PersonalLearningRecord aggregate yet.
- Workspace identity is currently a DTO/metadata contract over existing ownership/course objects.
- `ConceptAlignmentCard.status` remains a legacy storage projection; the new five dimensions are not schema columns.
- Teacher review access remains temporarily compatible at the API layer, hidden from Instructor navigation.
- Reviewer-specific student-feedback authorization remains future work.

Task 13B should consume the shared serializer and create one student concept-query vertical slice; it must not add another alignment engine or require Reviewer approval.

## Safety

Application external API requests: 0.

Real Provider requests: 0.

Real credentials read: false.

The repository accident database was not used by tests and is verified before/final in the task handoff.

## Verification

- Targeted boundary, permission, publication, Task 12J-B, idempotency/audit and frontend tests: 52 passed.
- Final frontend/reviewer focused check after the last navigation-only edit: 10 passed.
- Full pytest: 1596 passed, 5 skipped, 56 warnings.
- `scripts/dev_check.py`: passed, including its independent full pytest, migration and backend smoke.
- `scripts/check_release_safety.py`: passed.
- `git diff --check`: passed.

Frozen Cross-Corpus V2 hashes:

- English bundle: `e84fc99a993c099628fe7d740c1e248fefe1e03cbece7b4df43d02cd7dfaddc5`
- Chinese bundle: `cebd3274cb0802fa645948d9b641b1776c60ab99700bbf3cd4a80999bc45b5f7`
- Gold: `3379bc1e6c589256dcec384a9f7435c96277f6754b7cb44cff69f86244a9b3f0`
- Manifest: `a53a5152aa66189c954b703c42fb815a6a8c7f83933051f80f1538e78bdc3f88`

Artifact hashes:

- `13A-role-capability-matrix.json`: `bed0f22982aabe900961d560823bc28fc4211a56ff924ec45344cf78ca372865`
- `13A-result-dimension-contract.json`: `b13f3b6417a51ebe9ed6627ed9b9701da8339b7ed6f7be157985913d65d0771c`
- `13A-route-navigation-audit.json`: `33369c9ffdc76c1a3715e9143dfc986fbfd48157167c3288c0c878eb78829025`
- `13A-legal-state-combinations.csv`: `9274eb38bddbb400c58653d67b197001518395966902646a4e6cdd5cc8a2b173`

Accident database before/final: SHA-256 `9e6fb68ab13dff2763e2fff18d2aee531486360c557f058eb8a471d9209a9eaa`; size `1015808`; mtime `1785496597`; WAL/SHM absent/absent.
