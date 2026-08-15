# Student PDF Reading and Concept Selection

## Scope

Task 13C.3 turns the existing Student ConceptQuery page into a page-aware
course-material reader. It composes the Task 12/13 ingestion and alignment
objects; it does not add a parser, index, retrieval engine, alignment engine or
database table.

The reader serves both `PERSONAL` and `MANAGED_COURSE` workspaces. Workspace
scope changes ownership, membership and labels only. The selection and
alignment contracts are identical.

## Before and after

Before:

```text
My Workspace -> select "选词学习" -> generic material selector
  -> first 100 KnowledgeChunks rendered as one flat list
  -> select text -> existing ConceptQuery
```

After:

```text
authorized English KnowledgeSource
  -> student material reader contract
  -> authenticated original-PDF stream -> browser-local Blob URL
  -> page-aware governed KnowledgeChunks with page/block/span provenance
  -> select one bounded English term or phrase inside one chunk
  -> server re-reads the chunk and validates exact text and offsets
  -> existing ConceptQuery / Task 12 alignment / PersonalLearningRecord
```

## Reader contract

`student-material-reader@1.0.0` is exposed through the Student namespace:

- `GET /api/student/concept-materials/{source_uid}/reader?page={page}`
- `GET /api/student/concept-materials/{source_uid}/file`

The JSON endpoint returns source identity, workspace identity, bounded parser
identity, available-page navigation and the governed chunks on exactly one
page. Each selectable item includes chunk UID, page, parse-block UID, heading
path, block type, content hash and a chunk-relative `[span_start, span_end)`.
Storage keys, local paths and full document bodies are not serialized.

The original PDF endpoint is Student-only and reuses the same ownership or
active-course-membership check. It returns only an active, accessible PDF with
`private, no-store`, `nosniff`, same-origin framing and inline disposition.
The frontend fetches it with the existing Bearer credential, creates a
browser-local Blob URL, and revokes the URL on source change or logout. The
credential is never placed in an iframe URL.

## Selection and provenance

Browser PDF viewers do not expose a portable DOM selection API. The product
therefore displays the original PDF beside page-synchronized parsed text. The
student selects from the parsed text, not from an unverifiable visual overlay.

Selection remains bounded to one `KnowledgeChunk`. The client submits only
source UID, chunk UID, selected text and offsets. The server retrieves the
authorized chunk again, verifies exact byte-for-character text equality,
reconstructs bounded context and records source/page/block/span provenance.
Missing page or block provenance fails closed before the text is selectable.

This is an auditable page reader, not coordinate-level PDF highlighting. A
future coordinate overlay would require governed bounding boxes from the
parser and is intentionally outside this phase.

## Access control

- Personal source: exact Student ownership, active governed source, private PDF.
- Managed Course source: active `CourseMember` and source bound to that course.
- Other Student: not-found semantics.
- Instructor, Reviewer and Admin: denied by the Student-only route guard.
- Deleted/inactive source or unavailable file: no file response.
- A Managed Course source without retained original PDF still exposes its
  governed parsed text; the UI shows a safe unavailable-preview state.

The reader never exposes another Student's source, a source from another
course, storage metadata, credentials, Provider configuration or Reviewer data.

## Reused objects and migration decision

Reused production objects:

- `Document` for private storage identity and file lifecycle;
- `DocumentParseRecord` for parser identity and page count;
- `KnowledgeSource` for governance and access scope;
- `KnowledgeChunk` for selectable page/block evidence;
- `CourseMember` for Managed Course membership;
- `StudentConceptQuery` and `PersonalLearningRecord` for query and learning
  state;
- the existing Task 12 bilingual evidence workflow.

No migration is required. The older `/chunks` endpoint remains as a temporary
compatibility surface but the product UI no longer uses its flat, 100-item
view. Removal can happen only under a separate API deprecation task.

## Provider and privacy boundary

Reading and selecting a concept requires no Provider. The original PDF remains
private and is not copied into artifacts, audit payloads or model inputs. The
alignment result can still be shown without LLM explanation because the core
concept, candidates and evidence come from the existing governed alignment
chain. Automated tests use temporary databases/storage and deterministic local
scoring backends, with zero external application or real Provider requests.
