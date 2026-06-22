import pytest
from sqlalchemy.exc import IntegrityError


def test_terminology_card_persists_evidence_snapshots(app_module):
    with app_module.app.app_context():
        card = app_module.TerminologyCard(
            scope_type="course",
            course_id=101,
            english_term="Fourier Transform",
            normalized_english_term="fourier transform",
            final_chinese_term="傅里叶变换",
            normalized_chinese_term="傅里叶变换",
            courseware_sentence="Fourier Transform converts signals into frequencies.",
            english_evidence_chunk_id=1,
            chinese_evidence_chunk_id=2,
            english_evidence_snapshot="Fourier Transform represents frequency components.",
            chinese_evidence_snapshot="傅里叶变换用于将信号表示为频率分量。",
            english_evidence_score=0.92,
            chinese_evidence_score=0.88,
            alignment_status="exact_match",
            confidence_score=91.5,
            status="pending_quality_control",
            ai_provider="openai",
            ai_model="gpt-test",
            prompt_version="alignment-v1",
            score_breakdown_json='{"confidence_score": 91.5}',
            quality_flags_json='[]',
            risk_note="Chinese evidence is course-specific.",
        )

        app_module.db.session.add(card)
        app_module.db.session.commit()

        loaded = app_module.TerminologyCard.query.one()

        assert loaded.english_evidence_snapshot.startswith("Fourier Transform")
        assert loaded.chinese_evidence_snapshot.startswith("傅里叶变换")
        assert loaded.confidence_score == pytest.approx(91.5)
        assert loaded.feedback_count == 0
        assert loaded.created_at is not None
        assert loaded.updated_at is not None


def test_terminology_card_course_scope_unique_constraint(app_module):
    with app_module.app.app_context():
        first = app_module.TerminologyCard(
            scope_type="course",
            course_id=101,
            english_term="Hash Table",
            normalized_english_term="hash table",
        )
        duplicate = app_module.TerminologyCard(
            scope_type="course",
            course_id=101,
            english_term="Hash table",
            normalized_english_term="hash table",
        )

        app_module.db.session.add(first)
        app_module.db.session.commit()
        app_module.db.session.add(duplicate)

        with pytest.raises(IntegrityError):
            app_module.db.session.commit()

        app_module.db.session.rollback()
