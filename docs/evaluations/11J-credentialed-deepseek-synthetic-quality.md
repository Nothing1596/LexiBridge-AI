# Task 11J-R2 Credentialed DeepSeek Synthetic Quality Evaluation

## Status

- Technical status: `CREDENTIALED_DEEPSEEK_SYNTHETIC_EVALUATION_BLOCKED`
- Quality status: `BILINGUAL_KNOWLEDGE_QUALITY_VALIDATION_BLOCKED`
- Credential present: `true`
- Provider/model: `deepseek-alignment-v1` / `deepseek-chat`
- Transport configured: `DeepSeekHTTPTransport`
- Provider requests: `0`

## Attempt history

- Attempt 1: credential missing; Provider requests `0`.
- Attempt 2: Formal Workflow provider admission blocked; Provider requests `0`.
- Attempt 3 (11J-R2): the 11K sealed capability passed the evaluation gate and
  Formal Workflow provider selection. Momentum item preparation returned
  `DOCUMENT_ALIGNMENT_EVIDENCE_INSUFFICIENT`; Provider requests `0`.

Attempt 3 is consistent with the fresh retrieval-only result: momentum misses
the required English evidence at top 3. Because this failure occurs before the
Provider, its primary attribution is `ENGLISH_RETRIEVAL_DEFECT`. Task 11J-R2
forbids changing retrieval, and a failed preflight forbids the 25-item run.
No direct Provider request, replay, mock substitution, model switch, or runtime
monkeypatch was used.

## Frozen data and retrieval-only reproducibility

- Corpus SHA-256: `33715999c16a74610091b1e40896ee41921570a3740ebc2815565cf0ab7202dc`
- Gold SHA-256: `199baed9a8cb6deb68ae3480c3a67679b2daf273d3733e909d4e861685d45302`
- Concepts: `25`
- Synthetic sources: `4`
- Knowledge sources: `4`
- Knowledge chunks: `58`
- Retrieval-only Provider requests: `0`

| Metric | Fresh result |
| --- | ---: |
| Candidate recall | 0.0000 |
| Chinese candidate exactness top-1 | 0.0000 |
| Chinese candidate exactness top-3 | 0.0000 |
| English hit@3 | 0.2400 |
| Chinese hit@3 | 1.0000 |
| Bilingual evidence completeness | 0.2400 |
| Valid-evidence subset | 6/25 |

These values were recomputed through current upload, ingestion, candidate, and
retrieval code before any Provider request. They match 11E, so no corpus,
ordering, or filtering drift was found.

## Provider quality

The momentum preflight entered Formal Workflow with the verified evaluation
context and persisted the requested provider/model selection. Item preparation
then blocked on insufficient frozen evidence before transport. Therefore
request/retry counts are `0/0`, token usage and latency are unavailable, and
neither valid-evidence-subset Provider metrics nor all-25 end-to-end Provider
metrics can be reported. The 25-item run was not started.

Primary attribution:
`ENGLISH_RETRIEVAL_DEFECT`.

## Safety

- The accident database matched its frozen SHA-256, size, mtime, and absent
  WAL/SHM state before evaluation.
- Retrieval used a repository-external temporary SQLite database.
- Accident database business data was not queried or copied.
- Private data egress: `0`
- Secret exposure: `0`
- External document API requests: `0`
- Synthetic Provider egress: `0`

## Verification

- Required targeted regression: `41 passed`
- Related Formal Workflow, retrieval, and candidate regression: `45 passed`
- Full pytest: `1233 passed, 20 failed, 12 errors` out of 1265
- Every full-suite failure/error was caused by the sandbox denying a
  `127.0.0.1` bind with `PermissionError: [Errno 1] Operation not permitted`.
- dev_check: `1233 passed, 20 failed, 12 errors`; failed at its internal pytest
  step for the same loopback sandbox restriction.
- release-safety: passed.
- The loopback restriction is an environment limitation and is not attributed
  to `DeepSeekHTTPTransport`.
- The final accident database SHA-256, size, mtime, WAL, and SHM state exactly
  matched the before state.
