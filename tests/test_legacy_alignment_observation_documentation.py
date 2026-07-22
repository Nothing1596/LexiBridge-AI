from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_observation_report_is_honest_about_incomplete_target_window():
    report = (ROOT / "docs" / "legacy_alignment_observation_report.md").read_text(
        encoding="utf-8"
    )
    for expected in (
        "OBSERVATION_WINDOW_PENDING",
        "PENDING_TARGET_DEPLOYMENT",
        "Actual target-environment active days: `0`",
        "UNKNOWN_EXTERNAL_LEGACY_CONSUMER",
        "FORMAL_ONLY_RUNTIME_CONFIRMED",
        "LEGACY_ALIGNMENT_410_NOT_AUTHORIZED",
    ):
        assert expected in report
    assert "LEGACY_ALIGNMENT_DEPRECATION_OBSERVATION_COMPLETE" not in report
    assert "LEGACY_ALIGNMENT_410_READY" not in report


def test_rollback_procedure_requires_named_owner_and_restarts_window():
    procedure = (ROOT / "docs" / "legacy_alignment_rollback_procedure.md").read_text(
        encoding="utf-8"
    )
    for expected in (
        "PENDING_TARGET_ENVIRONMENT_ASSIGNMENT",
        "LEGACY_ALIGNMENT_RUNTIME_STATE=freeze",
        "LEGACY_ALIGNMENT_RUNTIME_STATE=active",
        "LEGACY_ALIGNMENT_ROUTE_ADMISSION_ENABLED=true",
        "restart the full observation window",
        "LEGACY_ALIGNMENT_ROLLBACK_REHEARSAL_PASS",
    ):
        assert expected in procedure


def test_openapi_keeps_deprecated_legacy_operation_and_pending_window_note():
    text = (ROOT / "docs" / "openapi.yaml").read_text(encoding="utf-8")
    operation = text.split("  /api/alignment/run:", 1)[1].split(
        "\n  /api/alignment/runs:", 1
    )[0]
    assert "deprecated: true" in operation
    assert "14 continuous days" in operation
    assert "five operating days" in operation
    assert '"410"' not in operation
