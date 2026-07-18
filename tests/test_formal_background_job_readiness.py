import inspect

from scripts import pilot_readiness_check


EXPECTED_CONDITIONS = {
    "FORMAL_BACKGROUND_JOB_LEASE_FOUNDATION_PRESENT",
    "FORMAL_CHUNK_SCOPED_TERM_CANDIDATES_PRESENT",
    "FORMAL_WORKFLOW_ITEM_BOOTSTRAP_PRESENT",
    "FORMAL_BOOTSTRAP_LEASE_FENCING_PRESENT",
    "FORMAL_VERIFICATION_TRANSACTION_ADAPTER_NOT_IMPLEMENTED",
    "POSTGRESQL_BOOTSTRAP_TRANSACTION_NOT_VERIFIED",
    "FORMAL_BACKGROUND_JOB_HANDLER_NOT_IMPLEMENTED",
    "FORMAL_PROCESSING_ORCHESTRATOR_NOT_IMPLEMENTED",
    "POSTGRESQL_LEASE_SEMANTICS_NOT_VERIFIED",
    "FORMAL_ITEM_EXECUTION_IDENTITY_SCHEMA_PRESENT",
    "FORMAL_VERIFICATION_EXECUTION_KEY_UNIQUENESS_PRESENT",
    "FORMAL_PREFLIGHT_EXECUTION_KEY_UNIQUENESS_PRESENT",
    "FORMAL_USAGE_EXECUTION_KEY_UNIQUENESS_PRESENT",
    "FORMAL_AUDIT_EVENT_IDENTITY_UNIQUENESS_PRESENT",
    "FORMAL_ITEM_VERIFICATION_ADAPTER_NOT_IMPLEMENTED",
    "POSTGRESQL_IDEMPOTENCY_CONSTRAINTS_NOT_VERIFIED",
    "FORMAL_MIGRATION_FRAMEWORK_NOT_ESTABLISHED",
}


def test_small_pilot_readiness_exposes_formal_job_ownership_conditions():
    conditions = set(pilot_readiness_check.default_conditions("small-pilot"))
    assert EXPECTED_CONDITIONS <= conditions


def test_readiness_runs_explicit_formal_job_ownership_gate():
    source = inspect.getsource(pilot_readiness_check.main)
    assert "formal background job execution ownership" in source
    assert "tests/test_formal_background_job_execution.py" in source
    assert "tests/test_formal_background_job_concurrency.py" in source
    assert "formal document alignment item bootstrap" in source
    assert "tests/test_document_alignment_term_candidates.py" in source
    assert "tests/test_document_alignment_item_bootstrap.py" in source
    assert "tests/test_document_alignment_item_bootstrap_integration.py" in source
    assert "formal item execution idempotency schema" in source
    assert "tests/test_formal_item_verification_execution_models.py" in source
    assert "tests/test_formal_item_idempotency_constraints.py" in source
    assert "tests/test_formal_item_execution_schema_upgrade.py" in source
