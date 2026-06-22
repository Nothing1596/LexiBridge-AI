import os
import sqlite3
import subprocess
import sys

from conftest import BACKEND_DIR, PROJECT_ROOT


def test_database_migrations_upgrade_empty_sqlite(tmp_path):
    database_path = tmp_path / "lexibridge-migration.db"
    upload_folder = tmp_path / "uploads"

    pythonpath = str(BACKEND_DIR)
    if os.environ.get("PYTHONPATH"):
        pythonpath = pythonpath + os.pathsep + os.environ["PYTHONPATH"]

    env = {
        **os.environ,
        "PYTHONPATH": pythonpath,
        "FLASK_APP": "app",
        "DATABASE_URL": "sqlite:///" + str(database_path),
        "UPLOAD_FOLDER": str(upload_folder),
    }

    result = subprocess.run(
        [sys.executable, "-m", "flask", "db", "upgrade"],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr

    connection = sqlite3.connect(database_path)
    tables = {
        row[0]
        for row in connection.execute(
            "select name from sqlite_master where type = 'table'"
        )
    }

    assert {
        "alembic_version",
        "term",
        "feedback",
        "knowledge_document",
        "knowledge_chunk",
        "terminology_card",
    }.issubset(tables)

    document_columns = {
        row[1]
        for row in connection.execute("pragma table_info(knowledge_document)")
    }
    chunk_columns = {
        row[1]
        for row in connection.execute("pragma table_info(knowledge_chunk)")
    }

    assert {"layout_provider", "layout_status", "layout_warnings_json"}.issubset(
        document_columns
    )
    assert {
        "page_number",
        "bbox_json",
        "layout_type",
        "reading_order",
        "layout_provider",
        "layout_confidence",
        "quality_flags_json",
    }.issubset(chunk_columns)

    card_columns = {
        row[1]
        for row in connection.execute("pragma table_info(terminology_card)")
    }
    card_indexes = {
        row[1]
        for row in connection.execute("pragma index_list(terminology_card)")
    }

    assert {
        "scope_type",
        "course_id",
        "owner_user_id",
        "source_document_id",
        "english_term",
        "normalized_english_term",
        "final_chinese_term",
        "english_evidence_snapshot",
        "chinese_evidence_snapshot",
        "english_evidence_score",
        "chinese_evidence_score",
        "alignment_status",
        "confidence_score",
        "status",
        "score_breakdown_json",
        "quality_flags_json",
        "risk_note",
        "feedback_count",
        "approved_by",
        "approved_at",
        "created_at",
        "updated_at",
    }.issubset(card_columns)
    assert {
        "ix_terminology_card_status",
        "ix_terminology_card_alignment_status",
        "ix_terminology_card_normalized_english_term",
    }.issubset(card_indexes)

    connection.execute(
        """
        insert into terminology_card (english_term, normalized_english_term)
        values (?, ?)
        """,
        ("Fourier Transform", "fourier transform"),
    )
    row = connection.execute(
        """
        select scope_type, alignment_status, confidence_score, status,
               feedback_count, created_at, updated_at
        from terminology_card
        where normalized_english_term = ?
        """,
        ("fourier transform",),
    ).fetchone()

    assert row[0] == "course"
    assert row[1] == "unverified_translation"
    assert row[2] == 0.0
    assert row[3] == "pending_quality_control"
    assert row[4] == 0
    assert row[5]
    assert row[6]
