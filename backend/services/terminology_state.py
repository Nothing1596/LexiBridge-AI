from services.confidence import (
    auto_approval_block_reasons,
    normalize_percent_score,
)


TERMINOLOGY_STATUS_DRAFT = "draft"
TERMINOLOGY_STATUS_NEEDS_MORE_EVIDENCE = "needs_more_evidence"
TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL = "pending_quality_control"
TERMINOLOGY_STATUS_CONFLICT_DETECTED = "conflict_detected"
TERMINOLOGY_STATUS_AUTO_APPROVED = "auto_approved"
TERMINOLOGY_STATUS_APPROVED = "approved"
TERMINOLOGY_STATUS_REJECTED = "rejected"
TERMINOLOGY_STATUS_ARCHIVED = "archived"

TERMINOLOGY_STATUSES = {
    TERMINOLOGY_STATUS_DRAFT,
    TERMINOLOGY_STATUS_NEEDS_MORE_EVIDENCE,
    TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL,
    TERMINOLOGY_STATUS_CONFLICT_DETECTED,
    TERMINOLOGY_STATUS_AUTO_APPROVED,
    TERMINOLOGY_STATUS_APPROVED,
    TERMINOLOGY_STATUS_REJECTED,
    TERMINOLOGY_STATUS_ARCHIVED,
}

ALLOWED_STATUS_TRANSITIONS = {
    TERMINOLOGY_STATUS_DRAFT: {
        TERMINOLOGY_STATUS_NEEDS_MORE_EVIDENCE,
        TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL,
        TERMINOLOGY_STATUS_CONFLICT_DETECTED,
        TERMINOLOGY_STATUS_AUTO_APPROVED,
    },
    TERMINOLOGY_STATUS_NEEDS_MORE_EVIDENCE: {
        TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL,
    },
    TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL: {
        TERMINOLOGY_STATUS_APPROVED,
        TERMINOLOGY_STATUS_REJECTED,
        TERMINOLOGY_STATUS_NEEDS_MORE_EVIDENCE,
    },
    TERMINOLOGY_STATUS_CONFLICT_DETECTED: {
        TERMINOLOGY_STATUS_APPROVED,
        TERMINOLOGY_STATUS_REJECTED,
    },
    TERMINOLOGY_STATUS_AUTO_APPROVED: {
        TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL,
    },
    TERMINOLOGY_STATUS_APPROVED: {
        TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL,
        TERMINOLOGY_STATUS_ARCHIVED,
    },
    TERMINOLOGY_STATUS_REJECTED: {
        TERMINOLOGY_STATUS_ARCHIVED,
    },
    TERMINOLOGY_STATUS_ARCHIVED: set(),
}

AUTO_APPROVAL_CONFIDENCE_THRESHOLD = 85
AUTO_APPROVAL_COMPONENT_THRESHOLD = 0.80


def normalize_status(value):
    return (value or "").strip().lower()


def is_valid_status(value):
    return normalize_status(value) in TERMINOLOGY_STATUSES


def can_transition(from_status, to_status):
    normalized_from = normalize_status(from_status)
    normalized_to = normalize_status(to_status)

    if normalized_from not in TERMINOLOGY_STATUSES:
        return False

    return normalized_to in ALLOWED_STATUS_TRANSITIONS[normalized_from]


def validate_status_transition(from_status, to_status):
    normalized_from = normalize_status(from_status)
    normalized_to = normalize_status(to_status)

    return {
        "allowed": can_transition(normalized_from, normalized_to),
        "from_status": normalized_from,
        "to_status": normalized_to,
    }


def _add_threshold_reason(reasons, reason, score, threshold):
    if normalize_percent_score(score) < threshold:
        reasons.append(reason)


def _non_auto_status_for_reasons(reasons):
    reason_set = set(reasons)

    if reason_set & {"domain_mismatch", "multi_translation_conflict"}:
        return TERMINOLOGY_STATUS_CONFLICT_DETECTED

    if reason_set & {"no_en_evidence", "no_zh_evidence"}:
        return TERMINOLOGY_STATUS_NEEDS_MORE_EVIDENCE

    return TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL


def evaluate_auto_approval_gate(
    *,
    confidence_score,
    term_quality_score,
    english_evidence_score,
    chinese_evidence_score,
    provider,
    provider_is_live,
    schema_validated,
    local_rules_passed,
    risk_flags=None,
):
    """
    Evaluate the documented v1.0 auto-approval gate.

    The function is intentionally pure. It does not write a card, choose a
    translation, or bypass human review outside the documented gate.
    """
    reasons = auto_approval_block_reasons(
        provider=provider,
        risk_flags=risk_flags,
        english_evidence_score=english_evidence_score,
        chinese_evidence_score=chinese_evidence_score,
    )

    _add_threshold_reason(
        reasons,
        "confidence_below_threshold",
        confidence_score,
        normalize_percent_score(AUTO_APPROVAL_CONFIDENCE_THRESHOLD),
    )
    _add_threshold_reason(
        reasons,
        "term_quality_below_threshold",
        term_quality_score,
        AUTO_APPROVAL_COMPONENT_THRESHOLD,
    )
    _add_threshold_reason(
        reasons,
        "english_evidence_below_threshold",
        english_evidence_score,
        AUTO_APPROVAL_COMPONENT_THRESHOLD,
    )
    _add_threshold_reason(
        reasons,
        "chinese_evidence_below_threshold",
        chinese_evidence_score,
        AUTO_APPROVAL_COMPONENT_THRESHOLD,
    )

    if not provider_is_live:
        reasons.append("provider_not_live")

    if not schema_validated:
        reasons.append("schema_not_validated")

    if not local_rules_passed:
        reasons.append("local_rules_failed")

    allowed = not reasons
    recommended_status = (
        TERMINOLOGY_STATUS_AUTO_APPROVED
        if allowed
        else _non_auto_status_for_reasons(reasons)
    )

    return {
        "allowed": allowed,
        "recommended_status": recommended_status,
        "reasons": reasons,
        "thresholds": {
            "confidence_score": AUTO_APPROVAL_CONFIDENCE_THRESHOLD,
            "term_quality_score": AUTO_APPROVAL_COMPONENT_THRESHOLD,
            "english_evidence_score": AUTO_APPROVAL_COMPONENT_THRESHOLD,
            "chinese_evidence_score": AUTO_APPROVAL_COMPONENT_THRESHOLD,
        },
    }
