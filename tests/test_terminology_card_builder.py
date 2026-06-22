import json

import pytest

from services.terminology_card_builder import build_terminology_card_payload


def _payload(**overrides):
    values = {
        "scope_type": "course",
        "course_id": 101,
        "english_term": "Fourier Transform",
        "final_chinese_term": "傅里叶变换",
        "courseware_sentence": "Fourier Transform converts signals into frequencies.",
        "english_evidence_chunk_id": 1,
        "chinese_evidence_chunk_id": 2,
        "english_evidence_snapshot": "Fourier Transform represents frequency components.",
        "chinese_evidence_snapshot": "傅里叶变换用于将信号表示为频率分量。",
        "english_evidence_score": 0.92,
        "chinese_evidence_score": 0.9,
        "term_quality_score": 0.9,
        "ai_alignment_score": 0.88,
        "course_scope_score": 1.0,
        "source_quality_score": 0.9,
        "alignment_status": "exact_match",
        "provider": "openai",
        "provider_is_live": True,
        "ai_model": "gpt-test",
        "prompt_version": "alignment-v1",
        "schema_validated": True,
        "local_rules_passed": True,
        "risk_flags": [],
        "quality_flags": [],
    }
    values.update(overrides)
    return build_terminology_card_payload(**values)


def test_builds_auto_approved_card_payload_for_strong_live_evidence():
    payload = _payload()
    score_breakdown = json.loads(payload["score_breakdown_json"])
    quality_flags = json.loads(payload["quality_flags_json"])

    assert payload["normalized_english_term"] == "fourier transform"
    assert payload["normalized_chinese_term"] == "傅里叶变换"
    assert payload["confidence_score"] >= 85
    assert payload["status"] == "auto_approved"
    assert payload["risk_note"] is None
    assert quality_flags == []
    assert score_breakdown["auto_approval_gate"]["allowed"] is True


def test_missing_chinese_evidence_becomes_needs_more_evidence_with_penalty():
    payload = _payload(
        chinese_evidence_chunk_id=None,
        chinese_evidence_snapshot=None,
        chinese_evidence_score=0,
    )
    score_breakdown = json.loads(payload["score_breakdown_json"])
    quality_flags = json.loads(payload["quality_flags_json"])

    assert payload["status"] == "needs_more_evidence"
    assert payload["confidence_score"] < 85
    assert "no_zh_evidence" in quality_flags
    assert score_breakdown["risk"]["risk_penalty_points"] == 40
    assert "no_zh_evidence" in score_breakdown["auto_approval_gate"]["reasons"]


def test_mock_provider_is_marked_for_qc_not_auto_approved():
    payload = _payload(provider="mock", provider_is_live=False)
    quality_flags = json.loads(payload["quality_flags_json"])
    gate = json.loads(payload["score_breakdown_json"])["auto_approval_gate"]

    assert payload["status"] == "pending_quality_control"
    assert "mock_or_local_ai" in quality_flags
    assert "provider_not_trusted_for_auto_approval" in gate["reasons"]
    assert "provider_not_live" in gate["reasons"]


def test_domain_mismatch_routes_to_quality_control_not_conflict():
    payload = _payload(risk_flags=["domain_mismatch"])
    gate = json.loads(payload["score_breakdown_json"])["auto_approval_gate"]

    assert payload["status"] == "pending_quality_control"
    assert "domain_mismatch" in gate["reasons"]


def test_multi_translation_conflict_routes_to_conflict_detected():
    payload = _payload(risk_flags=["multi_translation_conflict"])

    assert payload["status"] == "conflict_detected"


def test_payload_can_be_persisted_as_terminology_card(app_module):
    payload = _payload()

    with app_module.app.app_context():
        card = app_module.TerminologyCard(**payload)
        app_module.db.session.add(card)
        app_module.db.session.commit()

        loaded = app_module.TerminologyCard.query.one()

        assert loaded.status == "auto_approved"
        assert loaded.normalized_english_term == "fourier transform"
        assert loaded.english_evidence_snapshot.startswith("Fourier Transform")


def test_builder_rejects_missing_course_scope_key():
    with pytest.raises(ValueError, match="course_id"):
        _payload(course_id=None)


def test_builder_rejects_missing_personal_scope_keys():
    with pytest.raises(ValueError, match="owner_user_id"):
        _payload(scope_type="personal", course_id=None)

    with pytest.raises(ValueError, match="source_document_id"):
        _payload(
            scope_type="personal",
            course_id=None,
            owner_user_id=7,
            source_document_id=None,
        )


def test_builder_rejects_empty_english_term():
    with pytest.raises(ValueError, match="english_term"):
        _payload(english_term=" ")
