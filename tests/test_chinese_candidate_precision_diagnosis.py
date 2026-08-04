import json

from scripts.evaluations import chinese_candidate_precision_diagnosis as diagnosis
from scripts.evaluations.bilingual_knowledge_quality import dataset


def _trace(**overrides):
    values = {
        "source_term_present": True,
        "parsed_text_term_present": True,
        "chunk_term_present": True,
        "retrieval_rank": 1,
        "candidate_count": 1,
        "exact_candidate_rank": 1,
        "alias_candidate_rank": None,
        "boundary_defect_present": False,
        "fragmentation_present": False,
        "normalization_defect_present": False,
        "selected_candidate_correct": True,
        "pair_correct": True,
        "readiness_status": "prepared",
        "benchmark_alias_gap": False,
        "benchmark_fixture_defect": False,
        "ambiguous": False,
    }
    values.update(overrides)
    return diagnosis.ChineseCandidateTrace(**values)


def test_gold_bearing_chunk_not_retrieved_is_retrieval_miss():
    assert diagnosis.attribute_failure(
        _trace(retrieval_rank=None, candidate_count=0, exact_candidate_rank=None)
    ) == "CHINESE_RETRIEVAL_MISS"


def test_retrieved_chunk_without_exact_or_alias_candidate_is_extraction_missing():
    assert diagnosis.attribute_failure(
        _trace(candidate_count=0, exact_candidate_rank=None)
    ) == "CHINESE_CANDIDATE_EXTRACTION_MISSING"


def test_exact_candidate_below_top_three_is_ranking_defect():
    assert diagnosis.attribute_failure(
        _trace(candidate_count=5, exact_candidate_rank=4)
    ) == "CHINESE_CANDIDATE_RANKING_DEFECT"


def test_benchmark_alias_gap_is_not_attributed_to_production():
    assert diagnosis.attribute_failure(
        _trace(
            exact_candidate_rank=None,
            alias_candidate_rank=1,
            benchmark_alias_gap=True,
        )
    ) == "BENCHMARK_ALIAS_GAP"


def test_frozen_runner_preserves_all_25_rows_and_denominators():
    artifact = diagnosis.run_diagnosis()

    assert len(artifact["rows"]) == 25
    assert artifact["metrics"]["benchmark_coverage"] == "25/25"
    assert artifact["metrics"]["english_exact_matched"] == 25
    assert all(row["included_in_denominator"] is True for row in artifact["rows"])
    assert all(
        subset["denominator"] == 25
        for subset in artifact["survivor_subsets"].values()
    )
    assert artifact["real_provider_requests"] == 0


def test_runner_does_not_modify_frozen_inputs_or_production_contracts():
    before = dataset.dataset_hashes()
    artifact = diagnosis.run_diagnosis()

    assert dataset.dataset_hashes() == before
    assert artifact["frozen_hashes"] == before
    assert artifact["production_files_modified"] == []


def test_artifact_payloads_are_sanitized():
    artifact = diagnosis.run_diagnosis()
    serialized = json.dumps(
        diagnosis.artifact_payloads(artifact),
        ensure_ascii=False,
    )

    for forbidden in (
        "/Users/",
        "DEEPSEEK_API_KEY",
        "Authorization:",
        "Bearer ",
        "Mass measures the amount of matter",
        "电荷（electric charge）是物质产生电相互作用的属性",
    ):
        assert forbidden not in serialized
