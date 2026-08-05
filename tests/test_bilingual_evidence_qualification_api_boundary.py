from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_bilingual_api_cannot_submit_qualification_decision_or_threshold():
    app_text = (ROOT / "backend/app.py").read_text()
    workflow_text = (ROOT / "backend/services/bilingual_evidence_workflow.py").read_text()
    assert 'data.get("qualification_decision")' not in app_text
    assert 'data.get("qualification_score")' not in app_text
    assert 'data.get("qualification_threshold")' not in app_text
    assert 'input_data.get("qualification_threshold")' not in workflow_text


def test_existing_threshold_value_is_not_changed_by_task_12g():
    workflow_text = (ROOT / "backend/services/bilingual_evidence_workflow.py").read_text()
    assert "LOW_EVIDENCE_SCORE_THRESHOLD = 0.35" in workflow_text
