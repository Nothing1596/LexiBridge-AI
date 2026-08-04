# Pilot Runbook

## 1. Before The Pilot

1. Run migrations and seed demo or course data.
2. Confirm teacher/admin accounts are verified.
3. Confirm course membership for pilot students.
4. Run the smoke evaluation set and save the report.
5. Confirm OCR, Formula OCR, and AI provider status are visible to users.

## 2. Course Setup

1. Teacher creates or selects the course.
2. Teacher uploads English course notes and Chinese reference material.
3. Teacher monitors document ingestion jobs.
4. Teacher triggers alignment after parsing completes.
5. Teacher reviews `needs_more_evidence`, `pending_quality_control`, and conflict cards.

## 3. Student Trial

1. Student selects the joined course.
2. Student searches core English terms.
3. Student opens terminology cards and checks evidence.
4. Student uses favorite/mastered actions.
5. Student submits feedback for translation, evidence, explanation, OCR, formula OCR, or UI issues.

## 4. Feedback Handling

1. Teacher opens Feedback Review.
2. Teacher filters high/critical feedback first.
3. Teacher triages to `triaged` or `in_review`.
4. Teacher resolves, rejects, marks needs more evidence, converts to backlog, or converts to EvaluationItem.
5. Critical permission/security feedback is escalated to Admin.

## 5. Regression

1. Convert important real feedback to EvaluationItem.
2. Run the evaluation set.
3. Confirm `no_evidence_forced_alignment_rate = 0`.
4. Compare metrics with the previous pilot report.

## 6. Reporting

1. Run `python scripts/generate_pilot_report.py --course-id <id> --output docs/generated/pilot_report_course_<id>.md`.
2. Run `python scripts/export_feedback_summary.py --course-id <id> --output feedback_summary.csv`.
3. Review the iteration backlog and assign target PRs.

## Data That Must Not Be Public

- Full student email or real name.
- Tokens, API keys, password reset codes.
- Full personal uploaded document content.
- Full OCR text or AI prompts/responses.
