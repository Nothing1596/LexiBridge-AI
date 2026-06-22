CONFIDENCE_SCORING_VERSION = "confidence_v1"

CONFIDENCE_WEIGHTS = {
    "term_quality_score": 0.25,
    "english_evidence_score": 0.25,
    "chinese_evidence_score": 0.25,
    "ai_alignment_score": 0.15,
    "course_scope_score": 0.05,
    "source_quality_score": 0.05,
}

AUTO_APPROVAL_BLOCKING_FLAGS = (
    "no_zh_evidence",
    "no_en_evidence",
    "ocr_low_confidence",
    "domain_mismatch",
)

AUTO_APPROVAL_BLOCKING_PROVIDERS = {
    "mock",
    "local_heuristic",
    "rule_based",
}


def clamp_score(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, min(1.0, score))


def normalize_percent_score(value):
    """
    Convert current 0-100 style confidence values into the v1.0 0-1 contract.
    Values already in 0-1 form are preserved.
    """
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return 0.0

    if numeric_value > 1:
        return round(clamp_score(numeric_value / 100), 3)

    return round(clamp_score(numeric_value), 3)


def calculate_confidence_score(
    *,
    term_quality_score,
    english_evidence_score,
    chinese_evidence_score,
    ai_alignment_score,
    course_scope_score=0,
    source_quality_score=0,
    risk_penalty=0,
):
    """
    Apply the documented v1.0 confidence formula using normalized 0-1 inputs.
    """
    normalized_scores = {
        "term_quality_score": clamp_score(term_quality_score),
        "english_evidence_score": clamp_score(english_evidence_score),
        "chinese_evidence_score": clamp_score(chinese_evidence_score),
        "ai_alignment_score": clamp_score(ai_alignment_score),
        "course_scope_score": clamp_score(course_scope_score),
        "source_quality_score": clamp_score(source_quality_score),
    }
    normalized_risk_penalty = clamp_score(risk_penalty)

    weighted_components = {
        key: round(normalized_scores[key] * weight, 4)
        for key, weight in CONFIDENCE_WEIGHTS.items()
    }
    raw_score = sum(weighted_components.values()) - normalized_risk_penalty
    confidence_score = round(clamp_score(raw_score), 3)

    return {
        "confidence_score": confidence_score,
        "risk_penalty": normalized_risk_penalty,
        "score_breakdown": {
            "scoring_version": CONFIDENCE_SCORING_VERSION,
            "weights": CONFIDENCE_WEIGHTS.copy(),
            "inputs": normalized_scores,
            "weighted_components": weighted_components,
        },
    }


def auto_approval_block_reasons(
    *,
    provider,
    risk_flags=None,
    english_evidence_score=0,
    chinese_evidence_score=0,
):
    """
    Return documented hard blockers for auto approval.

    This intentionally does not choose an auto-approval confidence threshold.
    Threshold policy belongs with the later TerminologyCard state machine work.
    """
    reasons = []
    normalized_provider = (provider or "").strip().lower()
    normalized_flags = {
        str(flag).strip().lower()
        for flag in (risk_flags or [])
        if str(flag).strip()
    }

    if normalized_provider in AUTO_APPROVAL_BLOCKING_PROVIDERS:
        reasons.append("provider_not_trusted_for_auto_approval")

    if clamp_score(english_evidence_score) <= 0:
        normalized_flags.add("no_en_evidence")

    if clamp_score(chinese_evidence_score) <= 0:
        normalized_flags.add("no_zh_evidence")

    for flag in AUTO_APPROVAL_BLOCKING_FLAGS:
        if flag in normalized_flags:
            reasons.append(flag)

    return reasons


def is_auto_approval_allowed(**kwargs):
    return not auto_approval_block_reasons(**kwargs)
