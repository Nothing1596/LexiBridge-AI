import inspect

from scripts import pilot_readiness_check


EXPECTED_CONDITIONS = {
    "FORMAL_BACKGROUND_JOB_LEASE_FOUNDATION_PRESENT",
    "FORMAL_BACKGROUND_JOB_HANDLER_NOT_IMPLEMENTED",
    "FORMAL_PROCESSING_ORCHESTRATOR_NOT_IMPLEMENTED",
    "POSTGRESQL_LEASE_SEMANTICS_NOT_VERIFIED",
}


def test_small_pilot_readiness_exposes_formal_job_ownership_conditions():
    conditions = set(pilot_readiness_check.default_conditions("small-pilot"))
    assert EXPECTED_CONDITIONS <= conditions


def test_readiness_runs_explicit_formal_job_ownership_gate():
    source = inspect.getsource(pilot_readiness_check.main)
    assert "formal background job execution ownership" in source
    assert "tests/test_formal_background_job_execution.py" in source
    assert "tests/test_formal_background_job_concurrency.py" in source
