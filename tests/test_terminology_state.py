from services.terminology_state import (
    TERMINOLOGY_STATUS_APPROVED,
    TERMINOLOGY_STATUS_ARCHIVED,
    TERMINOLOGY_STATUS_AUTO_APPROVED,
    TERMINOLOGY_STATUS_CONFLICT_DETECTED,
    TERMINOLOGY_STATUS_DRAFT,
    TERMINOLOGY_STATUS_NEEDS_MORE_EVIDENCE,
    TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL,
    TERMINOLOGY_STATUS_REJECTED,
    can_transition,
    evaluate_auto_approval_gate,
    is_valid_status,
    validate_status_transition,
)


def _gate(**overrides):
    values = {
        "confidence_score": 88,
        "term_quality_score": 0.86,
        "english_evidence_score": 0.84,
        "chinese_evidence_score": 0.83,
        "provider": "openai",
        "provider_is_live": True,
        "schema_validated": True,
        "local_rules_passed": True,
        "risk_flags": [],
    }
    values.update(overrides)
    return evaluate_auto_approval_gate(**values)


def test_documented_status_transitions_are_allowed():
    allowed_pairs = [
        (TERMINOLOGY_STATUS_DRAFT, TERMINOLOGY_STATUS_NEEDS_MORE_EVIDENCE),
        (TERMINOLOGY_STATUS_DRAFT, TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL),
        (TERMINOLOGY_STATUS_DRAFT, TERMINOLOGY_STATUS_CONFLICT_DETECTED),
        (TERMINOLOGY_STATUS_DRAFT, TERMINOLOGY_STATUS_AUTO_APPROVED),
        (
            TERMINOLOGY_STATUS_NEEDS_MORE_EVIDENCE,
            TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL,
        ),
        (TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL, TERMINOLOGY_STATUS_APPROVED),
        (TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL, TERMINOLOGY_STATUS_REJECTED),
        (
            TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL,
            TERMINOLOGY_STATUS_NEEDS_MORE_EVIDENCE,
        ),
        (TERMINOLOGY_STATUS_CONFLICT_DETECTED, TERMINOLOGY_STATUS_APPROVED),
        (TERMINOLOGY_STATUS_CONFLICT_DETECTED, TERMINOLOGY_STATUS_REJECTED),
        (TERMINOLOGY_STATUS_AUTO_APPROVED, TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL),
        (TERMINOLOGY_STATUS_APPROVED, TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL),
        (TERMINOLOGY_STATUS_APPROVED, TERMINOLOGY_STATUS_ARCHIVED),
        (TERMINOLOGY_STATUS_REJECTED, TERMINOLOGY_STATUS_ARCHIVED),
    ]

    for from_status, to_status in allowed_pairs:
        assert can_transition(from_status, to_status)


def test_invalid_or_forbidden_status_transitions_are_rejected():
    assert not can_transition(
        TERMINOLOGY_STATUS_REJECTED,
        TERMINOLOGY_STATUS_AUTO_APPROVED,
    )
    assert not can_transition(TERMINOLOGY_STATUS_ARCHIVED, TERMINOLOGY_STATUS_APPROVED)
    assert not can_transition("unknown", TERMINOLOGY_STATUS_APPROVED)
    assert not is_valid_status("unknown")

    result = validate_status_transition(
        TERMINOLOGY_STATUS_REJECTED,
        TERMINOLOGY_STATUS_AUTO_APPROVED,
    )

    assert result == {
        "allowed": False,
        "from_status": TERMINOLOGY_STATUS_REJECTED,
        "to_status": TERMINOLOGY_STATUS_AUTO_APPROVED,
    }


def test_auto_approval_gate_passes_when_all_documented_conditions_pass():
    result = _gate()

    assert result["allowed"] is True
    assert result["recommended_status"] == TERMINOLOGY_STATUS_AUTO_APPROVED
    assert result["reasons"] == []


def test_auto_approval_gate_blocks_low_confidence_and_returns_qc_status():
    result = _gate(confidence_score=84.9)

    assert result["allowed"] is False
    assert result["recommended_status"] == TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL
    assert result["reasons"] == ["confidence_below_threshold"]


def test_auto_approval_gate_blocks_weak_but_nonzero_evidence():
    result = _gate(chinese_evidence_score=0.79)

    assert result["allowed"] is False
    assert result["recommended_status"] == TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL
    assert result["reasons"] == ["chinese_evidence_below_threshold"]


def test_auto_approval_gate_routes_missing_evidence_to_needs_more_evidence():
    result = _gate(english_evidence_score=0)

    assert result["allowed"] is False
    assert result["recommended_status"] == TERMINOLOGY_STATUS_NEEDS_MORE_EVIDENCE
    assert result["reasons"] == [
        "no_en_evidence",
        "english_evidence_below_threshold",
    ]


def test_auto_approval_gate_routes_conflicts_to_conflict_detected():
    result = _gate(risk_flags=["multi_translation_conflict"])

    assert result["allowed"] is False
    assert result["recommended_status"] == TERMINOLOGY_STATUS_CONFLICT_DETECTED
    assert result["reasons"] == ["multi_translation_conflict"]


def test_auto_approval_gate_routes_domain_mismatch_to_quality_control():
    result = _gate(risk_flags=["domain_mismatch"])

    assert result["allowed"] is False
    assert result["recommended_status"] == TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL
    assert result["reasons"] == ["domain_mismatch"]


def test_auto_approval_gate_blocks_untrusted_or_non_live_provider():
    result = _gate(provider="rule_based", provider_is_live=False)

    assert result["allowed"] is False
    assert result["recommended_status"] == TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL
    assert result["reasons"] == [
        "provider_not_trusted_for_auto_approval",
        "provider_not_live",
    ]


def test_auto_approval_gate_blocks_schema_and_local_rule_failures():
    result = _gate(schema_validated=False, local_rules_passed=False)

    assert result["allowed"] is False
    assert result["recommended_status"] == TERMINOLOGY_STATUS_PENDING_QUALITY_CONTROL
    assert result["reasons"] == ["schema_not_validated", "local_rules_failed"]
