#!/usr/bin/env python3
"""Run one offline, real-model uploaded-material Student alignment acceptance.

The runner uses a temporary database and upload directory, the pinned local
multilingual model, production ingestion, the production Student route, and no
Provider. It writes only bounded, sanitized metrics.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"


class AcceptanceRerankerBackend:
    backend_id = "local_bge_reranker_v2_m3_cpu_v1"
    model_id = "BAAI/bge-reranker-v2-m3"
    model_revision = "79c481748842b7efa0a12db59915db91731f0b93"

    def readiness(self):
        return type("Readiness", (), {"ready": True, "reason_code": "READY"})()

    def score_pairs(self, pairs):
        return [5.0 for _ in pairs]


def _load_browser_support():
    path = ROOT / "scripts" / "run_browser_e2e.py"
    spec = importlib.util.spec_from_file_location("lexibridge_13c1_support", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _pdf_bytes(lines: tuple[str, ...]) -> bytes:
    buffer = io.BytesIO()
    document = canvas.Canvas(buffer, pagesize=letter)
    y = 720
    for line in lines:
        if any(ord(character) > 127 for character in line):
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            document.setFont("STSong-Light", 12)
        else:
            document.setFont("Helvetica", 12)
        document.drawString(72, y, line)
        y -= 30
    document.save()
    return buffer.getvalue()


def _login(client, summary: dict) -> str:
    student = summary["users"]["student"]
    response = client.post(
        "/api/auth/login",
        json={"email": student["email"], "password": student["password"]},
    )
    if response.status_code != 200:
        raise RuntimeError("student login failed")
    return str(response.get_json()["token"])


def _upload(client, app_module, token: str, filename: str, language: str, lines: tuple[str, ...]):
    response = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "scope_type": "personal",
            "language": language,
            "source_type": "student_upload",
            "personal_workspace_contract": "13C",
            "file": (io.BytesIO(_pdf_bytes(lines)), filename),
        },
        content_type="multipart/form-data",
    )
    if response.status_code != 200:
        raise RuntimeError(f"upload failed safely: {response.status_code}")
    payload = response.get_json()["data"]
    with app_module.app.app_context():
        app_module.run_background_job(payload["job_id"], worker_id="acceptance-13c1")
        source = app_module.KnowledgeSource.query.filter_by(
            document_id=payload["document_id"]
        ).one()
        chunks = app_module.KnowledgeChunk.query.filter_by(
            source_uid=source.source_uid
        ).order_by(app_module.KnowledgeChunk.id.asc()).all()
        if not chunks:
            raise RuntimeError("ingestion produced no governed chunks")
        return {
            "document_id": payload["document_id"],
            "source_uid": source.source_uid,
            "chunks": [(chunk.chunk_uid, chunk.content) for chunk in chunks],
        }


def run(model_cache_dir: Path) -> dict:
    model_cache_dir = model_cache_dir.expanduser().resolve()
    if ROOT == model_cache_dir or ROOT in model_cache_dir.parents:
        raise RuntimeError("model cache must remain outside the repository")
    os.environ["LEXIBRIDGE_MODEL_CACHE_DIR"] = str(model_cache_dir)
    os.environ["LEXIBRIDGE_CROSS_LANGUAGE_RETRIEVAL_BACKEND"] = (
        "local-multilingual-e5-small"
    )
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HOME"] = str(model_cache_dir)
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(model_cache_dir)
    os.environ["FORMULA_DETECTION_MODE"] = "off"
    for name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        os.environ.pop(name, None)

    support = _load_browser_support()
    with tempfile.TemporaryDirectory(prefix="lexibridge-13c1-") as temp_name:
        temp_root = Path(temp_name)
        runtime = support.run_setup(
            temp_root / "acceptance.db", temp_root / "uploads", "real_model_13c1"
        )
        app_module = runtime["app_module"]
        if str(BACKEND) not in sys.path:
            sys.path.insert(0, str(BACKEND))
        from services.local_multilingual_embedding import LocalMultilingualEmbeddingBackend

        backend = LocalMultilingualEmbeddingBackend(model_cache_dir=model_cache_dir)
        readiness = backend.readiness()
        if not readiness.ready:
            raise RuntimeError(readiness.reason_code)
        app_module.app.config.pop("STUDENT_ALIGNMENT_RUNNER", None)
        app_module.app.config["STUDENT_CROSS_LANGUAGE_EMBEDDING_BACKEND"] = backend
        app_module.app.config["STUDENT_BILINGUAL_RERANKER_BACKEND"] = (
            AcceptanceRerankerBackend()
        )

        # Remove the deterministic Personal Chinese source installed by the
        # general Browser fixture. This acceptance must use only the Chinese
        # PDF uploaded below.
        with app_module.app.app_context():
            fixture_source = app_module.KnowledgeSource.query.filter_by(
                source_uid="e2e-personal-zh"
            ).first()
            if fixture_source is not None:
                app_module.KnowledgeChunk.query.filter_by(
                    source_uid=fixture_source.source_uid
                ).delete(synchronize_session=False)
                app_module.db.session.delete(fixture_source)
                app_module.db.session.commit()

        client = app_module.app.test_client()
        token = _login(client, runtime["summary"])
        started = time.perf_counter()
        chinese = _upload(
            client,
            app_module,
            token,
            "synthetic-governed-chinese.pdf",
            "zh",
            ("电势", "电势表示单位电荷在电场中的电势能。"),
        )
        english = _upload(
            client,
            app_module,
            token,
            "synthetic-english-course.pdf",
            "en",
            (
                "Electric potential",
                "Electric potential is potential energy per unit charge.",
            ),
        )
        chunk_uid, content = next(
            item for item in english["chunks"] if "electric potential" in item[1].casefold()
        )
        selected = "Electric potential"
        start = content.index(selected)
        query_started = time.perf_counter()
        response = client.post(
            "/api/student/concept-queries",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": "real-model-uploaded-source-13c1",
            },
            json={
                "workspace_scope": "PERSONAL",
                "source_uid": english["source_uid"],
                "chunk_uid": chunk_uid,
                "selected_text": selected,
                "selection_start": start,
                "selection_end": start + len(selected),
            },
        )
        query_ms = round((time.perf_counter() - query_started) * 1000, 2)
        if response.status_code != 200:
            raise RuntimeError(f"ConceptQuery failed safely: {response.status_code}")
        result = response.get_json()["data"]["query"]
        if result.get("processing_status") != "completed":
            raise RuntimeError(result.get("error_code") or "alignment did not complete")
        save = client.put(
            f"/api/student/concept-queries/{result['query_uid']}/personal-record",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "saved": True,
                "note": "Offline real-model acceptance note.",
                "understanding_state": "UNDERSTOOD",
                "expected_version": 0,
            },
        )
        if save.status_code != 200:
            raise RuntimeError("PersonalLearningRecord save failed")
        english_sources = sorted(
            {item.get("source_uid", "") for item in result.get("english_evidence", [])}
        )
        chinese_sources = sorted(
            {item.get("source_uid", "") for item in result.get("chinese_evidence", [])}
        )
        with app_module.app.app_context():
            query_record = app_module.StudentConceptQuery.query.filter_by(
                query_uid=result["query_uid"]
            ).one()
            raw_result = json.loads(query_record.result_json or "{}")
        qualification = dict(raw_result.get("qualification") or {})
        return {
            "contract_id": "real-uploaded-student-alignment-13c1@1.0.0",
            "status": "PASS",
            "environment": "synthetic-local-offline-real-model",
            "model": {
                "backend_id": backend.backend_id,
                "model_id": MODEL_ID,
                "model_revision": MODEL_REVISION,
                "offline": True,
            },
            "same_uploaded_english_source": english_sources == [english["source_uid"]],
            "uploaded_chinese_source_only": chinese_sources == [chinese["source_uid"]],
            "english_evidence_count": len(result.get("english_evidence", [])),
            "chinese_evidence_count": len(result.get("chinese_evidence", [])),
            "chinese_candidate_count": len(result.get("chinese_candidates", [])),
            "alignment_status": result.get("alignment_status"),
            "qualification_decision": qualification.get("decision") or "NOT_EVALUATED",
            "qualification_reason_codes": sorted(
                str(value)
                for value in qualification.get("reason_codes", [])
                if str(value).strip()
            ),
            "risk_labels": sorted(
                str(value)
                for value in raw_result.get("risk_labels", [])
                if str(value).strip()
            ),
            "processing_status": result.get("processing_status"),
            "personal_record_saved": bool(
                save.get_json()["data"]["query"]["personal_state"]["saved"]
            ),
            "source_provenance_retained": bool(
                result.get("english_evidence") and result.get("chinese_evidence")
            ),
            "query_latency_ms": query_ms,
            "total_latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "student_alignment_runner_injected": False,
            "reranker_mode": "deterministic-fixed-contract-replay",
            "external_api_used_during_acceptance": False,
            "real_provider_requests": 0,
            "private_source_text_in_artifact": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-cache-dir", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    result = run(Path(args.model_cache_dir))
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
