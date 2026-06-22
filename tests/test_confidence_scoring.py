from services.confidence import (
    auto_approval_block_reasons,
    calculate_confidence_score,
    normalize_percent_score,
    passes_auto_approval_hard_blockers,
    risk_penalty_from_flags,
)


def test_confidence_formula_uses_documented_weights():
    result = calculate_confidence_score(
        term_quality_score=0.8,
        english_evidence_score=0.9,
        chinese_evidence_score=0.7,
        ai_alignment_score=0.6,
        course_scope_score=1.0,
        source_quality_score=0.8,
        risk_penalty=0.1,
    )

    assert result["confidence_score"] == 68.0
    assert result["normalized_confidence_score"] == 0.68
    assert result["risk_penalty"] == 0.1
    assert result["risk_penalty_points"] == 10.0
    assert result["score_breakdown"]["scoring_version"] == "confidence_v1"
    assert result["score_breakdown"]["weighted_components"] == {
        "term_quality_score": 0.2,
        "english_evidence_score": 0.225,
        "chinese_evidence_score": 0.175,
        "ai_alignment_score": 0.09,
        "course_scope_score": 0.05,
        "source_quality_score": 0.04,
    }


def test_confidence_score_clamps_invalid_or_out_of_range_inputs():
    high = calculate_confidence_score(
        term_quality_score=2,
        english_evidence_score=2,
        chinese_evidence_score=2,
        ai_alignment_score=2,
        course_scope_score=2,
        source_quality_score=2,
        risk_penalty=-1,
    )
    low = calculate_confidence_score(
        term_quality_score="bad",
        english_evidence_score=None,
        chinese_evidence_score=-5,
        ai_alignment_score=0,
        risk_penalty=2,
    )

    assert high["confidence_score"] == 100.0
    assert high["normalized_confidence_score"] == 1.0
    assert low["confidence_score"] == 0.0
    assert low["normalized_confidence_score"] == 0.0


def test_confidence_score_accepts_documented_penalty_points():
    result = calculate_confidence_score(
        term_quality_score=0.8,
        english_evidence_score=0.9,
        chinese_evidence_score=0.7,
        ai_alignment_score=0.6,
        course_scope_score=1.0,
        source_quality_score=0.8,
        risk_penalty=40,
    )

    assert result["risk_penalty"] == 0.4
    assert result["risk_penalty_points"] == 40.0
    assert result["normalized_confidence_score"] == 0.38
    assert result["confidence_score"] == 38.0


def test_percent_score_normalization_supports_current_term_confidence_scale():
    assert normalize_percent_score(95) == 0.95
    assert normalize_percent_score("80") == 0.8
    assert normalize_percent_score(0.72) == 0.72
    assert normalize_percent_score("bad") == 0.0


def test_risk_penalty_from_flags_converts_points_to_normalized_penalty():
    result = risk_penalty_from_flags(
        risk_flags=["no_zh_evidence", "domain_mismatch"],
        provider="mock",
    )

    assert result["risk_penalty"] == 1.0
    assert result["risk_penalty_points"] == 100
    assert result["risk_flags"] == [
        "domain_mismatch",
        "mock_or_local_ai",
        "no_zh_evidence",
    ]


def test_auto_approval_blocks_mock_local_and_rule_based_providers():
    for provider in ["mock", "local_heuristic", "rule_based"]:
        reasons = auto_approval_block_reasons(
            provider=provider,
            english_evidence_score=0.9,
            chinese_evidence_score=0.9,
        )

        assert "provider_not_trusted_for_auto_approval" in reasons
        assert not passes_auto_approval_hard_blockers(
            provider=provider,
            english_evidence_score=0.9,
            chinese_evidence_score=0.9,
        )


def test_auto_approval_blocks_missing_evidence_and_risk_flags():
    reasons = auto_approval_block_reasons(
        provider="openai",
        risk_flags=["ocr_low_confidence", "domain_mismatch"],
        english_evidence_score=0,
        chinese_evidence_score=0.8,
    )

    assert reasons == [
        "no_en_evidence",
        "ocr_low_confidence",
        "domain_mismatch",
    ]


def test_auto_approval_blocks_invalid_term_and_multi_translation_conflict():
    reasons = auto_approval_block_reasons(
        provider="openai",
        risk_flags=["invalid_term_candidate", "multi_translation_conflict"],
        english_evidence_score=0.9,
        chinese_evidence_score=0.9,
    )

    assert reasons == ["invalid_term_candidate", "multi_translation_conflict"]


def test_passes_auto_approval_hard_blockers_is_necessary_not_sufficient():
    assert passes_auto_approval_hard_blockers(
        provider="openai",
        risk_flags=[],
        english_evidence_score=0.85,
        chinese_evidence_score=0.82,
    )
