from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_observation_report_is_honest_about_incomplete_target_window():
    report = (ROOT / "docs" / "legacy_alignment_observation_report.md").read_text(
        encoding="utf-8"
    )
    for expected in (
        "OBSERVATION_WINDOW_PENDING",
        "pilot-internal-local",
        "PENDING_OBSERVATION_START",
        "LEGACY_ALIGNMENT_OBSERVATION_ENVIRONMENT_READY",
        "Actual target-environment active days: `0`",
        "UNKNOWN_EXTERNAL_LEGACY_CONSUMER",
        "FORMAL_ONLY_RUNTIME_CONFIRMED",
        "LEGACY_ALIGNMENT_410_NOT_AUTHORIZED",
    ):
        assert expected in report
    assert "LEGACY_ALIGNMENT_DEPRECATION_OBSERVATION_COMPLETE" not in report
    assert "LEGACY_ALIGNMENT_410_READY" not in report


def test_rollback_procedure_names_owner_and_restarts_window():
    procedure = (ROOT / "docs" / "legacy_alignment_rollback_procedure.md").read_text(
        encoding="utf-8"
    )
    for expected in (
        "pilot-internal-local",
        "Rollback owner: Project Maintainer",
        "OBSERVATION_WINDOW_PENDING_START",
        "LEGACY_ALIGNMENT_RUNTIME_STATE=freeze",
        "LEGACY_ALIGNMENT_RUNTIME_STATE=active",
        "LEGACY_ALIGNMENT_ROUTE_ADMISSION_ENABLED=true",
        "restart the full observation window",
        "LEGACY_ALIGNMENT_ROLLBACK_REHEARSAL_PASS",
    ):
        assert expected in procedure


def test_pilot_environment_declares_runtime_evidence_without_starting_window():
    declaration = (ROOT / "docs" / "pilot_environment_declaration.md").read_text(
        encoding="utf-8"
    )
    for expected in (
        "pilot-internal-local",
        "f04c32c38423192a3088bf32151ae51127eb3b3f",
        "project-root/backend/lexibridge.db",
        "pilot-internal-formal-1",
        "pilot-internal-legacy-1",
        "Observation owner | Project Maintainer",
        "Gateway/reverse-proxy logs | none | `NOT_AVAILABLE`",
        "## Metric Availability Matrix",
        "EXTERNAL_CONSUMER_VISIBILITY_LIMITED",
        "OBSERVATION_WINDOW_PENDING_START",
    ):
        assert expected in declaration
    assert "LEGACY_ALIGNMENT_OBSERVATION_WINDOW_ACTIVE" not in declaration
    assert "LEGACY_ALIGNMENT_410_READY" not in declaration


def test_snapshot_procedure_covers_legacy_and_formal_state_without_live_restore():
    procedure = (ROOT / "docs" / "pilot_database_snapshot_procedure.md").read_text(
        encoding="utf-8"
    )
    for expected in (
        "alignment_run",
        "background_job",
        "background_job_event",
        "document_alignment_workflow_runs",
        "scripts/pilot_backup.py",
        "scripts/verify_pilot_backup.py",
        "scripts/pilot_restore.py",
        "Never use `--force` against the declared live source",
    ):
        assert expected in procedure


def test_migration_notice_is_ready_for_distribution_but_not_retirement():
    notice = (ROOT / "docs" / "legacy_alignment_migration_notice.md").read_text(
        encoding="utf-8"
    )
    for expected in (
        "READY_FOR_DISTRIBUTION",
        "pilot-internal-local",
        "Project Maintainer",
        "PENDING_OBSERVATION_START",
    ):
        assert expected in notice
    assert "Legacy API is already gone" in notice
    assert "LEGACY_ALIGNMENT_OBSERVATION_WINDOW_ACTIVE" not in notice
    assert "LEGACY_ALIGNMENT_410_READY" not in notice


def test_openapi_keeps_deprecated_legacy_operation_and_pending_window_note():
    text = (ROOT / "docs" / "openapi.yaml").read_text(encoding="utf-8")
    operation = text.split("  /api/alignment/run:", 1)[1].split(
        "\n  /api/alignment/runs:", 1
    )[0]
    assert "deprecated: true" in operation
    assert "14 continuous days" in operation
    assert "five operating days" in operation
    assert '"410"' not in operation
