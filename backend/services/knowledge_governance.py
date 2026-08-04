"""Knowledge governance service helpers.

The functions in this module keep governance logic independent from Flask app
imports. Callers pass SQLAlchemy sessions and model classes explicitly.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_

from services import audit_records
from services import document_parse_quality
from services import parse_quality_risk


VALID_LANGUAGES = {"en", "zh", "mixed", "unknown", ""}
VALID_SOURCE_TYPES = {
    "course_material",
    "textbook",
    "paper",
    "teacher_upload",
    "student_upload",
    "manual",
    "reference",
    "platform_seed",
    "unknown",
    "",
}
VALID_SOURCE_ROLES = {
    "english_course_material",
    "chinese_reference_material",
    "bilingual_reference",
    "student_private_material",
    "unknown",
    "",
}
VALID_OWNER_TYPES = {"system", "teacher", "student", "admin", "unknown", ""}
VALID_VISIBILITY = {"public", "course", "private", "admin_only", "global", ""}
VALID_TRUST_LEVELS = {
    "official_course",
    "teacher_verified",
    "reference_material",
    "student_uploaded",
    "unknown",
    "low_quality",
    "",
}
VALID_SOURCE_STATUSES = {"active", "draft", "needs_review", "deprecated", "blocked", ""}
VALID_CHUNK_STATUSES = {"active", "needs_review", "deprecated", "blocked", ""}
VALID_EMBEDDING_STATUSES = {"not_started", "pending", "ready", "failed", ""}
VALID_VERSION_CHANGE_TYPES = {"created", "updated", "reingested", "deprecated", "restored"}
VALID_PRINCIPAL_TYPES = {"user", "role", "course", "system"}
VALID_ACCESS_LEVELS = {"read", "write", "admin"}

BLOCKED_PARSE_STATUSES = parse_quality_risk.BLOCKED_QUALITY_STATUSES
REVIEW_PARSE_STATUSES = {
    "partial_text",
    "mixed_quality",
    "ocr_low_confidence",
    "formula_detected",
    "formula_ocr_required",
    "formula_ocr_unavailable",
}


class KnowledgeGovernanceError(ValueError):
    """Base error for knowledge governance service operations."""


class KnowledgeSourceNotFoundError(KnowledgeGovernanceError):
    """Raised when a KnowledgeSource cannot be found."""


class KnowledgeChunkNotFoundError(KnowledgeGovernanceError):
    """Raised when a KnowledgeChunk cannot be found."""


class KnowledgeIngestionBlockedError(KnowledgeGovernanceError):
    """Raised when parse quality blocks governed chunk creation."""


@dataclass(frozen=True)
class ListResult:
    items: list[Any]
    page: int
    per_page: int
    total: int

    @property
    def pagination(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "per_page": self.per_page,
            "total": self.total,
            "has_next": self.page * self.per_page < self.total,
        }


def json_loads(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def normalize_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        value = json_loads(value, [])
    if not isinstance(value, list):
        return [value]
    return [item for item in value if item not in (None, "")]


def dumps_json_list(value: Any) -> str:
    return json_dumps(normalize_list(value))


def content_hash(text: str) -> str:
    normalized = " ".join(str(text or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _clean_enum(value: Any, allowed: set[str], fallback: str) -> str:
    text = str(value or "").strip()
    if text not in allowed:
        return fallback
    return text or fallback


def _page(filters: dict[str, Any]) -> tuple[int, int]:
    page = max(1, int(filters.get("page") or 1))
    per_page = max(1, min(int(filters.get("per_page") or filters.get("page_size") or 20), 100))
    return page, per_page


def _now(now_fn=None) -> str:
    return now_fn() if now_fn else ""


def _quality_flags_from_parse(parse_record: Any, extra: Any = None) -> list[str]:
    flags = set(normalize_list(getattr(parse_record, "quality_flags", []) if parse_record is not None else []))
    if extra is not None:
        flags.update(normalize_list(extra))
    quality_status = str(getattr(parse_record, "quality_status", "") or "")
    if quality_status:
        flags.add(quality_status)
    return sorted(flag for flag in flags if flag)


def _status_from_quality(quality_status: str, default: str = "active") -> str:
    if quality_status in BLOCKED_PARSE_STATUSES:
        return "blocked"
    if quality_status in REVIEW_PARSE_STATUSES:
        return "needs_review"
    return default


def _trust_from_quality(quality_status: str, default: str = "unknown") -> str:
    if quality_status in BLOCKED_PARSE_STATUSES or quality_status in REVIEW_PARSE_STATUSES:
        return "low_quality"
    return default or "unknown"


def _source_snapshot(source: Any) -> dict[str, Any]:
    return {
        "source_uid": getattr(source, "source_uid", ""),
        "title": getattr(source, "title", "") or getattr(source, "source_title", "") or getattr(source, "name", ""),
        "course": getattr(source, "course", ""),
        "chapter": getattr(source, "chapter", ""),
        "language": getattr(source, "language", ""),
        "source_type": getattr(source, "source_type", ""),
        "source_role": getattr(source, "source_role", ""),
        "visibility": getattr(source, "visibility", ""),
        "trust_level": getattr(source, "trust_level", ""),
        "status": getattr(source, "status", ""),
        "parse_uid": getattr(source, "parse_uid", ""),
        "quality_status": getattr(source, "quality_status", ""),
        "version": getattr(source, "version", 1),
    }


def _record_audit(
    session: Any,
    audit_model: Any | None,
    *,
    event_type: str,
    target_type: str,
    target_uid: str,
    input_payload: dict[str, Any] | None = None,
    output_payload: dict[str, Any] | None = None,
    result: str = "success",
    error_code: str = "",
    error_message: str = "",
    audit_context: dict[str, Any] | None = None,
    now_fn=None,
    commit: bool = False,
) -> Any | None:
    if audit_model is None:
        return None
    return audit_records.create_audit_record(
        session,
        audit_model,
        {
            "event_type": event_type,
            "target_type": target_type,
            "target_uid": str(target_uid or ""),
            "source": "api" if audit_context else "service",
            "input_payload": input_payload or {},
            "output_payload": output_payload or {},
            "changed_fields": [],
            "result": result,
            "error_code": error_code,
            "error_message": error_message,
        },
        audit_context=audit_context,
        now_fn=now_fn,
        commit=commit,
    )


def _normalize_source_payload(data: dict[str, Any], now_fn=None) -> dict[str, Any]:
    title = str(data.get("title") or data.get("source_title") or data.get("name") or "").strip()
    if not title:
        raise KnowledgeGovernanceError("KnowledgeSource title is required.")
    quality_status = str(data.get("quality_status") or "").strip()
    source_type = _clean_enum(data.get("source_type"), VALID_SOURCE_TYPES, "unknown")
    source_role = _clean_enum(data.get("source_role"), VALID_SOURCE_ROLES, "unknown")
    trust_level = _clean_enum(
        data.get("trust_level") or _trust_from_quality(quality_status, "unknown"),
        VALID_TRUST_LEVELS,
        "unknown",
    )
    status = _clean_enum(
        data.get("status") or _status_from_quality(quality_status, "active"),
        VALID_SOURCE_STATUSES,
        "active",
    )
    visibility = _clean_enum(data.get("visibility"), VALID_VISIBILITY, "course")
    owner_type = _clean_enum(data.get("owner_type"), VALID_OWNER_TYPES, "unknown")
    language = _clean_enum(data.get("language"), VALID_LANGUAGES, "unknown")
    payload = {
        "source_uid": str(data.get("source_uid") or uuid.uuid4()),
        "title": title,
        "name": str(data.get("name") or title).strip(),
        "source_title": str(data.get("source_title") or title).strip(),
        "course": str(data.get("course") or "").strip(),
        "chapter": str(data.get("chapter") or "").strip(),
        "language": language,
        "source_type": source_type,
        "source_role": source_role,
        "owner_type": owner_type,
        "owner_id": str(data.get("owner_id") or "").strip(),
        "owner_user_id": data.get("owner_user_id"),
        "visibility": visibility,
        "trust_level": trust_level,
        "status": status,
        "parse_uid": str(data.get("parse_uid") or "").strip(),
        "source_filename": str(data.get("source_filename") or "").strip(),
        "file_type": str(data.get("file_type") or "unknown").strip() or "unknown",
        "content_hash": str(data.get("content_hash") or "").strip(),
        "version": int(data.get("version") or 1),
        "license_note": str(data.get("license_note") or "").strip(),
        "quality_status": quality_status,
        "quality_flags": dumps_json_list(data.get("quality_flags", [])),
        "created_by": data.get("created_by"),
        "created_at": data.get("created_at") or _now(now_fn),
        "updated_at": data.get("updated_at") or _now(now_fn),
    }
    for field in (
        "course_id",
        "scope_type",
        "document_id",
        "discipline",
        "knowledge_base_type",
        "access_method",
        "license_status",
        "license_type",
        "authorization_status",
        "source_quality",
        "version_introduced_id",
        "version_removed_id",
        "effective_from",
        "effective_to",
        "update_frequency",
        "allow_full_text_indexing",
        "allow_student_search",
        "allow_derivative_cards",
    ):
        if field in data:
            payload[field] = data[field]
    return payload


def create_knowledge_source(
    session: Any,
    source_model: Any,
    data: dict[str, Any],
    *,
    version_model: Any | None = None,
    audit_model: Any | None = None,
    audit_context: dict[str, Any] | None = None,
    now_fn=None,
    commit: bool = True,
) -> Any:
    payload = _normalize_source_payload(data or {}, now_fn=now_fn)
    source = source_model(**{key: value for key, value in payload.items() if hasattr(source_model, key)})
    session.add(source)
    session.flush()
    if version_model is not None:
        create_knowledge_version(
            session,
            version_model,
            source.source_uid,
            "created",
            version_number=getattr(source, "version", 1) or 1,
            new_content_hash=getattr(source, "content_hash", ""),
            parse_uid=getattr(source, "parse_uid", ""),
            changed_by=getattr(source, "created_by", None),
            change_note="Knowledge source created.",
            now_fn=now_fn,
            commit=False,
        )
    _record_audit(
        session,
        audit_model,
        event_type="knowledge_source_created",
        target_type="knowledge_source",
        target_uid=getattr(source, "source_uid", ""),
        input_payload={
            "parse_uid": getattr(source, "parse_uid", ""),
            "course": getattr(source, "course", ""),
            "language": getattr(source, "language", ""),
            "source_type": getattr(source, "source_type", ""),
        },
        output_payload=_source_snapshot(source),
        audit_context=audit_context,
        now_fn=now_fn,
        commit=False,
    )
    if commit:
        session.commit()
    return source


def get_knowledge_source(session: Any, source_model: Any, source_uid: Any) -> Any:
    source = None
    if isinstance(source_uid, int) or str(source_uid).isdigit():
        source = session.get(source_model, int(source_uid))
    if source is None:
        source = source_model.query.filter_by(source_uid=str(source_uid)).first()
    if source is None:
        raise KnowledgeSourceNotFoundError("KnowledgeSource not found.")
    return source


def list_knowledge_sources(session: Any, source_model: Any, filters: dict[str, Any] | None = None) -> ListResult:
    filters = filters or {}
    page, per_page = _page(filters)
    query = source_model.query
    for field in ("language", "source_type", "source_role", "trust_level", "status"):
        value = str(filters.get(field) or "").strip()
        if value and hasattr(source_model, field):
            query = query.filter_by(**{field: value})
    course = str(filters.get("course") or "").strip()
    if course and hasattr(source_model, "course"):
        query = query.filter(source_model.course == course)
    q = str(filters.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            source_model.name.ilike(like),
            source_model.source_title.ilike(like),
            source_model.title.ilike(like),
            source_model.source_filename.ilike(like),
        ))
    total = query.count()
    items = query.order_by(source_model.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return ListResult(items=items, page=page, per_page=per_page, total=total)


def update_knowledge_source(
    session: Any,
    source_model: Any,
    source_uid: Any,
    patch_data: dict[str, Any],
    *,
    version_model: Any | None = None,
    audit_model: Any | None = None,
    audit_context: dict[str, Any] | None = None,
    now_fn=None,
    commit: bool = True,
) -> Any:
    source = get_knowledge_source(session, source_model, source_uid)
    before = _source_snapshot(source)
    allowed = {
        "title",
        "name",
        "source_title",
        "course",
        "chapter",
        "language",
        "source_type",
        "source_role",
        "owner_type",
        "owner_id",
        "visibility",
        "trust_level",
        "status",
        "license_note",
        "quality_status",
        "quality_flags",
    }
    for field, value in (patch_data or {}).items():
        if field not in allowed:
            continue
        if field == "quality_flags":
            value = dumps_json_list(value)
        setattr(source, field, value)
    source.updated_at = _now(now_fn)
    source.version = int(getattr(source, "version", 1) or 1) + 1
    if version_model is not None:
        create_knowledge_version(
            session,
            version_model,
            source.source_uid,
            "updated",
            version_number=source.version,
            new_content_hash=getattr(source, "content_hash", ""),
            parse_uid=getattr(source, "parse_uid", ""),
            change_note="Knowledge source updated.",
            now_fn=now_fn,
            commit=False,
        )
    _record_audit(
        session,
        audit_model,
        event_type="knowledge_source_updated",
        target_type="knowledge_source",
        target_uid=getattr(source, "source_uid", ""),
        input_payload=patch_data or {},
        output_payload={"before": before, "after": _source_snapshot(source)},
        audit_context=audit_context,
        now_fn=now_fn,
        commit=False,
    )
    if commit:
        session.commit()
    return source


def _chunk_status_from_quality(quality_status: str, explicit_status: str = "") -> str:
    if quality_status in BLOCKED_PARSE_STATUSES:
        return "blocked"
    if quality_status in REVIEW_PARSE_STATUSES:
        return "needs_review"
    return _clean_enum(explicit_status, VALID_CHUNK_STATUSES, "active")


def create_knowledge_chunks(
    session: Any,
    chunk_model: Any,
    source: Any,
    chunks: list[dict[str, Any]],
    *,
    audit_model: Any | None = None,
    audit_context: dict[str, Any] | None = None,
    now_fn=None,
    commit: bool = True,
) -> list[Any]:
    created = []
    source_uid = getattr(source, "source_uid", "") or str(source)
    source_id = getattr(source, "id", None)
    for index, raw in enumerate(chunks or [], start=1):
        text = str(raw.get("text") or raw.get("content") or "").strip()
        if not text:
            continue
        q_status = str(raw.get("quality_status") or getattr(source, "quality_status", "") or "").strip()
        status = _chunk_status_from_quality(q_status, str(raw.get("status") or ""))
        normalized = " ".join(text.split())
        hash_value = str(raw.get("content_hash") or content_hash(text))
        existing = chunk_model.query.filter_by(source_uid=source_uid, content_hash=hash_value).first() if hasattr(chunk_model, "source_uid") else None
        quality_flags = set(normalize_list(raw.get("quality_flags", [])))
        if q_status:
            quality_flags.add(q_status)
        if existing is not None:
            quality_flags.add("duplicate")
        is_blocked = status == "blocked"
        record = chunk_model(
            chunk_uid=str(raw.get("chunk_uid") or uuid.uuid4()),
            source_uid=source_uid,
            document_id=int(raw.get("document_id") or getattr(source, "document_id", 0) or 0),
            source_id=source_id,
            knowledge_source_id=source_id,
            parse_uid=str(raw.get("parse_uid") or getattr(source, "parse_uid", "") or ""),
            parse_block_uid=str(raw.get("parse_block_uid") or ""),
            course_id=raw.get("course_id") or getattr(source, "course_id", None),
            scope_type=str(raw.get("scope_type") or getattr(source, "scope_type", "course") or "course"),
            course=str(raw.get("course") or getattr(source, "course", "") or ""),
            title=str(raw.get("title") or getattr(source, "title", "") or getattr(source, "source_title", "") or getattr(source, "name", "") or ""),
            discipline=str(raw.get("discipline") or getattr(source, "discipline", "") or ""),
            chapter=str(raw.get("chapter") or getattr(source, "chapter", "") or ""),
            chunk_index=int(raw.get("chunk_index") or index),
            content=text,
            normalized_text=str(raw.get("normalized_text") or normalized),
            content_hash=hash_value,
            source_page=str(raw.get("source_page") or raw.get("source_locator") or ""),
            source_slide=str(raw.get("source_slide") or raw.get("slide_number") or ""),
            source_section=str(raw.get("source_section") or raw.get("source_locator") or ""),
            source_locator=str(raw.get("source_locator") or ""),
            page_number=raw.get("page_number"),
            slide_number=raw.get("slide_number"),
            block_type=str(raw.get("block_type") or "text"),
            token_count=raw.get("token_count") or len(normalized.split()),
            char_count=raw.get("char_count") or len(text),
            language=_clean_enum(raw.get("language") or getattr(source, "language", ""), VALID_LANGUAGES, "unknown"),
            knowledge_base_type=str(raw.get("knowledge_base_type") or getattr(source, "knowledge_base_type", "") or ""),
            owner_user_id=str(raw.get("owner_user_id") or getattr(source, "owner_user_id", "") or ""),
            visibility=str(raw.get("visibility") or getattr(source, "visibility", "") or "course"),
            quality_status=q_status,
            quality_flags=dumps_json_list(sorted(flag for flag in quality_flags if flag)),
            trust_level=str(raw.get("trust_level") or getattr(source, "trust_level", "") or "unknown"),
            status=status,
            embedding_status=_clean_enum(raw.get("embedding_status"), VALID_EMBEDDING_STATUSES, "not_started"),
            index_status="blocked" if is_blocked else str(raw.get("index_status") or "indexed"),
            is_duplicate=existing is not None,
            duplicate_of_chunk_id=getattr(existing, "id", None) if existing is not None else None,
            is_active=not is_blocked,
            created_at=raw.get("created_at") or _now(now_fn),
            updated_at=raw.get("updated_at") or _now(now_fn),
        )
        session.add(record)
        created.append(record)
    session.flush()
    _record_audit(
        session,
        audit_model,
        event_type="knowledge_chunks_created",
        target_type="knowledge_source",
        target_uid=source_uid,
        input_payload={"source_uid": source_uid, "chunk_count": len(chunks or [])},
        output_payload={
            "source_uid": source_uid,
            "chunk_count": len(created),
            "quality_status": getattr(source, "quality_status", ""),
        },
        audit_context=audit_context,
        now_fn=now_fn,
        commit=False,
    )
    if commit:
        session.commit()
    return created


def get_knowledge_chunk(session: Any, chunk_model: Any, chunk_uid: Any) -> Any:
    chunk = None
    if isinstance(chunk_uid, int) or str(chunk_uid).isdigit():
        chunk = session.get(chunk_model, int(chunk_uid))
    if chunk is None:
        chunk = chunk_model.query.filter_by(chunk_uid=str(chunk_uid)).first()
    if chunk is None:
        raise KnowledgeChunkNotFoundError("KnowledgeChunk not found.")
    return chunk


def list_knowledge_chunks(session: Any, chunk_model: Any, filters: dict[str, Any] | None = None) -> ListResult:
    filters = filters or {}
    page, per_page = _page(filters)
    query = chunk_model.query
    for field in ("source_uid", "course", "chapter", "language", "quality_status", "trust_level", "status"):
        value = str(filters.get(field) or "").strip()
        if value and hasattr(chunk_model, field):
            query = query.filter_by(**{field: value})
    q = str(filters.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            chunk_model.content.ilike(like),
            chunk_model.normalized_text.ilike(like),
            chunk_model.source_locator.ilike(like),
        ))
    total = query.count()
    items = query.order_by(chunk_model.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return ListResult(items=items, page=page, per_page=per_page, total=total)


def create_knowledge_version(
    session: Any,
    version_model: Any,
    source_uid: str,
    change_type: str,
    *,
    version_number: int = 1,
    previous_content_hash: str = "",
    new_content_hash: str = "",
    parse_uid: str = "",
    changed_by: Any = None,
    change_note: str = "",
    now_fn=None,
    commit: bool = True,
) -> Any:
    change_type = _clean_enum(change_type, VALID_VERSION_CHANGE_TYPES, "updated")
    record = version_model(
        version_uid=str(uuid.uuid4()),
        source_uid=str(source_uid or ""),
        version_number=int(version_number or 1),
        change_type=change_type,
        previous_content_hash=str(previous_content_hash or ""),
        new_content_hash=str(new_content_hash or ""),
        parse_uid=str(parse_uid or ""),
        changed_by=changed_by,
        change_note=str(change_note or ""),
        created_at=_now(now_fn),
    )
    session.add(record)
    if commit:
        session.commit()
    else:
        session.flush()
    return record


def create_permission(
    session: Any,
    permission_model: Any,
    source_uid: str,
    *,
    principal_type: str,
    principal_id: str = "",
    access_level: str = "read",
    now_fn=None,
    commit: bool = True,
) -> Any:
    principal_type = _clean_enum(principal_type, VALID_PRINCIPAL_TYPES, "system")
    access_level = _clean_enum(access_level, VALID_ACCESS_LEVELS, "read")
    record = permission_model(
        permission_uid=str(uuid.uuid4()),
        source_uid=str(source_uid or ""),
        principal_type=principal_type,
        principal_id=str(principal_id or ""),
        access_level=access_level,
        created_at=_now(now_fn),
    )
    session.add(record)
    if commit:
        session.commit()
    else:
        session.flush()
    return record


def serialize_knowledge_source(source: Any) -> dict[str, Any]:
    return {
        "id": getattr(source, "id", None),
        "source_uid": getattr(source, "source_uid", ""),
        "title": getattr(source, "title", "") or getattr(source, "source_title", "") or getattr(source, "name", ""),
        "name": getattr(source, "name", ""),
        "course": getattr(source, "course", ""),
        "course_id": getattr(source, "course_id", None),
        "chapter": getattr(source, "chapter", ""),
        "language": getattr(source, "language", ""),
        "source_type": getattr(source, "source_type", ""),
        "source_role": getattr(source, "source_role", ""),
        "owner_type": getattr(source, "owner_type", ""),
        "owner_id": getattr(source, "owner_id", ""),
        "owner_user_id": getattr(source, "owner_user_id", None),
        "visibility": getattr(source, "visibility", ""),
        "trust_level": getattr(source, "trust_level", ""),
        "status": getattr(source, "status", ""),
        "parse_uid": getattr(source, "parse_uid", ""),
        "source_filename": getattr(source, "source_filename", ""),
        "file_type": getattr(source, "file_type", ""),
        "content_hash": getattr(source, "content_hash", ""),
        "version": getattr(source, "version", 1),
        "license_note": getattr(source, "license_note", ""),
        "quality_status": getattr(source, "quality_status", ""),
        "quality_flags": normalize_list(getattr(source, "quality_flags", [])),
        "created_by": getattr(source, "created_by", None),
        "created_at": getattr(source, "created_at", ""),
        "updated_at": getattr(source, "updated_at", ""),
    }


def serialize_knowledge_chunk(chunk: Any) -> dict[str, Any]:
    return {
        "id": getattr(chunk, "id", None),
        "chunk_uid": getattr(chunk, "chunk_uid", ""),
        "source_uid": getattr(chunk, "source_uid", ""),
        "knowledge_source_id": getattr(chunk, "knowledge_source_id", None),
        "parse_uid": getattr(chunk, "parse_uid", ""),
        "parse_block_uid": getattr(chunk, "parse_block_uid", ""),
        "course": getattr(chunk, "course", ""),
        "chapter": getattr(chunk, "chapter", ""),
        "language": getattr(chunk, "language", ""),
        "chunk_index": getattr(chunk, "chunk_index", 0),
        "text": getattr(chunk, "content", ""),
        "normalized_text": getattr(chunk, "normalized_text", ""),
        "source_locator": getattr(chunk, "source_locator", "") or getattr(chunk, "source_section", "") or getattr(chunk, "source_page", ""),
        "page_number": getattr(chunk, "page_number", None),
        "slide_number": getattr(chunk, "slide_number", None),
        "block_type": getattr(chunk, "block_type", ""),
        "token_count": getattr(chunk, "token_count", None),
        "char_count": getattr(chunk, "char_count", None),
        "content_hash": getattr(chunk, "content_hash", ""),
        "quality_status": getattr(chunk, "quality_status", ""),
        "quality_flags": normalize_list(getattr(chunk, "quality_flags", [])),
        "trust_level": getattr(chunk, "trust_level", ""),
        "status": getattr(chunk, "status", ""),
        "embedding_status": getattr(chunk, "embedding_status", ""),
        "is_duplicate": bool(getattr(chunk, "is_duplicate", False)),
        "duplicate_of_chunk_id": getattr(chunk, "duplicate_of_chunk_id", None),
        "is_active": bool(getattr(chunk, "is_active", True)),
        "created_at": getattr(chunk, "created_at", ""),
        "updated_at": getattr(chunk, "updated_at", ""),
    }


def serialize_knowledge_version(version: Any) -> dict[str, Any]:
    return {
        "id": getattr(version, "id", None),
        "version_uid": getattr(version, "version_uid", ""),
        "source_uid": getattr(version, "source_uid", ""),
        "version_number": getattr(version, "version_number", 1),
        "change_type": getattr(version, "change_type", ""),
        "previous_content_hash": getattr(version, "previous_content_hash", ""),
        "new_content_hash": getattr(version, "new_content_hash", ""),
        "parse_uid": getattr(version, "parse_uid", ""),
        "changed_by": getattr(version, "changed_by", None),
        "change_note": getattr(version, "change_note", ""),
        "created_at": getattr(version, "created_at", ""),
    }


def serialize_permission(permission: Any) -> dict[str, Any]:
    return {
        "id": getattr(permission, "id", None),
        "permission_uid": getattr(permission, "permission_uid", ""),
        "source_uid": getattr(permission, "source_uid", ""),
        "principal_type": getattr(permission, "principal_type", ""),
        "principal_id": getattr(permission, "principal_id", ""),
        "access_level": getattr(permission, "access_level", ""),
        "created_at": getattr(permission, "created_at", ""),
    }


def build_knowledge_source_from_parse_record(parse_record: Any, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = metadata or {}
    quality_status = str(getattr(parse_record, "quality_status", "") or metadata.get("quality_status", "") or "")
    title = str(metadata.get("title") or getattr(parse_record, "source_filename", "") or "Untitled knowledge source").strip()
    return {
        "title": title,
        "name": title,
        "source_title": title,
        "course": str(metadata.get("course") or "").strip(),
        "chapter": str(metadata.get("chapter") or "").strip(),
        "language": _clean_enum(metadata.get("language"), VALID_LANGUAGES, "unknown"),
        "source_type": _clean_enum(metadata.get("source_type"), VALID_SOURCE_TYPES, "unknown"),
        "source_role": _clean_enum(metadata.get("source_role"), VALID_SOURCE_ROLES, "unknown"),
        "owner_type": _clean_enum(metadata.get("owner_type"), VALID_OWNER_TYPES, "unknown"),
        "owner_id": str(metadata.get("owner_id") or "").strip(),
        "visibility": _clean_enum(metadata.get("visibility"), VALID_VISIBILITY, "course"),
        "trust_level": _clean_enum(
            metadata.get("trust_level") or _trust_from_quality(quality_status, "unknown"),
            VALID_TRUST_LEVELS,
            "unknown",
        ),
        "status": _status_from_quality(quality_status, "active"),
        "parse_uid": getattr(parse_record, "parse_uid", ""),
        "source_filename": getattr(parse_record, "source_filename", ""),
        "file_type": getattr(parse_record, "file_type", "unknown") or "unknown",
        "content_hash": str(metadata.get("content_hash") or ""),
        "version": int(metadata.get("version") or 1),
        "license_note": str(metadata.get("license_note") or "").strip(),
        "quality_status": quality_status,
        "quality_flags": _quality_flags_from_parse(parse_record, metadata.get("quality_flags")),
        "created_by": metadata.get("created_by"),
        "course_id": metadata.get("course_id"),
        "scope_type": metadata.get("scope_type", "course"),
        "document_id": metadata.get("document_id"),
        "owner_user_id": metadata.get("owner_user_id"),
        "knowledge_base_type": metadata.get("knowledge_base_type", ""),
        "access_method": metadata.get("access_method", "document_parse"),
    }


def build_knowledge_chunks_from_parse_blocks(
    parse_record: Any,
    parse_blocks: list[Any],
    source_uid: str,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    metadata = metadata or {}
    quality_status = str(getattr(parse_record, "quality_status", "") or "")
    if quality_status in BLOCKED_PARSE_STATUSES:
        return []
    chunks = []
    record_flags = _quality_flags_from_parse(parse_record, metadata.get("quality_flags"))
    for index, block in enumerate(parse_blocks or [], start=1):
        text = str(getattr(block, "text", "") or "").strip()
        if not text:
            continue
        block_flags = set(record_flags)
        block_flags.update(normalize_list(getattr(block, "quality_flags", [])))
        chunks.append({
            "source_uid": source_uid,
            "parse_uid": getattr(parse_record, "parse_uid", ""),
            "parse_block_uid": getattr(block, "block_uid", ""),
            "course": str(metadata.get("course") or "").strip(),
            "course_id": metadata.get("course_id"),
            "chapter": str(metadata.get("chapter") or "").strip(),
            "language": _clean_enum(metadata.get("language"), VALID_LANGUAGES, "unknown"),
            "chunk_index": index,
            "text": text,
            "source_locator": getattr(block, "source_locator", "") or f"block:{index}",
            "page_number": getattr(block, "page_number", None),
            "slide_number": getattr(block, "slide_number", None),
            "block_type": getattr(block, "block_type", "text") or "text",
            "quality_status": quality_status,
            "quality_flags": sorted(flag for flag in block_flags if flag),
            "trust_level": _trust_from_quality(quality_status, str(metadata.get("trust_level") or "unknown")),
            "status": _chunk_status_from_quality(quality_status),
            "embedding_status": "not_started",
            "document_id": metadata.get("document_id") or 0,
            "scope_type": metadata.get("scope_type", "course"),
            "knowledge_base_type": metadata.get("knowledge_base_type", ""),
            "owner_user_id": metadata.get("owner_user_id", ""),
        })
    return chunks


def record_knowledge_ingestion_blocked(
    session: Any,
    audit_model: Any | None,
    *,
    parse_record: Any,
    blocked_reason: str,
    audit_context: dict[str, Any] | None = None,
    now_fn=None,
    commit: bool = True,
) -> Any | None:
    record = _record_audit(
        session,
        audit_model,
        event_type="knowledge_ingestion_blocked",
        target_type="document_parse_record",
        target_uid=getattr(parse_record, "parse_uid", ""),
        input_payload={
            "parse_uid": getattr(parse_record, "parse_uid", ""),
            "source_filename": getattr(parse_record, "source_filename", ""),
            "file_type": getattr(parse_record, "file_type", ""),
        },
        output_payload={
            "parse_status": getattr(parse_record, "parse_status", ""),
            "quality_status": getattr(parse_record, "quality_status", ""),
            "blocked_reason": blocked_reason,
        },
        result="error",
        error_code="blocked_by_quality_gate",
        error_message=blocked_reason,
        audit_context=audit_context,
        now_fn=now_fn,
        commit=False,
    )
    if commit:
        session.commit()
    return record
