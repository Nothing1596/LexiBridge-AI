"""Student-owned ConceptQuery and PersonalLearningRecord routes."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from flask import current_app, request

from routes.shared import RouteCoreDependencies
from services import bilingual_evidence_workflow
from services import student_concept_queries


@dataclass(frozen=True)
class StudentConceptQueryModels:
    StudentConceptQuery: Any
    PersonalLearningRecord: Any
    KnowledgeSource: Any
    KnowledgeChunk: Any
    Course: Any
    CourseMember: Any


def register_student_concept_query_routes(
    app,
    *,
    core: RouteCoreDependencies,
    models: StudentConceptQueryModels,
) -> None:
    marker = "student_concept_query_routes"
    registered = app.extensions.setdefault("lexibridge_route_modules", set())
    if marker in registered:
        return
    db = core.db

    def error(reason, message, status, context):
        return core.api_error_with_audit_context(
            reason, message, status, context, {"audit_error_code": reason}
        )

    def student(context=None):
        user, response = core.require_current_user({"student"})
        return user, response

    def membership_active(user_id, course_id):
        return models.CourseMember.query.filter_by(
            user_id=user_id, course_id=course_id, status="active"
        ).first() is not None

    def source_access(user, source, scope):
        if (
            str(source.status or "").lower() != "active"
            or not bool(source.allow_student_search)
        ):
            return False
        if scope == "PERSONAL":
            return (
                str(source.scope_type or "").lower() == "personal"
                and str(source.owner_user_id) == str(user.id)
            )
        return (
            scope == "MANAGED_COURSE"
            and str(source.scope_type or "").lower() in {"course", "managed_course"}
            and source.course_id is not None
            and membership_active(user.id, source.course_id)
        )

    def get_owned_query(user, query_uid):
        query = models.StudentConceptQuery.query.filter_by(
            query_uid=query_uid, student_id=user.id
        ).first()
        if query is None:
            return None
        if query.workspace_scope == "MANAGED_COURSE" and not membership_active(
            user.id, query.course_id
        ):
            return None
        source = models.KnowledgeSource.query.filter_by(source_uid=query.source_uid).first()
        if source is None or not source_access(user, source, query.workspace_scope):
            return None
        return query

    def personal_state(query):
        record = models.PersonalLearningRecord.query.filter_by(
            student_id=query.student_id, result_uid=query.result_uid
        ).first()
        if record is None:
            return {
                "saved": False, "note": "", "understanding_state": "",
                "last_viewed_at": "", "version": 0,
            }
        return {
            "record_uid": record.record_uid,
            "saved": bool(record.saved),
            "note": record.personal_note,
            "understanding_state": record.understanding_state,
            "last_viewed_at": record.last_viewed_at,
            "version": record.version,
        }

    def serialize_query(query):
        raw = json.loads(query.result_json or "{}")
        raw["personal_state"] = personal_state(query)
        return student_concept_queries.serialize_alignment_result(raw)

    def audit(event_type, *, user, query, request_id, action="", result="success"):
        core.audit_record_service.create_audit_record(
            db.session,
            core.audit_record_model,
            {
                "event_type": event_type,
                "target_type": "student_concept_query",
                "target_uid": query.query_uid,
                "result": result,
                "input_payload": {
                    "query_uid": query.query_uid,
                    "student_id": user.id,
                    "workspace_uid": query.workspace_uid,
                    "source_uid": query.source_uid,
                    "action": action,
                },
                "output_payload": {"status": query.processing_status},
                "changed_fields": [action] if action else [],
            },
            audit_context={"actor_id": user.id, "actor_role": "student", "request_id": request_id},
            now_fn=core.current_time_text,
            commit=False,
        )

    def create_query():
        context = core.get_route_audit_context()
        user, response = student(context)
        if response:
            return core.attach_request_id_to_response(response, context)
        context = core.get_route_audit_context(user)
        data = request.get_json(silent=True) or {}
        scope = str(data.get("workspace_scope") or "").strip().upper()
        source = models.KnowledgeSource.query.filter_by(
            source_uid=str(data.get("source_uid") or "").strip()
        ).first()
        if source is None or not source_access(user, source, scope):
            return error("STUDENT_CONCEPT_SOURCE_NOT_ACCESSIBLE", "Source is not available.", 404, context)
        chunk = models.KnowledgeChunk.query.filter_by(
            chunk_uid=str(data.get("chunk_uid") or "").strip(),
            source_uid=source.source_uid,
        ).first()
        if chunk is None or str(chunk.language or "").lower() != "en":
            return error("STUDENT_CONCEPT_SOURCE_CHUNK_INVALID", "English source chunk is not available.", 404, context)
        try:
            selection = student_concept_queries.validate_selection(
                chunk,
                selected_text=data.get("selected_text"),
                selection_start=data.get("selection_start"),
                selection_end=data.get("selection_end"),
            )
        except student_concept_queries.StudentConceptQueryError as exc:
            return error(exc.reason_code, str(exc), 400, context)
        workspace_uid = (
            f"personal:{user.id}" if scope == "PERSONAL" else f"course:{source.course_id}"
        )
        source_version = str(source.version or 1)
        fingerprint = student_concept_queries.build_query_fingerprint(
            student_uid=user.id,
            workspace_scope=scope,
            workspace_uid=workspace_uid,
            source_uid=source.source_uid,
            source_version=source_version,
            chunk_uid=chunk.chunk_uid,
            selection_start=selection.selection_start,
            selection_end=selection.selection_end,
            selected_text=selection.selected_text,
        )
        existing = models.StudentConceptQuery.query.filter_by(
            student_id=user.id, query_fingerprint=fingerprint
        ).first()
        if existing is not None:
            return core.api_success_with_audit_context(
                {"query": serialize_query(existing), "idempotent_replay": True},
                audit_context=context,
            )
        sources = models.KnowledgeSource.query.filter_by(language="zh", status="active").all()
        evidence_scope = student_concept_queries.resolve_evidence_scope(
            sources,
            workspace_scope=scope,
            student_id=user.id,
            course_id=source.course_id if scope == "MANAGED_COURSE" else None,
            allow_platform_governed=bool(current_app.config.get("STUDENT_ALLOW_PLATFORM_EVIDENCE", False)),
        )
        now = core.current_time_text()
        query_uid, result_uid = str(uuid.uuid4()), str(uuid.uuid4())
        runner = current_app.config.get("STUDENT_ALIGNMENT_RUNNER")
        try:
            if not evidence_scope.allowed_source_uids:
                raise student_concept_queries.StudentConceptQueryError(
                    "STUDENT_CONCEPT_CHINESE_EVIDENCE_UNAVAILABLE",
                    "No governed Chinese evidence is available in this workspace.",
                )
            if runner is not None:
                workflow = runner(
                    session=db.session,
                    english_term=selection.selected_text,
                    english_context=selection.bounded_context,
                    allowed_source_uids=evidence_scope.allowed_source_uids,
                    english_source_uid=source.source_uid,
                )
            else:
                workflow = bilingual_evidence_workflow.retrieve_bilingual_evidence(
                    db.session,
                    models.KnowledgeChunk,
                    models.KnowledgeSource,
                    selection.selected_text,
                    course=source.course if scope == "MANAGED_COURSE" else "",
                    chapter=chunk.chapter,
                    filters={
                        "source_uids": evidence_scope.allowed_source_uids,
                        "english_source_uid": source.source_uid,
                    },
                    auto_generate_chinese_candidates=True,
                    english_candidate_uid=f"student:{query_uid}",
                    normalized_english_term=selection.selected_text.casefold(),
                    english_context=selection.bounded_context,
                    discipline=source.discipline,
                )
            raw = student_concept_queries.build_raw_alignment_result(
                workflow,
                query_uid=query_uid,
                result_uid=result_uid,
                workspace_scope=scope,
                workspace_uid=workspace_uid,
                source_uid=source.source_uid,
                source_version=source_version,
                selection=selection,
                created_at=now,
            )
            status = "completed"
            error_code = ""
        except Exception as exc:
            # Query ownership and validated source context remain useful; fail closed.
            failure_code = (
                exc.reason_code
                if isinstance(exc, student_concept_queries.StudentConceptQueryError)
                else "STUDENT_CONCEPT_ALIGNMENT_FAILED"
            )
            raw = {
                "query_uid": query_uid, "result_uid": result_uid,
                "workspace_scope": scope, "workspace_uid": workspace_uid,
                "source_uid": source.source_uid, "source_version": source_version,
                "english_term": selection.selected_text, "selected_text": selection.selected_text,
                "bounded_context": selection.bounded_context,
                "english_evidence": [{
                    "source_uid": source.source_uid, "chunk_uid": chunk.chunk_uid,
                    "page_number": chunk.page_number, "block_uid": chunk.parse_block_uid,
                    "span_start": selection.selection_start, "span_end": selection.selection_end,
                    "snippet": selection.bounded_context,
                }],
                "chinese_evidence": [], "chinese_candidates": [],
                "selected_candidate": None, "qualification": None,
                "risk_labels": [failure_code.lower()], "generated_hints": [],
                "created_at": now, "updated_at": now,
            }
            status = "failed_closed"
            error_code = failure_code
        query = models.StudentConceptQuery(
            query_uid=query_uid, result_uid=result_uid, student_id=user.id,
            workspace_scope=scope, workspace_uid=workspace_uid,
            course_id=source.course_id if scope == "MANAGED_COURSE" else None,
            source_uid=source.source_uid, source_version=source_version,
            chunk_uid=chunk.chunk_uid, selected_text=selection.selected_text,
            selection_start=selection.selection_start, selection_end=selection.selection_end,
            query_fingerprint=fingerprint,
            request_id=str(request.headers.get("Idempotency-Key") or data.get("request_id") or "")[:120],
            evidence_scope_id=evidence_scope.scope_id,
            allowed_source_uids_json=json.dumps(evidence_scope.allowed_source_uids),
            result_json=json.dumps(raw, ensure_ascii=False, sort_keys=True),
            processing_status=status, error_code=error_code,
            created_at=now, updated_at=now,
        )
        db.session.add(query)
        audit("student_concept_query_created", user=user, query=query, request_id=query.request_id)
        db.session.commit()
        return core.api_success_with_audit_context(
            {"query": serialize_query(query), "idempotent_replay": False},
            audit_context=context,
        )

    def list_materials():
        context = core.get_route_audit_context()
        user, response = student(context)
        if response:
            return core.attach_request_id_to_response(response, context)
        context = core.get_route_audit_context(user)
        items = []
        for source in models.KnowledgeSource.query.filter_by(language="en", status="active").all():
            scope = (
                "PERSONAL"
                if str(source.scope_type or "").lower() == "personal"
                else "MANAGED_COURSE"
            )
            if not source_access(user, source, scope):
                continue
            course = db.session.get(models.Course, source.course_id) if source.course_id else None
            items.append({
                "source_uid": source.source_uid,
                "source_version": str(source.version or 1),
                "title": str(source.title or source.name or "")[:220],
                "workspace_scope": scope,
                "workspace_uid": f"personal:{user.id}" if scope == "PERSONAL" else f"course:{source.course_id}",
                "course_name": getattr(course, "name", "") if course else "",
            })
        items.sort(key=lambda item: (item["workspace_scope"], item["title"], item["source_uid"]))
        return core.api_success_with_audit_context({"items": items}, audit_context=context)

    def list_material_chunks(source_uid):
        context = core.get_route_audit_context()
        user, response = student(context)
        if response:
            return core.attach_request_id_to_response(response, context)
        context = core.get_route_audit_context(user)
        source = models.KnowledgeSource.query.filter_by(source_uid=source_uid, language="en", status="active").first()
        scope = (
            "PERSONAL"
            if source is not None and str(source.scope_type or "").lower() == "personal"
            else "MANAGED_COURSE"
        )
        if source is None or not source_access(user, source, scope):
            return error("STUDENT_CONCEPT_SOURCE_NOT_ACCESSIBLE", "Source is not available.", 404, context)
        chunks = models.KnowledgeChunk.query.filter_by(source_uid=source.source_uid, language="en", status="active").order_by(
            models.KnowledgeChunk.chunk_index.asc(), models.KnowledgeChunk.id.asc()
        ).limit(100).all()
        return core.api_success_with_audit_context(
            {
                "source": {
                    "source_uid": source.source_uid,
                    "title": str(source.title or source.name or "")[:220],
                    "source_version": str(source.version or 1),
                    "workspace_scope": scope,
                    "course_id": source.course_id,
                },
                "items": [{
                    "chunk_uid": chunk.chunk_uid,
                    "text": str(chunk.content or "")[:4000],
                    "page_number": chunk.page_number,
                    "block_uid": chunk.parse_block_uid,
                    "heading_path": chunk.source_section or chunk.chapter,
                } for chunk in chunks],
            },
            audit_context=context,
        )

    def get_query(query_uid):
        context = core.get_route_audit_context()
        user, response = student(context)
        if response:
            return core.attach_request_id_to_response(response, context)
        context = core.get_route_audit_context(user)
        query = get_owned_query(user, query_uid)
        if query is None:
            return error("STUDENT_CONCEPT_QUERY_NOT_FOUND", "Query is not available.", 404, context)
        return core.api_success_with_audit_context({"query": serialize_query(query)}, audit_context=context)

    def personal_record(query_uid):
        context = core.get_route_audit_context()
        user, response = student(context)
        if response:
            return core.attach_request_id_to_response(response, context)
        context = core.get_route_audit_context(user)
        query = get_owned_query(user, query_uid)
        if query is None:
            return error("STUDENT_CONCEPT_QUERY_NOT_FOUND", "Query is not available.", 404, context)
        if request.method == "GET":
            return core.api_success_with_audit_context(
                {"personal_state": personal_state(query)},
                audit_context=context,
            )
        data = request.get_json(silent=True) or {}
        allowed = {"saved", "note", "understanding_state", "expected_version"}
        if set(data) - allowed:
            return error("STUDENT_PERSONAL_RECORD_FIELDS_INVALID", "Personal state fields are invalid.", 400, context)
        state = str(data.get("understanding_state") or "").strip().upper()
        if state not in {"", "UNDERSTOOD", "STILL_CONFUSED"}:
            return error("STUDENT_PERSONAL_RECORD_STATE_INVALID", "Understanding state is invalid.", 400, context)
        record = models.PersonalLearningRecord.query.filter_by(
            student_id=user.id, result_uid=query.result_uid
        ).first()
        expected = data.get("expected_version")
        current_version = record.version if record else 0
        try:
            expected_version = int(expected)
        except (TypeError, ValueError):
            expected_version = -1
        if expected_version != current_version:
            return error("STUDENT_PERSONAL_RECORD_VERSION_CONFLICT", "Personal record version is stale.", 409, context)
        now = core.current_time_text()
        if record is None:
            record = models.PersonalLearningRecord(
                student_id=user.id, query_uid=query.query_uid, result_uid=query.result_uid,
                workspace_scope=query.workspace_scope, workspace_uid=query.workspace_uid,
                created_at=now,
            )
            db.session.add(record)
        if "saved" in data:
            record.saved = bool(data["saved"])
        if "note" in data:
            record.personal_note = str(data["note"] or "")[:4000]
        if "understanding_state" in data:
            record.understanding_state = state
        record.last_viewed_at = now
        record.version = current_version + 1
        record.updated_at = now
        audit(
            "personal_learning_record_updated", user=user, query=query,
            request_id=str(request.headers.get("Idempotency-Key") or "")[:120],
            action="personal_state",
        )
        db.session.commit()
        return core.api_success_with_audit_context(
            {"query": serialize_query(query), "personal_state": personal_state(query)},
            audit_context=context,
        )

    app.add_url_rule("/api/student/concept-queries", view_func=create_query, methods=["POST"])
    app.add_url_rule("/api/student/concept-materials", view_func=list_materials, methods=["GET"])
    app.add_url_rule(
        "/api/student/concept-materials/<source_uid>/chunks",
        view_func=list_material_chunks,
        methods=["GET"],
    )
    app.add_url_rule("/api/student/concept-queries/<query_uid>", view_func=get_query, methods=["GET"])
    app.add_url_rule(
        "/api/student/concept-queries/<query_uid>/personal-record",
        view_func=personal_record,
        methods=["GET", "PUT"],
    )
    registered.add(marker)
