import inspect

from scripts import pilot_readiness_check


EXPECTED_CONDITIONS = {
    "FORMAL_BACKGROUND_JOB_LEASE_FOUNDATION_PRESENT",
    "FORMAL_CHUNK_SCOPED_TERM_CANDIDATES_PRESENT",
    "FORMAL_WORKFLOW_ITEM_BOOTSTRAP_PRESENT",
    "FORMAL_BOOTSTRAP_LEASE_FENCING_PRESENT",
    "FORMAL_ITEM_VERIFICATION_ADAPTER_PRESENT",
    "FORMAL_ITEM_EXECUTION_MAPPING_USED",
    "FORMAL_PROVIDER_PREFLIGHT_ENFORCED",
    "FORMAL_VERIFICATION_EXECUTION_REUSE_PRESENT",
    "FORMAL_USAGE_EXECUTION_IDENTITY_ENFORCED",
    "FORMAL_AUDIT_EVENT_IDENTITY_ENFORCED",
    "FORMAL_APPROVED_CARD_PROTECTION_PRESENT",
    "FORMAL_EVIDENCE_PERSISTENCE_MINIMIZED",
    "POSTGRESQL_ITEM_ADAPTER_NOT_VERIFIED",
    "POSTGRESQL_BOOTSTRAP_TRANSACTION_NOT_VERIFIED",
    "FORMAL_DOCUMENT_PROCESSING_ORCHESTRATOR_PRESENT",
    "FORMAL_ITEM_PREPARATION_COMPOSITION_PRESENT",
    "FORMAL_ROOT_PROGRESS_RECALCULATION_PRESENT",
    "FORMAL_ROOT_FINALIZATION_PRESENT",
    "FORMAL_ROOT_AUDIT_IDEMPOTENCY_PRESENT",
    "FORMAL_PROCESSING_PARTIAL_FAILURE_PRESENT",
    "FORMAL_PROCESSING_RESUME_PRESENT",
    "FORMAL_DOCUMENT_ALIGNMENT_WORKER_HANDLER_PRESENT",
    "FORMAL_DOCUMENT_ALIGNMENT_JOB_DISPATCH_PRESENT",
    "FORMAL_WORKER_RESULT_MAPPING_PRESENT",
    "FORMAL_WORKER_RETRY_MAPPING_PRESENT",
    "FORMAL_WORKER_STALE_RECOVERY_PRESENT",
    "FORMAL_ROOT_JOB_TERMINAL_CONSISTENCY_PRESENT",
    "FORMAL_JOB_NO_LEGACY_DISPATCH_PRESENT",
    "FORMAL_QUERY_SERVICE_NOT_IMPLEMENTED",
    "FORMAL_ROUTES_NOT_IMPLEMENTED",
    "FRONTEND_NOT_MIGRATED",
    "POSTGRESQL_PROCESSING_NOT_VERIFIED",
    "POSTGRESQL_LEASE_SEMANTICS_NOT_VERIFIED",
    "POSTGRESQL_WORKER_NOT_VERIFIED",
    "PRODUCTION_WORKER_RUNTIME_NOT_ESTABLISHED",
    "FORMAL_ITEM_EXECUTION_IDENTITY_SCHEMA_PRESENT",
    "FORMAL_VERIFICATION_EXECUTION_KEY_UNIQUENESS_PRESENT",
    "FORMAL_PREFLIGHT_EXECUTION_KEY_UNIQUENESS_PRESENT",
    "FORMAL_USAGE_EXECUTION_KEY_UNIQUENESS_PRESENT",
    "FORMAL_AUDIT_EVENT_IDENTITY_UNIQUENESS_PRESENT",
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
    assert "formal item verification transaction adapter" in source
    assert "tests/test_document_alignment_item_verification_adapter.py" in source
    assert "tests/test_document_alignment_item_verification_adapter_integration.py" in source
    assert "tests/test_document_alignment_item_verification_idempotency.py" in source
    assert "tests/test_document_alignment_item_verification_security.py" in source
    assert "tests/test_document_alignment_item_verification_fault_recovery.py" in source
    assert "formal document alignment processing orchestrator" in source
    assert "tests/test_document_alignment_processing_orchestrator.py" in source
    assert "tests/test_document_alignment_processing_orchestrator_integration.py" in source
    assert "tests/test_document_alignment_processing_partial_failure.py" in source
    assert "tests/test_document_alignment_processing_resume.py" in source
    assert "tests/test_document_alignment_processing_concurrency.py" in source
    assert "tests/test_document_alignment_processing_security.py" in source
    assert "tests/test_document_alignment_processing_fault_recovery.py" in source
    assert "formal document alignment worker handler" in source
    assert "tests/test_document_alignment_worker_handler.py" in source
    assert "tests/test_document_alignment_worker_result_mapping.py" in source
    assert "tests/test_document_alignment_worker_integration.py" in source
    assert "tests/test_document_alignment_worker_retry_recovery.py" in source
    assert "tests/test_document_alignment_worker_concurrency.py" in source
    assert "tests/test_document_alignment_worker_legacy_compatibility.py" in source
    assert "tests/test_document_alignment_worker_security.py" in source
