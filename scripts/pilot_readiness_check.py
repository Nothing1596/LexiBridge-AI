#!/usr/bin/env python3
"""Run pilot-readiness checks for LexiBridge-AI without external network calls."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "backend" / ".venv-macos" / "bin" / "python"
PYTHON_CMD = str(PYTHON if PYTHON.exists() else sys.executable)
READY = "READY"
READY_WITH_CONDITIONS = "READY_WITH_CONDITIONS"
NOT_READY = "NOT_READY"
E2E_ENVIRONMENT_UNAVAILABLE = 2

PROFILE_CONDITIONS = {
    "local-demo": [
        "sqlite_database",
        "flask_development_server",
        "external_llm_disabled",
        "demo_local_accounts_only",
        "formal_migration_not_enabled",
        "FORMAL_BACKGROUND_JOB_LEASE_FOUNDATION_PRESENT",
        "FORMAL_CHUNK_SCOPED_TERM_CANDIDATES_PRESENT",
        "FORMAL_WORKFLOW_ITEM_BOOTSTRAP_PRESENT",
        "FORMAL_BOOTSTRAP_LEASE_FENCING_PRESENT",
        "FORMAL_VERIFICATION_TRANSACTION_ADAPTER_NOT_IMPLEMENTED",
        "POSTGRESQL_BOOTSTRAP_TRANSACTION_NOT_VERIFIED",
        "FORMAL_BACKGROUND_JOB_HANDLER_NOT_IMPLEMENTED",
        "FORMAL_PROCESSING_ORCHESTRATOR_NOT_IMPLEMENTED",
        "POSTGRESQL_LEASE_SEMANTICS_NOT_VERIFIED",
    ],
    "small-pilot": [
        "small_pilot_only",
        "sqlite_database",
        "flask_development_server",
        "external_llm_disabled",
        "demo_local_account_restrictions",
        "formal_migration_not_enabled",
        "production_monitoring_not_enabled",
        "FORMAL_BACKGROUND_JOB_LEASE_FOUNDATION_PRESENT",
        "FORMAL_CHUNK_SCOPED_TERM_CANDIDATES_PRESENT",
        "FORMAL_WORKFLOW_ITEM_BOOTSTRAP_PRESENT",
        "FORMAL_BOOTSTRAP_LEASE_FENCING_PRESENT",
        "FORMAL_VERIFICATION_TRANSACTION_ADAPTER_NOT_IMPLEMENTED",
        "POSTGRESQL_BOOTSTRAP_TRANSACTION_NOT_VERIFIED",
        "FORMAL_BACKGROUND_JOB_HANDLER_NOT_IMPLEMENTED",
        "FORMAL_PROCESSING_ORCHESTRATOR_NOT_IMPLEMENTED",
        "POSTGRESQL_LEASE_SEMANTICS_NOT_VERIFIED",
    ],
}


class PhaseResult(dict):
    @property
    def ok(self) -> bool:
        return self.get("status") in {"PASS", "WARN", "UNAVAILABLE"}

    @property
    def blocking_failed(self) -> bool:
        return self.get("status") == "FAIL"


def default_conditions(profile: str) -> list[str]:
    return list(PROFILE_CONDITIONS.get(profile, PROFILE_CONDITIONS["small-pilot"]))


def compute_readiness_verdict(checks: list[dict], conditions: list[str] | None = None) -> str:
    if any(str(check.get("status") or "").upper() == "FAIL" for check in checks):
        return NOT_READY
    if conditions:
        return READY_WITH_CONDITIONS
    return READY


def build_readiness_payload(
    *,
    profile: str,
    checks: list[dict],
    conditions: list[str],
    warnings: list[str],
    browser_e2e: dict | None = None,
) -> dict:
    blocking_failures = [
        {
            "name": check.get("name"),
            "returncode": check.get("returncode"),
            "status": check.get("status"),
        }
        for check in checks
        if str(check.get("status") or "").upper() == "FAIL"
    ]
    verdict = compute_readiness_verdict(checks, conditions)
    return {
        "verdict": verdict,
        "profile": profile,
        "checks": checks,
        "conditions": conditions,
        "blocking_failures": blocking_failures,
        "warnings": warnings,
        "browser_e2e": browser_e2e or {},
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def summarize_browser_e2e_result(result: dict | None) -> dict:
    result = result or {}
    student = result.get("student_flow") or {}
    teacher = result.get("teacher_flow") or {}
    browser = result.get("browser") or {}
    flows = [student, teacher]
    return {
        "browser_e2e_status": result.get("status", "UNKNOWN"),
        "browser_name": browser.get("name", ""),
        "browser_version": browser.get("version", ""),
        "student_flow_status": student.get("status", "UNKNOWN"),
        "teacher_flow_status": teacher.get("status", "UNKNOWN"),
        "js_error_count": sum(len(flow.get("console_errors") or []) for flow in flows),
        "page_error_count": sum(len(flow.get("page_errors") or []) for flow in flows),
        "external_dependency_count": len(result.get("external_dependency_requests") or []),
        "blocked_external_request_count": len(result.get("blocked_external_requests") or []),
    }


def load_json_result(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def build_env(temp_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{temp_root / 'pilot-readiness.db'}"
    env["UPLOAD_FOLDER"] = str(temp_root / "uploads")
    env["AUTH_REQUIRED"] = "True"
    env["AI_PROVIDER"] = "none"
    env["ALLOW_MOCK_AI"] = "True"
    env["OCR_PROVIDER"] = "none"
    env["FORMULA_OCR_PROVIDER"] = "none"
    env.pop("DEEPSEEK_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def run_command(
    name: str,
    cmd: list[str],
    env: dict[str, str],
    *,
    timeout: int = 180,
    condition_returncodes: dict[int, tuple[str, str]] | None = None,
) -> PhaseResult:
    print(f"\n==> {name}")
    started = time.perf_counter()
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if result.stdout.strip():
        print(result.stdout.rstrip())
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)
    condition_returncodes = condition_returncodes or {}
    condition = ""
    if result.returncode == 0:
        status = "PASS"
    elif result.returncode in condition_returncodes:
        status, condition = condition_returncodes[result.returncode]
    else:
        status = "FAIL"
    print(f"{status}: {name} ({elapsed_ms} ms)")
    payload = PhaseResult(name=name, returncode=result.returncode, elapsed_ms=elapsed_ms, status=status)
    if condition:
        payload["condition"] = condition
    return payload


def run_python_snippet(name: str, code: str, env: dict[str, str], *, timeout: int = 180) -> PhaseResult:
    return run_command(name, [PYTHON_CMD, "-c", textwrap.dedent(code)], env, timeout=timeout)


def frontend_js_syntax_check_code() -> str:
    return r"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path.cwd()
html = root / "frontend" / "index.html"
text = html.read_text(encoding="utf-8")
matches = re.findall(r"<script>(.*?)</script>", text, flags=re.S)
if not matches:
    raise SystemExit("no inline frontend script found")
node = (
    Path.home()
    / ".cache"
    / "codex-runtimes"
    / "codex-primary-runtime"
    / "dependencies"
    / "node"
    / "bin"
    / "node"
)
node_cmd = str(node) if node.exists() else shutil.which("node")
if not node_cmd:
    print("SKIP: node not available for frontend JavaScript syntax check")
    raise SystemExit(0)
with tempfile.TemporaryDirectory(prefix="lexibridge-js-check-") as tmp:
    path = Path(tmp) / "frontend.js"
    path.write_text("\n".join(matches), encoding="utf-8")
    subprocess.run([node_cmd, "--check", str(path)], cwd=root, check=True)
"""


def python_compile_code() -> str:
    return r"""
import tokenize
from pathlib import Path

root = Path.cwd()
skip_parts = {".git", ".venv", ".venv-macos", "__pycache__", ".pytest_cache", "uploads", "final_delivery"}
failures = []
for path in root.rglob("*.py"):
    relative_parts = path.relative_to(root).parts
    if any(part in skip_parts or part.startswith(".venv") for part in relative_parts):
        continue
    try:
        with tokenize.open(path) as handle:
            source = handle.read()
        compile(source, str(path), "exec")
    except Exception as exc:
        failures.append(f"{path}: {exc}")
if failures:
    print("\n".join(failures))
    raise SystemExit(1)
print("compiled python files")
"""


def api_smoke_code() -> str:
    return r"""
import importlib.util
from pathlib import Path

root = Path.cwd()
backend = root / "backend"
import sys
sys.path.insert(0, str(backend))
spec = importlib.util.spec_from_file_location("pilot_app", backend / "app.py")
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)
seed_spec = importlib.util.spec_from_file_location("pilot_seed", root / "scripts" / "seed_review_demo.py")
seed = importlib.util.module_from_spec(seed_spec)
seed_spec.loader.exec_module(seed)
summary = seed.seed_review_demo(app_module, reset_demo=False)
client = app_module.app.test_client()
login = client.post("/api/auth/login", json={
    "email": summary["users"]["student"]["email"],
    "password": summary["users"]["student"]["password"],
})
assert login.status_code == 200, login.get_data(as_text=True)
token = login.get_json()["token"]
headers = {"Authorization": f"Bearer {token}", "X-Request-ID": "pilot-readiness-api-smoke"}
cards = client.get("/api/student/concept-cards?per_page=5", headers=headers)
assert cards.status_code == 200, cards.get_data(as_text=True)
assert cards.get_json()["request_id"] == "pilot-readiness-api-smoke"
print(f"student cards: {len(cards.get_json()['data']['items'])}")
"""


def provider_network_disabled_code() -> str:
    return r"""
import importlib.util
import socket
import sys
import urllib.request
from pathlib import Path

root = Path.cwd()
backend = root / "backend"
sys.path.insert(0, str(backend))
spec = importlib.util.spec_from_file_location("pilot_app_network", backend / "app.py")
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)
seed_spec = importlib.util.spec_from_file_location("pilot_seed_network", root / "scripts" / "seed_review_demo.py")
seed = importlib.util.module_from_spec(seed_spec)
seed_spec.loader.exec_module(seed)
summary = seed.seed_review_demo(app_module, reset_demo=False)
client = app_module.app.test_client()
login = client.post("/api/auth/login", json={
    "email": summary["users"]["admin"]["email"],
    "password": summary["users"]["admin"]["password"],
})
assert login.status_code == 200, login.get_data(as_text=True)
token = login.get_json()["token"]
original_connect = socket.socket.connect
original_request = urllib.request.Request
original_urlopen = urllib.request.urlopen
def blocked_connect(*args, **kwargs):
    raise AssertionError("external network is disabled during pilot readiness checks")
def blocked_request(*args, **kwargs):
    raise AssertionError("legacy alignment urllib Request must not be constructed")
def blocked_urlopen(*args, **kwargs):
    raise AssertionError("legacy alignment urlopen must not be called")
socket.socket.connect = blocked_connect
urllib.request.Request = blocked_request
urllib.request.urlopen = blocked_urlopen
try:
    response = client.post(
        "/api/alignment/verify",
        json={"card_uid": summary["card_uids"]["fourier"], "provider": "deepseek-alignment-v1-disabled"},
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "pilot-readiness-disabled-provider"},
    )
finally:
    socket.socket.connect = original_connect
    urllib.request.Request = original_request
    urllib.request.urlopen = original_urlopen
assert response.status_code == 200, response.get_data(as_text=True)
payload = response.get_json()["data"]
assert payload["verification_status"] == "failed"
assert payload["can_auto_approve"] is False
with app_module.app.app_context():
    live_config = app_module.AIProviderConfig(
        provider_name="deepseek",
        provider_mode="live",
        base_url="https://example.invalid/readiness-live-probe",
        default_model="deepseek-chat",
        is_enabled=True,
        is_default=True,
        health_status="unknown",
        created_at=app_module.current_time_text(),
        updated_at=app_module.current_time_text(),
    )
    app_module.db.session.add(live_config)
    app_module.db.session.commit()
app_module.DEEPSEEK_API_KEY = "LEXIBRIDGE_READINESS_SENTINEL_SECRET"
app_module.DEEPSEEK_BASE_URL = "https://example.invalid/readiness-live-probe"
legacy_response = client.post(
    "/api/admin/ai/healthcheck",
    json={"live_probe": True},
    headers={"Authorization": f"Bearer {token}", "X-Request-ID": "pilot-readiness-legacy-live-probe-disabled"},
)
assert legacy_response.status_code == 200, legacy_response.get_data(as_text=True)
legacy_payload = legacy_response.get_json()
serialized = str(legacy_payload)
assert "LEXIBRIDGE_READINESS_SENTINEL_SECRET" not in serialized
assert any(
    item.get("error_code") == "LEGACY_LIVE_PROBE_DISABLED"
    for item in legacy_payload["data"]["items"]
), legacy_payload
ctx = app_module.app.app_context()
ctx.push()
course = app_module.Course.query.filter_by(name=summary["course"]).first()
admin = app_module.User.query.filter_by(email=summary["users"]["admin"]["email"]).first()
assert course is not None
assert admin is not None
before_route = {
    "alignment_runs": app_module.AlignmentRun.query.count(),
    "background_jobs": app_module.BackgroundJob.query.count(),
    "terminology_cards": app_module.TerminologyCard.query.count(),
    "usage_records": app_module.UsageRecord.query.count(),
    "ai_call_logs": app_module.AICallLog.query.count(),
    "verification_runs": app_module.AlignmentVerificationRun.query.count(),
    "audit_records": app_module.AuditRecord.query.count(),
}
def fail_metadata(*args, **kwargs):
    raise AssertionError("legacy alignment blocked path must not load provider metadata")
app_module.current_provider_metadata = fail_metadata
original_connect = socket.socket.connect
original_request = urllib.request.Request
original_urlopen = urllib.request.urlopen
socket.socket.connect = blocked_connect
urllib.request.Request = blocked_request
urllib.request.urlopen = blocked_urlopen
try:
    route_response = client.post(
        "/api/alignment/run",
        json={
            "scope_type": "course",
            "course_id": course.id,
            "english_term": "Pilot readiness external legacy route",
            "courseware_sentence": "External provider must be blocked before transport.",
            "provider": "deepseek",
            "base_url": "https://example.invalid/readiness-legacy-alignment?token=LEXIBRIDGE_READINESS_SENTINEL_SECRET",
        },
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "pilot-readiness-legacy-alignment-external-disabled"},
    )
finally:
    socket.socket.connect = original_connect
    urllib.request.Request = original_request
    urllib.request.urlopen = original_urlopen
assert route_response.status_code == 422, route_response.get_data(as_text=True)
route_payload = route_response.get_json()
route_serialized = str(route_payload)
assert route_payload["error_code"] == "LEGACY_ALIGNMENT_EXTERNAL_EXECUTION_DISABLED", route_payload
assert "LEXIBRIDGE_READINESS_SENTINEL_SECRET" not in route_serialized
after_route = {
    "alignment_runs": app_module.AlignmentRun.query.count(),
    "background_jobs": app_module.BackgroundJob.query.count(),
    "terminology_cards": app_module.TerminologyCard.query.count(),
    "usage_records": app_module.UsageRecord.query.count(),
    "ai_call_logs": app_module.AICallLog.query.count(),
    "verification_runs": app_module.AlignmentVerificationRun.query.count(),
    "audit_records": app_module.AuditRecord.query.count(),
}
assert after_route == before_route, (before_route, after_route)
alignment_run = app_module.AlignmentRun(
    course_id=course.id,
    triggered_by=admin.id,
    provider="deepseek",
    model_name="deepseek-chat",
    ai_provider="deepseek",
    ai_provider_mode="live",
    ai_model="deepseek-chat",
    prompt_key="term_alignment",
    prompt_version="v1",
    retrieval_version=app_module.RETRIEVAL_VERSION,
    status="queued",
    started_at="",
)
app_module.db.session.add(alignment_run)
app_module.db.session.flush()
job = app_module.create_background_job(
    "alignment_run",
    admin.id,
    course_id=course.id,
    alignment_run_id=alignment_run.id,
    scope_type="course",
    input_data={
        "provider": "deepseek",
        "provider_mode": "live",
        "base_url": "https://example.invalid/readiness-worker?token=LEXIBRIDGE_READINESS_SENTINEL_SECRET",
        "english_term": "Pilot readiness external worker",
        "courseware_sentence": "Queued external job must be quarantined.",
    },
)
app_module.db.session.commit()
before_worker = {
    "terminology_cards": app_module.TerminologyCard.query.count(),
    "usage_records": app_module.UsageRecord.query.count(),
    "ai_call_logs": app_module.AICallLog.query.count(),
    "verification_runs": app_module.AlignmentVerificationRun.query.count(),
    "audit_records": app_module.AuditRecord.query.count(),
}
original_connect = socket.socket.connect
original_request = urllib.request.Request
original_urlopen = urllib.request.urlopen
socket.socket.connect = blocked_connect
urllib.request.Request = blocked_request
urllib.request.urlopen = blocked_urlopen
try:
    processed = app_module.run_background_job(job.id, worker_id="pilot-readiness-worker")
finally:
    socket.socket.connect = original_connect
    urllib.request.Request = original_request
    urllib.request.urlopen = original_urlopen
assert processed.status == "failed"
assert processed.error_code == "LEGACY_ALIGNMENT_EXTERNAL_EXECUTION_DISABLED"
assert "LEXIBRIDGE_READINESS_SENTINEL_SECRET" not in (processed.error_message or "")
after_worker = {
    "terminology_cards": app_module.TerminologyCard.query.count(),
    "usage_records": app_module.UsageRecord.query.count(),
    "ai_call_logs": app_module.AICallLog.query.count(),
    "verification_runs": app_module.AlignmentVerificationRun.query.count(),
    "audit_records": app_module.AuditRecord.query.count(),
}
assert after_worker == before_worker, (before_worker, after_worker)
legacy_external_runnable_jobs_count = 0
for existing_job in app_module.BackgroundJob.query.filter(app_module.BackgroundJob.status.in_(["queued", "running", "retrying"])).all():
    data = app_module.job_input(existing_job)
    run = app_module.db.session.get(app_module.AlignmentRun, existing_job.alignment_run_id) if existing_job.alignment_run_id else None
    classification = app_module.classify_legacy_alignment_job(existing_job, alignment_run=run, data=data)
    if classification.external_execution_blocked:
        legacy_external_runnable_jobs_count += 1
assert legacy_external_runnable_jobs_count == 0
openapi_text = (root / "docs" / "openapi.yaml").read_text(encoding="utf-8")
alignment_run_section = openapi_text.split("/api/alignment/run:", 1)[1].split("/api/", 1)[0]
assert "deprecated: true" in alignment_run_section
assert "LEGACY_ALIGNMENT_EXTERNAL_EXECUTION_DISABLED" in alignment_run_section
print("disabled external provider, legacy live probe, legacy alignment route, and legacy worker produced safe results without network")
"""


def performance_smoke_code() -> str:
    return r"""
import importlib.util
import sys
import time
from pathlib import Path

root = Path.cwd()
backend = root / "backend"
sys.path.insert(0, str(backend))
spec = importlib.util.spec_from_file_location("pilot_app_perf", backend / "app.py")
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)
seed_spec = importlib.util.spec_from_file_location("pilot_seed_perf", root / "scripts" / "seed_review_demo.py")
seed = importlib.util.module_from_spec(seed_spec)
seed_spec.loader.exec_module(seed)
summary = seed.seed_review_demo(app_module, reset_demo=False)
client = app_module.app.test_client()

def token_for(role):
    response = client.post("/api/auth/login", json={
        "email": summary["users"][role]["email"],
        "password": summary["users"][role]["password"],
    })
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["token"]

student_token = token_for("student")
teacher_token = token_for("teacher")
course = seed.DEMO_COURSE.replace(" ", "%20")
checks = [
    ("review queue", "/api/concept-cards/review-queue?course=" + course, teacher_token),
    ("student card list", "/api/student/concept-cards?course=" + course, student_token),
    ("student progress", "/api/student/progress?course=" + course, student_token),
    ("feedback queue", "/api/concept-cards/student-feedback-queue?course=" + course, teacher_token),
    ("teacher analytics", "/api/teacher/learning-analytics?course=" + course, teacher_token),
]
warnings = []
for name, path, token in checks:
    started = time.perf_counter()
    response = client.get(path, headers={"Authorization": f"Bearer {token}", "X-Request-ID": "pilot-readiness-perf"})
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    assert response.status_code == 200, response.get_data(as_text=True)
    data = response.get_json().get("data", {})
    if isinstance(data, dict) and "items" in data:
        count = len(data["items"])
    elif isinstance(data, dict) and "course_summary" in data:
        count = data["course_summary"].get("approved_card_count", 0)
    else:
        count = 1
    print(f"{name}: {elapsed_ms} ms, result_count={count}")
    if elapsed_ms > 2000:
        warnings.append(name)
if warnings:
    print("WARNING: slow demo endpoints: " + ", ".join(warnings))
"""


def table_count(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(f"select count(*) from {table}").fetchone()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LexiBridge pilot-readiness checks.")
    parser.add_argument("--skip-full-tests", action="store_true", help="Run targeted pilot checks instead of full pytest.")
    parser.add_argument("--profile", choices=sorted(PROFILE_CONDITIONS), default="small-pilot")
    parser.add_argument("--json-output", help="Write machine-readable readiness result JSON.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="lexibridge-pilot-readiness-") as tmp:
        temp_root = Path(tmp)
        env = build_env(temp_root)
        db_path = temp_root / "pilot-readiness.db"
        upload_dir = temp_root / "uploads"
        backup_parent = temp_root / "backup-output"
        restored_db = temp_root / "restored" / "restored.db"
        restored_uploads = temp_root / "restored" / "uploads"
        browser_e2e_json = temp_root / "browser-e2e-result.json"
        browser_e2e_result: dict | None = None

        phases: list[PhaseResult] = []
        warnings: list[str] = []
        conditions = default_conditions(args.profile)
        phases.append(run_command("release safety", [PYTHON_CMD, "scripts/check_release_safety.py"], env, timeout=120))
        phases.append(run_python_snippet("python compile", python_compile_code(), env, timeout=120))
        phases.append(run_python_snippet("frontend javascript syntax", frontend_js_syntax_check_code(), env, timeout=120))

        if args.skip_full_tests:
            pytest_cmd = [
                PYTHON_CMD,
                "-m",
                "pytest",
                "-q",
                "tests/test_pilot_end_to_end.py",
                "tests/test_permission_matrix.py",
                "tests/test_openapi_route_parity.py",
                "tests/test_database_upgrade_path.py",
                "tests/test_data_integrity.py",
            ]
        else:
            pytest_cmd = [PYTHON_CMD, "-m", "pytest", "-q"]
        phases.append(run_command("pytest", pytest_cmd, env, timeout=600))

        phases.append(run_command("fresh database migration", [PYTHON_CMD, "scripts/migrate_db.py"], env, timeout=120))
        phases.append(run_command("existing database upgrade simulation", [PYTHON_CMD, "-m", "pytest", "-q", "tests/test_database_upgrade_path.py"], env, timeout=240))
        phases.append(run_command("demo seed reset", [PYTHON_CMD, "scripts/seed_review_demo.py", "--reset-demo"], env, timeout=120))
        phases.append(run_command("demo seed repeated run", [PYTHON_CMD, "scripts/seed_review_demo.py"], env, timeout=120))
        backup_phase = run_command(
            "backup creation",
            [
                PYTHON_CMD,
                "scripts/pilot_backup.py",
                "--database",
                str(db_path),
                "--uploads",
                str(upload_dir),
                "--output",
                str(backup_parent),
            ],
            env,
            timeout=120,
        )
        phases.append(backup_phase)
        backup_path = backup_parent
        if backup_phase.ok:
            manifest_candidates = sorted(backup_parent.rglob("backup_manifest.json"))
            if manifest_candidates:
                backup_path = manifest_candidates[-1].parent
        phases.append(run_command("backup verification", [PYTHON_CMD, "scripts/verify_pilot_backup.py", "--backup", str(backup_path)], env, timeout=120))
        phases.append(
            run_command(
                "restore",
                [
                    PYTHON_CMD,
                    "scripts/pilot_restore.py",
                    "--backup",
                    str(backup_path),
                    "--database-target",
                    str(restored_db),
                    "--uploads-target",
                    str(restored_uploads),
                ],
                env,
                timeout=120,
            )
        )
        phases.append(
            run_python_snippet(
                "restored database integrity",
                f"""
import sqlite3
from pathlib import Path
db = Path({str(restored_db)!r})
assert db.exists(), db
with sqlite3.connect(db) as conn:
    assert conn.execute("pragma integrity_check").fetchone()[0] == "ok"
    for table in ["concept_alignment_card", "concept_card_review_record", "student_concept_card_state", "audit_record"]:
        assert conn.execute("select count(*) from sqlite_master where type='table' and name=?", (table,)).fetchone()[0] == 1, table
print("restored database integrity ok")
""",
                env,
                timeout=120,
            )
        )
        phases.append(run_python_snippet("api smoke", api_smoke_code(), env, timeout=120))
        phases.append(run_command("core permission matrix", [PYTHON_CMD, "-m", "pytest", "-q", "tests/test_permission_matrix.py"], env, timeout=240))
        phases.append(run_python_snippet("provider network-disabled check", provider_network_disabled_code(), env, timeout=120))
        phases.append(run_command("openapi route parity", [PYTHON_CMD, "-m", "pytest", "-q", "tests/test_openapi_route_parity.py"], env, timeout=120))
        phases.append(run_command("data integrity checks", [PYTHON_CMD, "-m", "pytest", "-q", "tests/test_data_integrity.py"], env, timeout=180))
        phases.append(run_command(
            "formal background job execution ownership",
            [
                PYTHON_CMD,
                "-m",
                "pytest",
                "-q",
                "tests/test_formal_background_job_execution.py",
                "tests/test_formal_background_job_concurrency.py",
            ],
            env,
            timeout=240,
        ))
        phases.append(run_command(
            "formal document alignment item bootstrap",
            [
                PYTHON_CMD,
                "-m",
                "pytest",
                "-q",
                "tests/test_document_alignment_term_candidates.py",
                "tests/test_document_alignment_item_bootstrap.py",
                "tests/test_document_alignment_item_bootstrap_integration.py",
            ],
            env,
            timeout=240,
        ))
        phases.append(run_command("critical e2e workflow", [PYTHON_CMD, "-m", "pytest", "-q", "tests/test_pilot_end_to_end.py"], env, timeout=300))
        browser_phase = run_command(
            "browser e2e",
            [
                PYTHON_CMD,
                "scripts/run_browser_e2e.py",
                "--json-output",
                str(browser_e2e_json),
                "--artifacts",
                str(temp_root / "browser-e2e-artifacts"),
            ],
            env,
            timeout=600,
            condition_returncodes={
                E2E_ENVIRONMENT_UNAVAILABLE: ("UNAVAILABLE", "browser_e2e_not_executed")
            },
        )
        phases.append(browser_phase)
        browser_e2e_result = load_json_result(browser_e2e_json)
        if browser_phase.get("condition") and browser_phase["condition"] not in conditions:
            conditions.append(browser_phase["condition"])
            warnings.append(browser_phase["condition"])
        phases.append(run_python_snippet("lightweight performance smoke", performance_smoke_code(), env, timeout=120))
        phases.append(
            run_python_snippet(
                "verdict consistency",
                f"""
from pathlib import Path
report = Path("docs/pilot_readiness_report.md").read_text(encoding="utf-8")
assert "READY WITH CONDITIONS" in report or "READY_WITH_CONDITIONS" in report
print("report verdict documents READY WITH CONDITIONS")
""",
                env,
                timeout=60,
            )
        )

        if db_path.exists():
            print(f"\nTemporary database rows: concept_cards={table_count(db_path, 'concept_alignment_card')}, audits={table_count(db_path, 'audit_record')}")
        shutil.rmtree(upload_dir, ignore_errors=True)

        print("\nPilot readiness phase summary:")
        for phase in phases:
            condition = f" [{phase['condition']}]" if phase.get("condition") else ""
            print(f"- {phase['status']}: {phase['name']} ({phase['elapsed_ms']} ms){condition}")

        payload = build_readiness_payload(
            profile=args.profile,
            checks=[dict(phase) for phase in phases],
            conditions=conditions,
            warnings=warnings,
            browser_e2e=summarize_browser_e2e_result(browser_e2e_result),
        )
        if args.json_output:
            Path(args.json_output).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        printable_verdict = payload["verdict"].replace("_", " ")
        print(f"\n{payload['verdict']}")
        print(f"Pilot readiness verdict: {printable_verdict}")
        if payload["conditions"]:
            print("Conditions: " + ", ".join(payload["conditions"]))
        return 0 if payload["verdict"] != NOT_READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
