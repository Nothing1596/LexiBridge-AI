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
