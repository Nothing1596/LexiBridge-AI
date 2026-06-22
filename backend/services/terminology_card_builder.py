import json
import re

from services.confidence import (
    calculate_confidence_score,
    normalize_percent_score,
    risk_penalty_from_flags,
)
from services.terminology_state import evaluate_auto_approval_gate


WHITESPACE_PATTERN = re.compile(r"\s+")
VALID_SCOPE_TYPES = {"course", "personal", "global"}


def normalize_term(value):
    if not value:
        return ""

    return WHITESPACE_PATTERN.sub(" ", str(value).strip().lower())


def normalize_chinese_term(value):
    if not value:
        return None

    return WHITESPACE_PATTERN.sub("", str(value).strip())


def _normalized_flags(values):
    return {
        str(value).strip().lower()
        for value in (values or [])
        if str(value).strip()
    }


def _evidence_risk_flags(english_evidence_score, chinese_evidence_score):
    flags = set()

    if normalize_percent_score(english_evidence_score) <= 0:
        flags.add("no_en_evidence")

    if normalize_percent_score(chinese_evidence_score) <= 0:
        flags.add("no_zh_evidence")

    return flags


def _default_risk_note(gate_result):
    if gate_result["allowed"]:
        return None

    return "Auto approval blocked: " + ", ".join(gate_result["reasons"])


def validate_card_identity(
    *,
    scope_type,
    english_term,
    course_id=None,
    owner_user_id=None,
    source_document_id=None,
):
    normalized_scope = normalize_term(scope_type)

    if normalized_scope not in VALID_SCOPE_TYPES:
        raise ValueError("scope_type must be course, personal, or global")

    if not normalize_term(english_term):
        raise ValueError("english_term is required")

    if normalized_scope == "course" and course_id is None:
        raise ValueError("course_id is required for course cards")

    if normalized_scope == "personal":
        if owner_user_id is None:
            raise ValueError("owner_user_id is required for personal cards")

        if source_document_id is None:
            raise ValueError("source_document_id is required for personal cards")

    return normalized_scope


def build_terminology_card_payload(
    *,
    scope_type,
    english_term,
    final_chinese_term=None,
    course_id=None,
    owner_user_id=None,
    source_document_id=None,
    courseware_sentence=None,
    english_evidence_chunk_id=None,
    chinese_evidence_chunk_id=None,
    english_evidence_snapshot=None,
    chinese_evidence_snapshot=None,
    english_evidence_score=0,
    chinese_evidence_score=0,
    term_quality_score=0,
    ai_alignment_score=0,
    course_scope_score=0,
    source_quality_score=0,
    alignment_status="unverified_translation",
    provider=None,
    provider_is_live=False,
    ai_model=None,
    prompt_version=None,
    schema_validated=False,
    local_rules_passed=False,
    risk_flags=None,
    quality_flags=None,
    risk_note=None,
):
    """
    Build a TerminologyCard-compatible payload without writing to the database.

    This is the narrow bridge between extraction/retrieval/alignment outputs and
    the v1.0 persistence model. API permission checks, idempotency, and DB writes
    stay outside this function.
    """
    normalized_scope_type = validate_card_identity(
        scope_type=scope_type,
        english_term=english_term,
        course_id=course_id,
        owner_user_id=owner_user_id,
        source_document_id=source_document_id,
    )
    normalized_english_term = normalize_term(english_term)
    normalized_chinese_term = normalize_chinese_term(final_chinese_term)
    normalized_english_evidence_score = normalize_percent_score(
        english_evidence_score
    )
    normalized_chinese_evidence_score = normalize_percent_score(
        chinese_evidence_score
    )
    normalized_term_quality_score = normalize_percent_score(term_quality_score)
    normalized_ai_alignment_score = normalize_percent_score(ai_alignment_score)
    normalized_course_scope_score = normalize_percent_score(course_scope_score)
    normalized_source_quality_score = normalize_percent_score(source_quality_score)

    normalized_risk_flags = _normalized_flags(risk_flags)
    normalized_risk_flags.update(
        _evidence_risk_flags(
            normalized_english_evidence_score,
            normalized_chinese_evidence_score,
        )
    )
    risk = risk_penalty_from_flags(
        risk_flags=normalized_risk_flags,
        provider=provider,
    )
    normalized_risk_flags = set(risk["risk_flags"])

    confidence = calculate_confidence_score(
        term_quality_score=normalized_term_quality_score,
        english_evidence_score=normalized_english_evidence_score,
        chinese_evidence_score=normalized_chinese_evidence_score,
        ai_alignment_score=normalized_ai_alignment_score,
        course_scope_score=normalized_course_scope_score,
        source_quality_score=normalized_source_quality_score,
        risk_penalty=risk["risk_penalty"],
    )
    gate = evaluate_auto_approval_gate(
        confidence_score=confidence["confidence_score"],
        term_quality_score=normalized_term_quality_score,
        english_evidence_score=normalized_english_evidence_score,
        chinese_evidence_score=normalized_chinese_evidence_score,
        provider=provider,
        provider_is_live=provider_is_live,
        schema_validated=schema_validated,
        local_rules_passed=local_rules_passed,
        risk_flags=normalized_risk_flags,
    )

    normalized_quality_flags = sorted(
        _normalized_flags(quality_flags) | normalized_risk_flags
    )
    score_breakdown = {
        "confidence": confidence,
        "auto_approval_gate": gate,
        "risk": risk,
        "inputs": {
            "term_quality_score": normalized_term_quality_score,
            "english_evidence_score": normalized_english_evidence_score,
            "chinese_evidence_score": normalized_chinese_evidence_score,
            "ai_alignment_score": normalized_ai_alignment_score,
            "course_scope_score": normalized_course_scope_score,
            "source_quality_score": normalized_source_quality_score,
        },
    }

    return {
        "scope_type": normalized_scope_type,
        "course_id": course_id,
        "owner_user_id": owner_user_id,
        "source_document_id": source_document_id,
        "english_term": english_term,
        "normalized_english_term": normalized_english_term,
        "final_chinese_term": final_chinese_term,
        "normalized_chinese_term": normalized_chinese_term,
        "courseware_sentence": courseware_sentence,
        "english_evidence_chunk_id": english_evidence_chunk_id,
        "chinese_evidence_chunk_id": chinese_evidence_chunk_id,
        "english_evidence_snapshot": english_evidence_snapshot,
        "chinese_evidence_snapshot": chinese_evidence_snapshot,
        "english_evidence_score": normalized_english_evidence_score,
        "chinese_evidence_score": normalized_chinese_evidence_score,
        "alignment_status": alignment_status,
        "confidence_score": confidence["confidence_score"],
        "status": gate["recommended_status"],
        "ai_provider": provider,
        "ai_model": ai_model,
        "prompt_version": prompt_version,
        "score_breakdown_json": json.dumps(
            score_breakdown,
            ensure_ascii=False,
            sort_keys=True,
        ),
        "quality_flags_json": json.dumps(
            normalized_quality_flags,
            ensure_ascii=False,
            sort_keys=True,
        ),
        "risk_note": risk_note or _default_risk_note(gate),
    }
