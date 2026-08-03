# Task 11J-R3 Credentialed DeepSeek Synthetic Quality Evaluation

## Status

- Technical status: `CREDENTIALED_DEEPSEEK_SYNTHETIC_EVALUATION_BLOCKED`
- Quality status: `BILINGUAL_KNOWLEDGE_QUALITY_VALIDATION_BLOCKED`
- Credential present: `true`
- Provider/model: `deepseek-alignment-v1` / `deepseek-chat`
- Transport configured: `DeepSeekHTTPTransport`
- Provider requests: `1`

## Attempt history

- Attempt 1: credential missing; Provider requests `0`.
- Attempt 2: Formal Workflow provider admission blocked; Provider requests `0`.
- Attempt 3 (11J-R2): the 11K sealed capability passed the evaluation gate and
  Formal Workflow provider selection. Momentum item preparation returned
  `DOCUMENT_ALIGNMENT_EVIDENCE_INSUFFICIENT`; Provider requests `0`.
- Attempt 4 (11J-R3): the 11L readiness selector chose `physics-21`, the first
  provider-ready concept in frozen order. The full Formal path made one
  successful DeepSeek request and persisted the term pair, confidence, and
  evidence references. The required explanation was absent from persisted
  verification output, so the systemic preflight failed with
  `WORKFLOW_OR_PERSISTENCE_DEFECT`. The 25-item run was not started.

Attempt 3 is consistent with the fresh retrieval-only result: momentum misses
the required English evidence at top 3. Because this failure occurs before the
Provider, its primary attribution is `ENGLISH_RETRIEVAL_DEFECT`. Task 11J-R2
forbids changing retrieval, and a failed preflight forbids the 25-item run.
No direct endpoint bypass, replay, mock substitution, model switch, or runtime
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

## Formal readiness and Provider preflight

- Formal provider ready: `5/25`
- Formal provider not ready: `20/25`
- Gold-scored valid-evidence subset: `6/25`
- Deterministic preflight selection: `physics-21`
- Selection reason: `first_provider_ready_in_frozen_order`

Formal readiness is the production preparation predicate and does not read gold
scoring data. The gold-valid subset remains a separate evaluation metric.

The selected preflight entered the complete Formal Workflow and
`DeepSeekHTTPTransport`. Request/retry counts were `1/0`; wall latency was
approximately `5 seconds`. The Provider did not report usage, so the runner's
request estimates are `1,770` input and `1,000` output tokens. The response
parsed successfully and persisted the term pair, confidence, provenance, and
evidence references, but not the required explanation. This systemic
persistence validation failure forbids the 25-item run. Valid-evidence-subset
Provider metrics and all-25 metrics are therefore unavailable.

Primary attribution:
`WORKFLOW_OR_PERSISTENCE_DEFECT`.

## Safety

- The accident database matched its frozen SHA-256, size, mtime, and absent
  WAL/SHM state before evaluation.
- Retrieval used a repository-external temporary SQLite database.
- Accident database business data was not queried or copied.
- Private data egress: `0`
- Secret exposure: `0`
- External document API requests: `0`
- Synthetic-only Provider requests: `1`

## Verification

- Required targeted and evaluation-boundary regression: `56 passed`
- Full pytest: `1238 passed, 20 failed, 12 errors` out of 1270
- Every full-suite failure/error was caused by the sandbox denying a
  `127.0.0.1` bind with `PermissionError: [Errno 1] Operation not permitted`.
- dev_check: `1238 passed, 20 failed, 12 errors`; failed at its internal pytest
  step for the same loopback sandbox restriction.
- release-safety: passed.
- The loopback restriction is an environment limitation and is not attributed
  to `DeepSeekHTTPTransport`.
- The final accident database SHA-256, size, mtime, WAL, and SHM state exactly
  matched the before state.
