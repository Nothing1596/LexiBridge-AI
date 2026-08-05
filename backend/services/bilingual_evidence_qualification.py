"""Deterministic governance for a production-selected bilingual top-1 pair."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any


QUALIFIED = "QUALIFIED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
REJECTED = "REJECTED"

POLICY_ID = "governed-bilingual-evidence-qualification"
POLICY_VERSION = "1.0.0"
CREATED_BY = f"{POLICY_ID}@{POLICY_VERSION}"

# The existing production evidence floor remains unchanged. The margin and
# aggregate gates are new, conservative policy values fixed with non-benchmark
# synthetic contract tests before V2 evaluation.
MIN_EVIDENCE_SCORE = 0.35
MIN_PAIR_SEMANTIC_SCORE = 0.35
MIN_PAIR_MARGIN = 0.05
MIN_QUALIFICATION_SCORE = 0.65
MIN_CONTEXT_CHARS = 12

EVIDENCE_QUALIFICATION_INPUT_INCOMPLETE = "EVIDENCE_QUALIFICATION_INPUT_INCOMPLETE"
EVIDENCE_PROVENANCE_INCOMPLETE = "EVIDENCE_PROVENANCE_INCOMPLETE"
EVIDENCE_SOURCE_NOT_ELIGIBLE = "EVIDENCE_SOURCE_NOT_ELIGIBLE"
EVIDENCE_LANGUAGE_SCOPE_INVALID = "EVIDENCE_LANGUAGE_SCOPE_INVALID"
EVIDENCE_PAIR_NOT_TOP1 = "EVIDENCE_PAIR_NOT_TOP1"
EVIDENCE_PAIR_SCORE_INSUFFICIENT = "EVIDENCE_PAIR_SCORE_INSUFFICIENT"
EVIDENCE_PAIR_MARGIN_INSUFFICIENT = "EVIDENCE_PAIR_MARGIN_INSUFFICIENT"
EVIDENCE_CONTEXT_INSUFFICIENT = "EVIDENCE_CONTEXT_INSUFFICIENT"
EVIDENCE_QUALIFICATION_POLICY_UNAVAILABLE = "EVIDENCE_QUALIFICATION_POLICY_UNAVAILABLE"
EVIDENCE_QUALIFICATION_EXECUTION_FAILED = "EVIDENCE_QUALIFICATION_EXECUTION_FAILED"

_ELIGIBLE_SOURCE_STATUSES = frozenset({"active", "ready", "governed"})
_ELIGIBLE_QUALITY_STATUSES = frozenset({"", "ready", "accepted", "governed", "high_quality"})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", _text(value)).split()).casefold()


def _bounded(value: Any, lower: float = 0.0, upper: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return lower
    return max(lower, min(number, upper))


def _rank_support(value: Any) -> float:
    try:
        rank = max(1, int(value))
    except (TypeError, ValueError):
        return 0.0
    return round(1.0 / rank, 8)


@dataclass(frozen=True)
class BilingualEvidenceQualificationInput:
    english_candidate_uid: str
    english_term: str
    normalized_english_term: str
    english_context: str
    english_source_uid: str
    english_chunk_uid: str
    english_evidence_span: str
    english_source_language: str
    english_source_status: str
    english_quality_status: str
    chinese_candidate_uid: str
    chinese_term: str
    normalized_chinese_term: str
    chinese_context: str
    chinese_source_uid: str
    chinese_chunk_uid: str
    chinese_evidence_span: str
    chinese_source_language: str
    chinese_source_status: str
    chinese_quality_status: str
    retrieval_score: float
    retrieval_rank: int
    extraction_score: float
    extraction_rank: int
    pair_rank: int
    bi_encoder_score: float
    reranker_score: float | None
    final_pair_score: float
    pair_score_margin: float
    pair_backend_id: str
    pair_model_id: str
    pair_model_revision: str
    reranker_backend_id: str
    reranker_model_id: str
    reranker_model_revision: str
    english_representation_hash: str
    chinese_representation_hash: str
    require_independent_sources: bool = True
    english_source_role: str = ""
    chinese_source_role: str = ""


@dataclass(frozen=True)
class BilingualEvidenceQualificationResult:
    decision: str
    qualification_score: float
    qualification_score_is_probability: bool
    score_components: dict[str, float]
    thresholds: dict[str, float | int]
    policy_id: str
    policy_version: str
    reason_codes: tuple[str, ...]
    risk_labels: tuple[str, ...]
    english_provenance: dict[str, str]
    chinese_provenance: dict[str, str]
    pair_rank: int
    pair_score: float
    pair_margin: float
    backend_metadata: dict[str, str]
    representation_hashes: dict[str, str]
    result_id: str
    created_by: str


def policy_manifest() -> dict[str, Any]:
    return {
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "thresholds": {
            "minimum_evidence_score": MIN_EVIDENCE_SCORE,
            "minimum_pair_semantic_score": MIN_PAIR_SEMANTIC_SCORE,
            "minimum_pair_margin": MIN_PAIR_MARGIN,
            "minimum_qualification_score": MIN_QUALIFICATION_SCORE,
            "minimum_context_chars": MIN_CONTEXT_CHARS,
        },
        "existing_evidence_threshold_changed": False,
        "score_weights": {
            "english_span_validity": 0.10,
            "chinese_span_validity": 0.10,
            "provenance_completeness": 0.15,
            "source_governance": 0.15,
            "pair_semantic_score": 0.25,
            "pair_margin_score": 0.10,
            "retrieval_support": 0.075,
            "extraction_support": 0.075,
        },
        "hard_governance_gates": [
            EVIDENCE_PROVENANCE_INCOMPLETE,
            EVIDENCE_SOURCE_NOT_ELIGIBLE,
            EVIDENCE_LANGUAGE_SCOPE_INVALID,
            EVIDENCE_PAIR_NOT_TOP1,
            EVIDENCE_PAIR_SCORE_INSUFFICIENT,
            EVIDENCE_CONTEXT_INSUFFICIENT,
        ],
        "decision_mapping": {
            "QUALIFIED": "all hard gates pass, margin passes, aggregate score passes",
            "REVIEW_REQUIRED": "hard gates pass but pair margin is insufficient",
            "REJECTED": "one or more hard gates fail or aggregate score is insufficient",
        },
        "unknown_decision_fails_closed": True,
        "qualification_score_is_probability": False,
    }


def _stable_result_id(value: BilingualEvidenceQualificationInput, decision: str, reasons: list[str]) -> str:
    payload = {
        "policy": CREATED_BY,
        "english_candidate_uid": _text(value.english_candidate_uid),
        "chinese_candidate_uid": _text(value.chinese_candidate_uid),
        "english_source_uid": _text(value.english_source_uid),
        "english_chunk_uid": _text(value.english_chunk_uid),
        "chinese_source_uid": _text(value.chinese_source_uid),
        "chinese_chunk_uid": _text(value.chinese_chunk_uid),
        "english_representation_hash": _text(value.english_representation_hash),
        "chinese_representation_hash": _text(value.chinese_representation_hash),
        "decision": decision,
        "reasons": sorted(reasons),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "evidence-qualification:" + hashlib.sha256(encoded).hexdigest()


def qualify_bilingual_evidence(
    value: BilingualEvidenceQualificationInput,
) -> BilingualEvidenceQualificationResult:
    reasons: list[str] = []
    required = (
        value.english_candidate_uid,
        value.english_term,
        value.english_source_uid,
        value.english_chunk_uid,
        value.english_evidence_span,
        value.chinese_candidate_uid,
        value.chinese_term,
        value.chinese_source_uid,
        value.chinese_chunk_uid,
        value.chinese_evidence_span,
        value.pair_backend_id,
        value.pair_model_id,
        value.pair_model_revision,
        value.english_representation_hash,
        value.chinese_representation_hash,
    )
    if any(not _text(item) for item in required):
        reasons.append(EVIDENCE_PROVENANCE_INCOMPLETE)
    if len(_text(value.english_context)) < MIN_CONTEXT_CHARS or len(_text(value.chinese_context)) < MIN_CONTEXT_CHARS:
        reasons.append(EVIDENCE_CONTEXT_INSUFFICIENT)

    english_span_valid = _norm(value.english_term) in _norm(value.english_evidence_span)
    chinese_span_valid = _norm(value.chinese_term) in _norm(value.chinese_evidence_span)
    if not english_span_valid or not chinese_span_valid:
        reasons.append(EVIDENCE_PROVENANCE_INCOMPLETE)

    source_governed = (
        _norm(value.english_source_status) in _ELIGIBLE_SOURCE_STATUSES
        and _norm(value.chinese_source_status) in _ELIGIBLE_SOURCE_STATUSES
        and _norm(value.english_quality_status) in _ELIGIBLE_QUALITY_STATUSES
        and _norm(value.chinese_quality_status) in _ELIGIBLE_QUALITY_STATUSES
    )
    if not source_governed:
        reasons.append(EVIDENCE_SOURCE_NOT_ELIGIBLE)

    independent_language_scope = (
        _norm(value.english_source_language) == "en"
        and _norm(value.chinese_source_language) == "zh"
    )
    governed_bilingual_scope = (
        _norm(value.english_source_language) == "mixed"
        and _norm(value.chinese_source_language) == "mixed"
        and _norm(value.english_source_role) == "bilingual_reference"
        and _norm(value.chinese_source_role) == "bilingual_reference"
    )
    language_valid = independent_language_scope or governed_bilingual_scope
    if value.require_independent_sources:
        language_valid = language_valid and _text(value.english_source_uid) != _text(value.chinese_source_uid)
    if not language_valid:
        reasons.append(EVIDENCE_LANGUAGE_SCOPE_INVALID)
    if int(value.pair_rank or 0) != 1:
        reasons.append(EVIDENCE_PAIR_NOT_TOP1)
    if float(value.bi_encoder_score or 0.0) < MIN_PAIR_SEMANTIC_SCORE:
        reasons.append(EVIDENCE_PAIR_SCORE_INSUFFICIENT)
    if float(value.pair_score_margin or 0.0) < MIN_PAIR_MARGIN:
        reasons.append(EVIDENCE_PAIR_MARGIN_INSUFFICIENT)
    if float(value.retrieval_score or 0.0) < MIN_EVIDENCE_SCORE:
        reasons.append(EVIDENCE_PAIR_SCORE_INSUFFICIENT)

    components = {
        "english_span_validity": 1.0 if english_span_valid else 0.0,
        "chinese_span_validity": 1.0 if chinese_span_valid else 0.0,
        "provenance_completeness": 0.0 if EVIDENCE_PROVENANCE_INCOMPLETE in reasons else 1.0,
        "source_governance": 1.0 if source_governed and language_valid else 0.0,
        "pair_semantic_score": _bounded(value.bi_encoder_score),
        "pair_margin_score": _bounded(float(value.pair_score_margin or 0.0) / 0.20),
        "retrieval_support": _rank_support(value.retrieval_rank),
        "extraction_support": _bounded(value.extraction_score),
    }
    score = round(
        0.10 * components["english_span_validity"]
        + 0.10 * components["chinese_span_validity"]
        + 0.15 * components["provenance_completeness"]
        + 0.15 * components["source_governance"]
        + 0.25 * components["pair_semantic_score"]
        + 0.10 * components["pair_margin_score"]
        + 0.075 * components["retrieval_support"]
        + 0.075 * components["extraction_support"],
        8,
    )

    hard_reasons = {
        EVIDENCE_PROVENANCE_INCOMPLETE,
        EVIDENCE_SOURCE_NOT_ELIGIBLE,
        EVIDENCE_LANGUAGE_SCOPE_INVALID,
        EVIDENCE_PAIR_NOT_TOP1,
        EVIDENCE_PAIR_SCORE_INSUFFICIENT,
        EVIDENCE_CONTEXT_INSUFFICIENT,
    }
    if set(reasons) & hard_reasons or score < MIN_QUALIFICATION_SCORE:
        decision = REJECTED
        if score < MIN_QUALIFICATION_SCORE and EVIDENCE_PAIR_SCORE_INSUFFICIENT not in reasons:
            reasons.append(EVIDENCE_PAIR_SCORE_INSUFFICIENT)
    elif EVIDENCE_PAIR_MARGIN_INSUFFICIENT in reasons:
        decision = REVIEW_REQUIRED
    else:
        decision = QUALIFIED
    reasons = sorted(set(reasons))
    risks = tuple(
        sorted(
            reason
            for reason in reasons
            if reason != EVIDENCE_PAIR_MARGIN_INSUFFICIENT or decision != QUALIFIED
        )
    )
    return BilingualEvidenceQualificationResult(
        decision=decision,
        qualification_score=score,
        qualification_score_is_probability=False,
        score_components=components,
        thresholds=dict(policy_manifest()["thresholds"]),
        policy_id=POLICY_ID,
        policy_version=POLICY_VERSION,
        reason_codes=tuple(reasons),
        risk_labels=risks,
        english_provenance={
            "source_uid": _text(value.english_source_uid),
            "chunk_uid": _text(value.english_chunk_uid),
            "span_hash": hashlib.sha256(_text(value.english_evidence_span).encode()).hexdigest(),
        },
        chinese_provenance={
            "source_uid": _text(value.chinese_source_uid),
            "chunk_uid": _text(value.chinese_chunk_uid),
            "span_hash": hashlib.sha256(_text(value.chinese_evidence_span).encode()).hexdigest(),
        },
        pair_rank=int(value.pair_rank or 0),
        pair_score=round(float(value.final_pair_score or 0.0), 8),
        pair_margin=round(float(value.pair_score_margin or 0.0), 8),
        backend_metadata={
            "pair_backend_id": _text(value.pair_backend_id),
            "pair_model_id": _text(value.pair_model_id),
            "pair_model_revision": _text(value.pair_model_revision),
            "reranker_backend_id": _text(value.reranker_backend_id),
            "reranker_model_id": _text(value.reranker_model_id),
            "reranker_model_revision": _text(value.reranker_model_revision),
        },
        representation_hashes={
            "english": _text(value.english_representation_hash),
            "chinese": _text(value.chinese_representation_hash),
        },
        result_id=_stable_result_id(value, decision, reasons),
        created_by=CREATED_BY,
    )


def serialize_qualification_result(
    result: BilingualEvidenceQualificationResult | None,
) -> dict[str, Any] | None:
    return asdict(result) if result is not None else None


def qualify_workflow_top1(
    input_data: dict[str, Any],
    english_evidence: list[dict[str, Any]],
    chinese_evidence: list[dict[str, Any]],
    chinese_candidates: list[dict[str, Any]],
    pair_candidates: list[dict[str, Any]],
) -> BilingualEvidenceQualificationResult | None:
    if not pair_candidates:
        return None
    ordered = sorted(pair_candidates, key=lambda item: (int(item.get("rank") or 999), -float(item.get("final_score") or 0.0)))
    top = ordered[0]
    candidate = next(
        (
            item for item in chinese_candidates
            if _text(item.get("candidate_uid")) == _text(top.get("chinese_candidate_uid"))
        ),
        None,
    )
    if candidate is None:
        return None
    english = next(
        (
            item for item in english_evidence
            if _text(item.get("source_uid")) == _text((input_data.get("english_provenance") or {}).get("source_uid"))
            and _text(item.get("chunk_uid")) == _text((input_data.get("english_provenance") or {}).get("chunk_uid"))
        ),
        english_evidence[0] if english_evidence else {},
    )
    chinese = next(
        (
            item for item in chinese_evidence
            if _text(item.get("source_uid")) == _text(top.get("source_uid"))
            and _text(item.get("chunk_uid")) == _text(top.get("chunk_uid"))
        ),
        {},
    )
    next_score = float(ordered[1].get("final_score") or 0.0) if len(ordered) > 1 else 0.0
    components = dict(top.get("score_components") or {})
    return qualify_bilingual_evidence(BilingualEvidenceQualificationInput(
        english_candidate_uid=_text(top.get("english_candidate_uid") or input_data.get("english_candidate_uid")),
        english_term=_text(input_data.get("english_term")),
        normalized_english_term=_text(input_data.get("normalized_english_term")),
        english_context=_text(input_data.get("english_context")),
        english_source_uid=_text(english.get("source_uid")),
        english_chunk_uid=_text(english.get("chunk_uid")),
        english_evidence_span=_text(english.get("snippet") or input_data.get("english_context")),
        english_source_language=_text(english.get("language") or "en"),
        english_source_status=_text(english.get("status") or "active"),
        english_quality_status=_text(english.get("quality_status") or "ready"),
        chinese_candidate_uid=_text(candidate.get("candidate_uid")),
        chinese_term=_text(candidate.get("chinese_term")),
        normalized_chinese_term=_text(candidate.get("normalized_text") or candidate.get("chinese_term")),
        chinese_context=_text(candidate.get("evidence_snippet") or candidate.get("snippet")),
        chinese_source_uid=_text(top.get("source_uid")),
        chinese_chunk_uid=_text(top.get("chunk_uid")),
        chinese_evidence_span=_text(candidate.get("original_span") or candidate.get("evidence_snippet") or candidate.get("snippet")),
        chinese_source_language=_text(chinese.get("language") or "zh"),
        chinese_source_status=_text(chinese.get("status") or "active"),
        chinese_quality_status=_text(chinese.get("quality_status") or "ready"),
        retrieval_score=float(chinese.get("score") or candidate.get("retrieval_score") or 0.0),
        retrieval_rank=int(top.get("retrieval_rank") or candidate.get("retrieval_rank") or 999),
        extraction_score=float(candidate.get("score") or 0.0),
        extraction_rank=int(top.get("extraction_rank") or candidate.get("rank") or 999),
        pair_rank=int(top.get("rank") or 0),
        bi_encoder_score=float(top.get("semantic_score") or 0.0),
        reranker_score=top.get("cross_encoder_score"),
        final_pair_score=float(top.get("final_score") or 0.0),
        pair_score_margin=float(top.get("final_score") or 0.0) - next_score,
        pair_backend_id=_text(top.get("backend_id")),
        pair_model_id=_text(top.get("model_id")),
        pair_model_revision=_text(top.get("model_revision")),
        reranker_backend_id=_text(top.get("reranker_backend_id")),
        reranker_model_id=_text(top.get("reranker_model_id")),
        reranker_model_revision=_text(top.get("reranker_model_revision")),
        english_representation_hash=_text(top.get("english_representation_hash")),
        chinese_representation_hash=_text(top.get("chinese_representation_hash")),
        require_independent_sources=not (
            _norm(english.get("language")) == "mixed"
            and _norm(chinese.get("language")) == "mixed"
            and _text(english.get("source_uid")) == _text(chinese.get("source_uid"))
        ),
        english_source_role=_text(english.get("source_role")),
        chinese_source_role=_text(chinese.get("source_role")),
    ))
