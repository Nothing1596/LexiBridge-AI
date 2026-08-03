from scripts.evaluations.bilingual_knowledge_quality import runner


def test_per_item_continuation_keeps_not_ready_in_denominator_and_reuses_preflight():
    readiness = (
        runner.FormalProviderReadiness(
            "physics-07",
            False,
            "evidence_insufficient",
            rejection_code="DOCUMENT_ALIGNMENT_EVIDENCE_INSUFFICIENT",
        ),
        runner.FormalProviderReadiness("physics-21", True, "prepared"),
        runner.FormalProviderReadiness("physics-22", True, "prepared"),
    )
    calls = []
    preflight = {"concept_id": "physics-21", "status": "provider_success", "request_count": 1}

    results = runner.continue_real_provider_evaluation(
        ("physics-07", "physics-21", "physics-22"),
        readiness,
        preflight_result=preflight,
        execute_ready_item=lambda concept_id: calls.append(concept_id)
        or {"concept_id": concept_id, "status": "provider_success", "request_count": 1},
        upstream_attribution=lambda concept_id, row: "ENGLISH_RETRIEVAL_DEFECT",
    )

    assert [row["status"] for row in results] == [
        "upstream_not_ready",
        "provider_success",
        "provider_success",
    ]
    assert results[0]["provider_called"] is False
    assert results[0]["primary_attribution"] == "ENGLISH_RETRIEVAL_DEFECT"
    assert results[1]["reused_preflight"] is True
    assert calls == ["physics-22"]
    assert len(results) == 3


def test_systemic_provider_failure_stops_later_calls():
    readiness = (
        runner.FormalProviderReadiness("physics-21", True, "prepared"),
        runner.FormalProviderReadiness("physics-22", True, "prepared"),
    )
    calls = []

    def execute(concept_id):
        calls.append(concept_id)
        return {
            "concept_id": concept_id,
            "status": "provider_failure",
            "error_category": "authentication_failed",
            "systemic": True,
            "request_count": 1,
        }

    results = runner.continue_real_provider_evaluation(
        ("physics-21", "physics-22"),
        readiness,
        preflight_result=None,
        execute_ready_item=execute,
        upstream_attribution=lambda concept_id, row: "",
    )

    assert calls == ["physics-21"]
    assert len(results) == 1
    assert results[0]["status"] == "provider_failure"
