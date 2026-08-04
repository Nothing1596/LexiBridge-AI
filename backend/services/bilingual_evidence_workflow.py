"""Bilingual evidence retrieval workflow for Concept Card draft payloads.

The workflow only retrieves governed evidence and prepares a draft payload. It
does not call an LLM, verify final alignment, invent confidence, or approve a
ConceptAlignmentCard.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services import chinese_term_candidates
from services import evidence_retrieval
from services import parse_quality_risk


BILINGUAL_RETRIEVAL_VERSION = "lexical-v1"
LOW_EVIDENCE_SCORE_THRESHOLD = 0.35
MAX_BILINGUAL_LIMIT = 20


class BilingualEvidenceWorkflowError(ValueError):
    """Raised for controlled bilingual evidence workflow failures."""


@dataclass(frozen=True)
class BilingualEvidenceResult:
    english_term: str
    chinese_term: str
    course: str
    chapter: str
    concept_scope: str
    filters: dict[str, Any]
    english_evidence_candidates: list[dict[str, Any]]
    chinese_evidence_candidates: list[dict[str, Any]]
    chinese_term_candidates: list[dict[str, Any]]
    selected_chinese_candidate: dict[str, Any] | None
    risk_labels: list[str]
    draft_payload: dict[str, Any]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: Any, default: int = 5) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_labels(labels: Any) -> list[str]:
    return parse_quality_risk.normalize_labels(labels)


def _merge_labels(*label_groups: Any) -> list[str]:
    merged: list[str] = []
    for labels in label_groups:
        merged = parse_quality_risk.merge_risk_labels(merged, labels)
    return merged


def build_bilingual_evidence_query(input_data: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(input_data or {})
    english_term = _text(data.get("english_term") or data.get("query") or data.get("q"))
    if not english_term:
        raise BilingualEvidenceWorkflowError("english_term is required.")
    limit = max(1, min(_as_int(data.get("limit"), 5), MAX_BILINGUAL_LIMIT))
    filters = dict(data.get("filters") or {})
    for key in ("include_needs_review", "include_low_quality", "visibility", "trust_level", "quality_status", "source_uid"):
        if key in data and key not in filters:
            filters[key] = data[key]
    candidate_limit = max(1, min(_as_int(data.get("candidate_limit"), 10), chinese_term_candidates.MAX_CANDIDATE_LIMIT))
    return {
        "english_term": english_term,
        "chinese_term": _text(data.get("chinese_term")),
        "course": _text(data.get("course")),
        "chapter": _text(data.get("chapter")),
        "concept_scope": _text(data.get("concept_scope")),
        "limit": limit,
        "auto_generate_chinese_candidates": _as_bool(data.get("auto_generate_chinese_candidates")),
        "candidate_limit": candidate_limit,
        "selected_chinese_candidate_uid": _text(data.get("selected_chinese_candidate_uid")),
        "filters": {
            **filters,
            "include_needs_review": _as_bool(filters.get("include_needs_review")),
            "include_low_quality": _as_bool(filters.get("include_low_quality")),
        },
    }


def _candidate_key(candidate: dict[str, Any]) -> str:
    return _text(candidate.get("chunk_uid")) or _text(candidate.get("evidence_uid"))


def _merge_candidates(groups: list[list[dict[str, Any]]], limit: int) -> list[dict[str, Any]]:
    seen = set()
    merged: list[dict[str, Any]] = []
    for group in groups:
        for candidate in group:
            key = _candidate_key(candidate)
            if not key or key in seen:
                continue
            merged.append(candidate)
            seen.add(key)
            if len(merged) >= limit:
                return merged
    return merged


def _base_filters(course: str | None, chapter: str | None, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    base = dict(filters or {})
    if course:
        base["course"] = course
    if chapter:
        base["chapter"] = chapter
    return base


def _search_with_attempts(
    session: Any,
    chunk_model: Any,
    source_model: Any,
    term: str,
    attempts: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    groups = []
    for filters in attempts:
        result = evidence_retrieval.search_evidence(
            session,
            chunk_model,
            source_model,
            term,
            filters=filters,
            limit=limit,
        )
        groups.append(result.candidates)
    return _merge_candidates(groups, limit)


def retrieve_english_evidence(
    session: Any,
    chunk_model: Any,
    source_model: Any,
    english_term: str,
    course: str | None = None,
    chapter: str | None = None,
    limit: int = 5,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    term = _text(english_term)
    if not term:
        raise BilingualEvidenceWorkflowError("english_term is required.")
    base = _base_filters(course, chapter, filters)
    attempts = [
        {**base, "language": "en", "source_role": "english_course_material", "source_type": "course_material"},
        {**base, "language": "en", "source_role": "english_course_material", "source_type": "textbook"},
        {**base, "language": "en", "source_role": "english_course_material", "source_type": "reference"},
        {**base, "language": "en", "source_role": "english_course_material"},
        {**base, "language": "mixed", "source_role": "bilingual_reference"},
        {**base, "language": "en"},
    ]
    return _search_with_attempts(session, chunk_model, source_model, term, attempts, limit)


def retrieve_chinese_evidence(
    session: Any,
    chunk_model: Any,
    source_model: Any,
    chinese_term: str,
    course: str | None = None,
    chapter: str | None = None,
    limit: int = 5,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    term = _text(chinese_term)
    if not term:
        return []
    base = _base_filters(course, chapter, filters)
    attempts = [
        {**base, "language": "zh", "source_role": "chinese_reference_material", "source_type": "textbook"},
        {**base, "language": "zh", "source_role": "chinese_reference_material", "source_type": "reference"},
        {**base, "language": "zh", "source_role": "chinese_reference_material", "source_type": "teacher_upload"},
        {**base, "language": "zh", "source_role": "chinese_reference_material"},
        {**base, "language": "mixed", "source_role": "bilingual_reference"},
        {**base, "language": "zh"},
    ]
    return _search_with_attempts(session, chunk_model, source_model, term, attempts, limit)


def _candidate_has_review_risk(candidate: dict[str, Any]) -> bool:
    status = _text(candidate.get("status"))
    quality_status = _text(candidate.get("quality_status"))
    flags = set(_normalize_labels(candidate.get("quality_flags", [])))
    risk_labels = set(_normalize_labels(candidate.get("risk_labels", [])))
    return (
        status == "needs_review"
        or quality_status in evidence_retrieval.REVIEW_QUALITY_STATUSES
        or bool(flags & evidence_retrieval.REVIEW_QUALITY_STATUSES)
        or "needs_review_evidence" in risk_labels
    )


def _candidate_has_partial_text(candidate: dict[str, Any]) -> bool:
    quality_status = _text(candidate.get("quality_status"))
    flags = set(_normalize_labels(candidate.get("quality_flags", [])))
    risk_labels = set(_normalize_labels(candidate.get("risk_labels", [])))
    return quality_status == "partial_text" or "partial_text" in flags or "input_partial_text" in risk_labels


def _candidate_low_trust(candidate: dict[str, Any]) -> bool:
    trust_level = _text(candidate.get("trust_level"))
    return trust_level in {"low_quality", "unknown", "student_uploaded"}


def _mismatches(candidate: dict[str, Any], field: str, expected: str) -> bool:
    expected = _text(expected)
    actual = _text(candidate.get(field))
    return bool(expected and actual and actual != expected)


def classify_bilingual_evidence_risks(
    english_candidates: list[dict[str, Any]],
    chinese_candidates: list[dict[str, Any]],
    input_data: dict[str, Any] | None = None,
) -> list[str]:
    data = dict(input_data or {})
    risks = ["bilingual_alignment_not_verified"]
    chinese_term = _text(data.get("chinese_term"))
    course = _text(data.get("course"))
    chapter = _text(data.get("chapter"))

    if not english_candidates:
        risks.append("no_english_evidence")
    if not chinese_term:
        risks.append("missing_chinese_term")
    elif not chinese_candidates:
        risks.append("no_chinese_evidence")
    if not english_candidates or not chinese_candidates:
        risks.append("cross_language_evidence_missing")

    if english_candidates and float(english_candidates[0].get("score") or 0) < LOW_EVIDENCE_SCORE_THRESHOLD:
        risks.append("low_english_evidence_score")
    if chinese_candidates and float(chinese_candidates[0].get("score") or 0) < LOW_EVIDENCE_SCORE_THRESHOLD:
        risks.append("low_chinese_evidence_score")

    all_candidates = [*english_candidates, *chinese_candidates]
    if any(_mismatches(candidate, "course", course) for candidate in all_candidates):
        risks.append("course_mismatch")
    if any(_mismatches(candidate, "chapter", chapter) for candidate in all_candidates):
        risks.append("chapter_mismatch")
    if any(_candidate_has_review_risk(candidate) for candidate in all_candidates):
        risks.append("evidence_from_needs_review_source")
    if any(_candidate_has_partial_text(candidate) for candidate in all_candidates):
        risks.append("evidence_from_partial_text")
    if any(_candidate_low_trust(candidate) for candidate in all_candidates):
        risks.append("evidence_from_low_trust_source")
    return _merge_labels(risks)


def _status_from_risks(risk_labels: list[str]) -> str:
    return "needs_review" if risk_labels else "draft"


def build_concept_card_draft_payload_from_evidence(
    input_data: dict[str, Any],
    english_candidates: list[dict[str, Any]],
    chinese_candidates: list[dict[str, Any]],
    chinese_candidates_for_term: list[dict[str, Any]] | None = None,
    selected_chinese_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query = build_bilingual_evidence_query(input_data)
    risks = classify_bilingual_evidence_risks(english_candidates, chinese_candidates, query)
    if chinese_candidates_for_term:
        risks = _merge_labels(risks, ["candidate_not_alignment_verified"])
    if input_data.get("candidate_risk_labels"):
        risks = _merge_labels(risks, input_data.get("candidate_risk_labels"))
    chinese_evidence = [evidence_retrieval.serialize_evidence_candidate(candidate) for candidate in chinese_candidates]
    if selected_chinese_candidate:
        selected_summary = chinese_term_candidates.serialize_chinese_term_candidate(selected_chinese_candidate)
        selected_marker = {
            "evidence_type": "selected_chinese_candidate",
            "selected_chinese_candidate": selected_summary,
            "chunk_uid": selected_summary.get("chunk_uid", ""),
            "source_uid": selected_summary.get("source_uid", ""),
            "source_title": "",
            "course": selected_summary.get("course", ""),
            "chapter": selected_summary.get("chapter", ""),
            "language": "zh",
            "source_role": "",
            "trust_level": selected_summary.get("trust_level", ""),
            "quality_status": selected_summary.get("quality_status", ""),
            "quality_flags": selected_summary.get("quality_flags", []),
            "source_locator": selected_summary.get("source_locator", ""),
            "snippet": selected_summary.get("evidence_snippet", ""),
            "score": selected_summary.get("score", 0.0),
            "retrieval_reason": "selected Chinese term candidate for draft evidence retrieval",
            "risk_labels": selected_summary.get("risk_labels", []),
            "parse_uid": selected_summary.get("parse_uid", ""),
            "parse_block_uid": selected_summary.get("parse_block_uid", ""),
        }
        chinese_evidence = [selected_marker, *chinese_evidence]
    return {
        "english_term": query["english_term"],
        "chinese_term": query["chinese_term"],
        "course": query["course"],
        "chapter": query["chapter"],
        "concept_scope": query["concept_scope"],
        "english_evidence": [evidence_retrieval.serialize_evidence_candidate(candidate) for candidate in english_candidates],
        "chinese_evidence": chinese_evidence,
        "chinese_term_candidates": [
            chinese_term_candidates.serialize_chinese_term_candidate(candidate)
            for candidate in (chinese_candidates_for_term or [])
        ],
        "selected_chinese_candidate": (
            chinese_term_candidates.serialize_chinese_term_candidate(selected_chinese_candidate)
            if selected_chinese_candidate else None
        ),
        "risk_labels": risks,
        "status": _status_from_risks(risks),
        "confidence_score": None,
        "alignment_reason": "",
        "model_name": None,
        "prompt_version": None,
        "retrieval_version": BILINGUAL_RETRIEVAL_VERSION,
    }


def retrieve_bilingual_evidence(
    session: Any,
    chunk_model: Any,
    source_model: Any,
    english_term: str,
    chinese_term: str | None = None,
    course: str | None = None,
    chapter: str | None = None,
    limit: int = 5,
    filters: dict[str, Any] | None = None,
    concept_scope: str = "",
    auto_generate_chinese_candidates: bool = False,
    candidate_limit: int = 10,
    selected_chinese_candidate_uid: str | None = None,
    concept_card_model: Any | None = None,
    term_model: Any | None = None,
    terminology_card_model: Any | None = None,
    audit_context: dict[str, Any] | None = None,
) -> BilingualEvidenceResult:
    del audit_context
    input_data = build_bilingual_evidence_query({
        "english_term": english_term,
        "chinese_term": chinese_term,
        "course": course,
        "chapter": chapter,
        "concept_scope": concept_scope,
        "limit": limit,
        "filters": filters or {},
        "auto_generate_chinese_candidates": auto_generate_chinese_candidates,
        "candidate_limit": candidate_limit,
        "selected_chinese_candidate_uid": selected_chinese_candidate_uid,
    })
    english_candidates = retrieve_english_evidence(
        session,
        chunk_model,
        source_model,
        input_data["english_term"],
        course=input_data["course"],
        chapter=input_data["chapter"],
        limit=input_data["limit"],
        filters=input_data["filters"],
    )
    generated_candidates: list[dict[str, Any]] = []
    selected_candidate = None
    candidate_risk_labels: list[str] = []
    effective_chinese_term = input_data["chinese_term"]
    if not effective_chinese_term and input_data["auto_generate_chinese_candidates"]:
        candidate_result = chinese_term_candidates.generate_chinese_term_candidates(
            session,
            concept_card_model=concept_card_model,
            term_model=term_model,
            terminology_card_model=terminology_card_model,
            chunk_model=chunk_model,
            source_model=source_model,
            english_term=input_data["english_term"],
            course=input_data["course"],
            chapter=input_data["chapter"],
            limit=input_data["candidate_limit"],
            filters=input_data["filters"],
        )
        generated_candidates = [
            chinese_term_candidates.serialize_chinese_term_candidate(candidate)
            for candidate in candidate_result.candidates
        ]
        candidate_risk_labels = candidate_result.risk_labels
        requested_uid = input_data["selected_chinese_candidate_uid"]
        if generated_candidates:
            selected_candidate = next(
                (candidate for candidate in generated_candidates if requested_uid and candidate.get("candidate_uid") == requested_uid),
                generated_candidates[0],
            )
            effective_chinese_term = _text(selected_candidate.get("chinese_term"))
            input_data["chinese_term"] = effective_chinese_term

    chinese_candidates = retrieve_chinese_evidence(
        session,
        chunk_model,
        source_model,
        effective_chinese_term,
        course=input_data["course"],
        chapter=input_data["chapter"],
        limit=input_data["limit"],
        filters=input_data["filters"],
    )
    risk_labels = _merge_labels(
        classify_bilingual_evidence_risks(english_candidates, chinese_candidates, input_data),
        candidate_risk_labels,
    )
    draft_payload = build_concept_card_draft_payload_from_evidence(
        {**input_data, "candidate_risk_labels": candidate_risk_labels},
        english_candidates,
        chinese_candidates,
        generated_candidates,
        selected_candidate,
    )
    draft_payload["risk_labels"] = risk_labels
    return BilingualEvidenceResult(
        english_term=input_data["english_term"],
        chinese_term=effective_chinese_term,
        course=input_data["course"],
        chapter=input_data["chapter"],
        concept_scope=input_data["concept_scope"],
        filters={**input_data["filters"], "limit": input_data["limit"]},
        english_evidence_candidates=english_candidates,
        chinese_evidence_candidates=chinese_candidates,
        chinese_term_candidates=generated_candidates,
        selected_chinese_candidate=selected_candidate,
        risk_labels=risk_labels,
        draft_payload=draft_payload,
    )


def serialize_bilingual_evidence_result(result: BilingualEvidenceResult) -> dict[str, Any]:
    return {
        "english_term": result.english_term,
        "chinese_term": result.chinese_term,
        "course": result.course,
        "chapter": result.chapter,
        "concept_scope": result.concept_scope,
        "filters": dict(result.filters),
        "english_evidence_candidates": [
            evidence_retrieval.serialize_evidence_candidate(candidate)
            for candidate in result.english_evidence_candidates
        ],
        "chinese_evidence_candidates": [
            evidence_retrieval.serialize_evidence_candidate(candidate)
            for candidate in result.chinese_evidence_candidates
        ],
        "chinese_term_candidates": [
            chinese_term_candidates.serialize_chinese_term_candidate(candidate)
            for candidate in result.chinese_term_candidates
        ],
        "selected_chinese_candidate": (
            chinese_term_candidates.serialize_chinese_term_candidate(result.selected_chinese_candidate)
            if result.selected_chinese_candidate else None
        ),
        "risk_labels": list(result.risk_labels),
        "draft_payload": dict(result.draft_payload),
    }
