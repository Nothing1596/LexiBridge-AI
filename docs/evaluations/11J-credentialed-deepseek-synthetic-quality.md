# Task 11J-R Credentialed DeepSeek Synthetic Quality Evaluation

## Status

- Technical status: `CREDENTIALED_DEEPSEEK_SYNTHETIC_EVALUATION_BLOCKED`
- Quality status: `BILINGUAL_KNOWLEDGE_QUALITY_VALIDATION_BLOCKED`
- Credential present: `true`
- Provider/model: `deepseek-alignment-v1` / `deepseek-chat`
- Transport configured: `DeepSeekHTTPTransport`
- Provider requests: `0`

## Blocking boundary

The evaluation-only real-provider policy gate allowed the frozen corpus, gold,
runner identity, request budget, isolated database, provider, model, and
credential checks. The next required boundary did not allow the provider:
the frozen Formal Workflow server-owned provider selection rejects
`deepseek-alignment-v1`, and item preparation independently rejects providers
that support external calls.

Consequently, the required momentum preflight could not reach
`DeepSeekHTTPTransport` through the Formal Workflow. Continuing would require
changing production provider selection/preparation or bypassing the workflow
with a hand-built prepared input. Both actions are forbidden by Task 11J-R.
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

The momentum preflight was not run because Formal Workflow selection blocked
before transport. Therefore request/retry counts are `0/0`, token usage and
latency are unavailable, and neither valid-evidence-subset Provider metrics nor
all-25 end-to-end Provider metrics can be reported. No concept was removed from
a denominator; the Provider evaluation denominator was never opened.

Primary attribution:
`FORMAL_WORKFLOW_EXTERNAL_PROVIDER_SELECTION_UNAVAILABLE`.

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

- Targeted Provider, Formal Workflow, retrieval, candidate, and metrics
  regression: `63 passed`
- Full pytest: `1222 passed, 20 failed, 12 errors` out of 1254
- Every full-suite failure/error was caused by the sandbox denying a
  `127.0.0.1` bind with `PermissionError: [Errno 1] Operation not permitted`.
- dev_check: failed at its internal pytest step for the same loopback sandbox
  restriction.
- release-safety: passed.
- The loopback restriction is an environment limitation and is not attributed
  to `DeepSeekHTTPTransport`.
- The final accident database SHA-256, size, mtime, WAL, and SHM state exactly
  matched the before state.
