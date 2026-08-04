# Task 12C.1 — Frozen Chinese Candidate Precision and Pairing Diagnosis

Status: `CHINESE_CANDIDATE_PRECISION_DIAGNOSIS_COMPLETED`

## Executive conclusion

The current Task 12B.3 English pipeline binds all 25 frozen concepts exactly,
so the complete benchmark population now reaches the Chinese diagnostic
boundary. The historical Chinese top1 and top3 results were recomputed rather
than reused. Both remain 0.0000.

The dominant and earliest failure is a Chinese candidate boundary defect, not
retrieval, ranking, pairing, or Provider readiness. All 25 gold Chinese terms
exist in the frozen source, parsed text, and chunks. The production
candidate-source retrieval finds every gold-bearing chunk within its top three.
However, the explicit bilingual pattern captures up to 32 Chinese or
alphanumeric characters after `English term 即` without stopping at Chinese
definition predicates. It therefore emits definition fragments such as
`术语 + 是/表示/描述/说明 + explanation` instead of the exact term.

Production generated at least one Chinese candidate for every concept, but
generated zero exact or accepted-alias candidates. Pairing consequently
received 25 correct English inputs and zero correct Chinese inputs. There is
no independently observable pairing-selection defect in this population
because the correct Chinese candidate never reaches that layer.

Task 12C.1 added only evaluation scripts, tests, sanitized artifacts, and this
report. It did not change production quality.

## Current 25-item Chinese baseline

| Metric | Current result |
| --- | ---: |
| Benchmark coverage | 25/25 |
| English exact matched | 25/25 |
| Chinese gold term in source | 25/25 |
| Chinese gold term in parsed text | 25/25 |
| Chinese gold term in chunk | 25/25 |
| Concepts with at least one generated Chinese candidate | 25/25 |
| Exact Chinese candidate generated | 0/25 |
| Accepted-alias candidate generated | 0/25 |
| Chinese candidate top1 accuracy | 0.0000 |
| Chinese candidate top3 accuracy | 0.0000 |
| Chinese candidate MRR | 0.0000 |
| Bilingual pair top1 accuracy | 0.0000 |
| Bilingual pair top3 accuracy | 0.0000 |
| Operational evidence-qualified | 5/25 |
| Provider-ready | 5/25 |

No benchmark concept defines an additional accepted Chinese alias, so alias
generation and alias-source presence are not applicable to this fixture.

## Retrieval results

The production candidate-generation retrieval, queried with the system-derived
English candidate against governed Chinese reference chunks, produced:

- hit@1: 0.6000 (15/25);
- hit@3: 1.0000 (25/25);
- MRR: 0.8000;
- all gold-bearing chunks in the production retrieval scope: 25/25.

Ten concepts had their gold-bearing chunk at rank 2 because another governed
chunk containing the same English substring ranked equally or higher. This did
not prevent candidate generation because all gold-bearing chunks remained in
the production retrieval scope.

For historical comparability, the second retrieval performed after selecting
the generated Chinese fragment produced hit@1 1.0000, hit@3 1.0000, and MRR
1.0000. This apparently perfect evidence retrieval is not a term-quality
success: the overlong selected fragment is copied from the definition chunk,
so it retrieves that same chunk exactly. The historical evidence hit@3 result
therefore coexists with zero Chinese candidate accuracy.

## Candidate morphology audit

Production emitted 30 post-dedup candidates across 25 concepts:

- candidate count per concept: 21 concepts produced one, three concepts
  produced two, and one concept produced three;
- average candidate length: 15.8333 characters;
- candidates containing a definition predicate: 30/30;
- definition-fragment ratio: 1.0000;
- candidates longer than 12 characters: 25/30;
- generic standalone candidates: 0/30;
- single-character candidates: 0/30;
- mixed Chinese/English candidates: 0/30;
- parenthesized English abbreviations: 0/30;
- symbol or unit candidates: 0/30;
- full-width ASCII candidates: 0/30;
- Unicode punctuation retained in candidate text: 0/30;
- post-dedup duplicate ratio: 0.0000;
- ranking inversion count: 0, because no correct candidate exists to be
  inverted;
- top1 and top3 precision proxies: both 0.0000.

Four concepts produced multiple candidates with identical 0.81 scores:
`velocity`, `force`, `momentum`, and `mechanical energy`. These are
overgeneration observations, but their earliest defect remains boundary
capture because every competing candidate is itself a definition fragment.
No simplified/traditional or full-width/half-width competition was observed
in the frozen fixture.

## Attribution counts

| Primary attribution | Count | Denominator |
| --- | ---: | ---: |
| `CHINESE_CANDIDATE_BOUNDARY_DEFECT` | 25 | 25 |
| All other attribution classes | 0 | 25 |

The generator did not merely fail to emit output: every item produced one or
more candidates. The exact term was present at every upstream stage, and the
retrieval scope included every correct chunk. The first divergence was
`extract_chinese_candidates_from_text_around_english_term`, where
`CHINESE_PATTERN` greedily included the definition predicate and explanation.

There were no benchmark fixture defects and no benchmark alias gaps.

## Ranking audit

There are no valid `CHINESE_CANDIDATE_RANKING_DEFECT` cases in this run.
Ranking defects require a correct candidate to be present but ranked below the
accepted cutoff. Here, exact and alias candidate presence is 0/25.

All bilingual-chunk candidates receive the same principal production features
in this synthetic corpus: exact English match, course match, Chinese reference
role, bilingual pattern, and governed source trust. The four multi-candidate
concepts therefore have equal 0.81 candidate scores. Retrieval score is
retained in diagnostic breakdown but is not included in the final candidate
score.

The primary selector orders by descending score, then candidate UID, then
case-folded Chinese text. This is deterministic within a persisted run, but
candidate UID includes source/chunk identity, so an equal-score selection can
change across fresh synthetic ingestions that receive new UUIDs. That behavior
did not hide a correct candidate in this benchmark because none was generated.

## Bilingual pairing audit

Pairing inputs and outcomes:

- correct English input present: 25/25;
- correct Chinese input present: 0/25;
- correct pair: 0/25;
- independent pairing defects: 0/25;
- truncation loss of a correct Chinese input: 0;
- source/chunk provenance retained: yes.

Production candidate discovery uses exact English lexical matching and
proximity to the English term inside a governed Chinese/bilingual chunk.
Candidate scoring uses source type, exact English match, course/chapter,
trust, source role, bilingual-pattern status, duplicate-source support, and
risk penalties. It does not use cross-language surface overlap, definition
similarity, retrieval rank, or abbreviation mapping.

The pairing/selection boundary chooses the highest-scoring generated candidate;
it does not independently verify semantic equivalence. There is no explicit
pair-failure reason code. Instead, candidates carry
`candidate_not_alignment_verified`, and formal preparation may continue if
evidence exists. This is a separate governance limitation, but it cannot be
classified as the primary defect until correct Chinese candidates are supplied
to the layer.

## Evidence readiness audit

Five electricity concepts were operationally evidence-qualified and
Provider-ready:

- electric charge;
- electric field;
- electric potential;
- potential difference;
- capacitance.

The other 20 returned `DOCUMENT_ALIGNMENT_EVIDENCE_INSUFFICIENT` during formal
preparation. None is classified as `EVIDENCE_READINESS_DEFECT`, because every
concept had already failed at the earlier Chinese boundary stage.

Operational readiness does not mean the pair is correct. All five ready items
still selected overlong Chinese definition fragments. Real Provider requests
remained zero.

## Population funnel and survivor bias

Every layer retains the original denominator:

| Population/subset | Count | Original denominator |
| --- | ---: | ---: |
| All benchmark concepts | 25 | 25 |
| Gold-bearing Chinese chunk in production retrieval scope | 25 | 25 |
| Exact/accepted Chinese candidate generated | 0 | 25 |
| Correct candidate in top3 | 0 | 25 |
| Correctly paired | 0 | 25 |
| Operational evidence-qualified | 5 | 25 |
| Provider-ready | 5 | 25 |

The operational evidence-qualified and Provider-ready sets are not semantic
subsets of correctly paired items: preparation does not have access to
benchmark correctness and can ready an overlong candidate. Treating the five
ready electricity items as the Chinese-quality denominator would therefore
introduce strong conditional selection bias.

Task 12B raised downstream English coverage from a small matched subset to all
25 concepts, exposing the existing Chinese behavior across the full
population. It did not improve Chinese top1 or top3 accuracy. The current
Chinese logic already retrieved the correct chunks, but its candidate boundary
contract prevented that retrieval strength from becoming correct terms.

## Recommended Task 12C.2 priority

The single dominant root cause is the boundary contract in the explicit
bilingual pattern extractor: the Chinese capture following an English alias
does not stop before `是`, `指`, `表示`, `称为`, `定义为`, `描述`, `说明`, or
similar definition predicates.

Task 12C.2 should address that general boundary only, with unseen bilingual
fixtures and false-positive controls. Ranking, pairing, retrieval, thresholds,
Prompt, and Provider behavior should remain unchanged until exact Chinese
candidate generation is remeasured.

This is a diagnosis and recommendation, not a production repair.

## RED/GREEN and validation

The RED run failed during collection because the evaluation-only diagnosis
module did not yet exist. After implementing the diagnostic runner:

- focused diagnostic GREEN: 10 passed;
- required targeted regression: 48 passed;
- release safety: passed.

The runner uses repository-external temporary SQLite storage and configures
the database before backend import. It does not read a DeepSeek credential or
call any Provider.

## Frozen inputs, database safety, and artifacts

Frozen hashes remained:

- Corpus:
  `33715999c16a74610091b1e40896ee41921570a3740ebc2815565cf0ab7202dc`
- Gold:
  `199baed9a8cb6deb68ae3480c3a67679b2daf273d3733e909d4e861685d45302`

The incident database remained unchanged before and after:

- SHA-256:
  `9e6fb68ab13dff2763e2fff18d2aee531486360c557f058eb8a471d9209a9eaa`
- size: 1015808
- mtime: 1785496597
- WAL: absent
- SHM: absent

Sanitized artifacts:

- `12C1-chinese-candidate-matrix.json`:
  `b4826f01ef1e8d4abc87e6b6c1563a9f3101b651c8d8fd1f68deb248a38a8f50`
- `12C1-chinese-candidate-matrix.csv`:
  `ad4f784318521bbaf23aa03f07ebbe69c004a2575a4be58d7f45369825332dd9`
- `12C1-bilingual-pairing-audit.json`:
  `7bcd93de29365565c8fe872cac5236f7c2c1de06bd9fe4bc8042cbf14010784d`

The artifacts contain bounded candidate summaries and governed identifiers,
not complete source text, credentials, private material, machine-absolute
paths, or incident database contents.

Task 12C.1 made no production change and did not begin Task 12C.2.
