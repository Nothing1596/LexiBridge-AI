"""Student self-service one-concept query contracts and safe adapters.

The module composes the governed Task 12 services.  It does not implement a
student-only retrieval or alignment algorithm and never treats published cards
as query results.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

from services import student_first_boundaries


CONTRACT_VERSION = "student-concept-query@1.0.0"
ALIGNMENT_RESULT_CONTRACT_VERSION = "student-alignment-result@1.1.0"
ALIGNMENT_POLICY_VERSION = "governed-bilingual-evidence-qualification@1.1.0"
MAX_SELECTION_CHARS = 180
MAX_CONTEXT_CHARS = 800
CONTEXT_WINDOW_CHARS = 360


class StudentConceptQueryError(ValueError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class ValidatedSelection:
    selected_text: str
    selection_start: int
    selection_end: int
    bounded_context: str
    provenance: dict[str, Any]


@dataclass(frozen=True)
class EvidenceScope:
    scope_id: str
    workspace_scope: str
    allowed_source_uids: tuple[str, ...]
    platform_governed_included: bool


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _source_is_governed(source: Any) -> bool:
    if _text(_field(source, "language")).lower() not in {"zh", "chinese"}:
        return False
    if _text(_field(source, "status", "active")).lower() != "active":
        return False
    if not bool(_field(source, "allow_student_search", False)):
        return False
    authorization = _text(_field(source, "authorization_status")).lower()
    license_status = _text(_field(source, "license_status")).lower()
    return authorization in {
        "authorized",
        "approved",
        "granted",
        "allowed_for_private_use",
        "allowed_for_course_use",
    } and license_status not in {
        "", "unknown", "blocked", "rejected",
    }


def validate_selection(
    chunk: Any,
    *,
    selected_text: Any,
    selection_start: Any,
    selection_end: Any,
) -> ValidatedSelection:
    content = str(_field(chunk, "content", "") or "")
    selected = str(selected_text or "")
    if not selected.strip():
        raise StudentConceptQueryError(
            "STUDENT_CONCEPT_SELECTION_EMPTY", "Select an English concept."
        )
    try:
        start, end = int(selection_start), int(selection_end)
    except (TypeError, ValueError) as exc:
        raise StudentConceptQueryError(
            "STUDENT_CONCEPT_SELECTION_SPAN_INVALID", "Selection offsets are invalid."
        ) from exc
    if start < 0 or end <= start or end > len(content):
        raise StudentConceptQueryError(
            "STUDENT_CONCEPT_SELECTION_SPAN_INVALID", "Selection offsets are outside the source chunk."
        )
    if len(selected) > MAX_SELECTION_CHARS:
        raise StudentConceptQueryError(
            "STUDENT_CONCEPT_SELECTION_TOO_LONG", "Select a bounded term or short phrase."
        )
    if not re.search(r"[A-Za-z]", selected) or not re.search(r"[A-Za-z]{2,}", selected):
        raise StudentConceptQueryError(
            "STUDENT_CONCEPT_SELECTION_NOT_CONCEPT", "Selection must contain a meaningful English term."
        )
    if content[start:end] != selected:
        raise StudentConceptQueryError(
            "STUDENT_CONCEPT_SELECTION_TEXT_MISMATCH", "Selected text does not match the source."
        )
    left = max(0, start - CONTEXT_WINDOW_CHARS)
    right = min(len(content), end + CONTEXT_WINDOW_CHARS)
    context = content[left:right][:MAX_CONTEXT_CHARS]
    return ValidatedSelection(
        selected_text=selected.strip(),
        selection_start=start,
        selection_end=end,
        bounded_context=context,
        provenance={
            "chunk_uid": _text(_field(chunk, "chunk_uid")) or str(_field(chunk, "id", "")),
            "block_uid": _text(_field(chunk, "parse_block_uid")),
            "page_number": _field(chunk, "page_number"),
            "span_start": start,
            "span_end": end,
            "heading_path": _text(_field(chunk, "section_title") or _field(chunk, "source_section")),
        },
    )


def build_query_fingerprint(**values: Any) -> str:
    identity = {
        "student_uid": _text(values.get("student_uid")),
        "workspace_scope": _text(values.get("workspace_scope")).upper(),
        "workspace_uid": _text(values.get("workspace_uid")),
        "source_uid": _text(values.get("source_uid")),
        "source_version": _text(values.get("source_version")),
        "chunk_uid": _text(values.get("chunk_uid")),
        "selection_start": int(values.get("selection_start") or 0),
        "selection_end": int(values.get("selection_end") or 0),
        "selected_text": " ".join(_text(values.get("selected_text")).casefold().split()),
        "alignment_policy_version": _text(
            values.get("alignment_policy_version") or ALIGNMENT_POLICY_VERSION
        ),
    }
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def resolve_evidence_scope(
    sources: Iterable[Any],
    *,
    workspace_scope: Any,
    student_id: int,
    course_id: int | None,
    allow_platform_governed: bool,
) -> EvidenceScope:
    scope = _text(workspace_scope).upper()
    if scope not in {"PERSONAL", "MANAGED_COURSE"}:
        raise StudentConceptQueryError(
            "STUDENT_CONCEPT_WORKSPACE_INVALID", "Workspace scope is invalid."
        )
    allowed: list[str] = []
    platform_included = False
    for source in sources:
        if not _source_is_governed(source):
            continue
        source_scope = _text(_field(source, "scope_type")).lower()
        visibility = _text(_field(source, "visibility")).lower()
        owner_id = _field(source, "owner_user_id")
        source_course_id = _field(source, "course_id")
        is_platform = source_scope in {"global", "platform"} and visibility in {
            "global", "platform", "public",
        }
        permitted = False
        if scope == "PERSONAL":
            permitted = source_scope == "personal" and str(owner_id) == str(student_id)
        else:
            permitted = (
                source_scope in {"course", "managed_course"}
                and course_id is not None
                and str(source_course_id) == str(course_id)
                and visibility in {"course", "course_shared"}
            )
        if is_platform and allow_platform_governed:
            permitted = True
            platform_included = True
        if permitted:
            uid = _text(_field(source, "source_uid"))
            if uid:
                allowed.append(uid)
    allowed_uids = tuple(sorted(set(allowed)))
    scope_material = f"{scope}:{student_id}:{course_id or ''}:{','.join(allowed_uids)}"
    return EvidenceScope(
        scope_id=hashlib.sha256(scope_material.encode()).hexdigest()[:24],
        workspace_scope=scope,
        allowed_source_uids=allowed_uids,
        platform_governed_included=platform_included,
    )


def alignment_status_from_qualification(qualification: Any) -> str:
    decision = _text(
        qualification.get("decision") if isinstance(qualification, dict) else qualification
    ).upper()
    if decision == "QUALIFIED":
        return "READY"
    if decision == "REVIEW_REQUIRED":
        return "REVIEW_REQUIRED"
    return "NOT_READY"


def serialize_alignment_result(result: dict[str, Any]) -> dict[str, Any]:
    status = alignment_status_from_qualification(result.get("qualification"))
    selected = result.get("selected_candidate") if isinstance(result.get("selected_candidate"), dict) else {}
    raw = {
        "alignment_result_uid": result.get("result_uid"),
        "workspace_scope": result.get("workspace_scope"),
        "alignment_status": status,
        "english_term": result.get("english_term"),
        "chinese_term": selected.get("text") or selected.get("chinese_term"),
        "english_evidence": result.get("english_evidence", []),
        "chinese_evidence": result.get("chinese_evidence", []),
        "chinese_candidates": result.get("chinese_candidates", []),
        "generated_hints": result.get("generated_hints", []),
    }
    base = student_first_boundaries.serialize_student_alignment_result(raw)
    recommended = None
    if status in {"READY", "REVIEW_REQUIRED"} and base["chinese_term"]:
        recommended = {
            "candidate_uid": _text(selected.get("candidate_uid")),
            "text": base["chinese_term"],
            "evidence_backed": True,
        }
    student_explanations = {
        "READY": "已在独立中文资料中找到有双侧证据支持的概念对应。",
        "REVIEW_REQUIRED": "找到了有证据的候选，但当前证据不足以唯一确认。",
        "NOT_READY": "当前没有在独立中文资料中找到足够可靠的概念对应。",
    }
    student_risk_summaries = {
        "READY": [],
        "REVIEW_REQUIRED": ["存在多个可能对应或概念范围不确定。"],
        "NOT_READY": ["请补充受治理的中文资料，或重新选择更明确的英文概念。"],
    }
    return {
        **base,
        "contract_id": ALIGNMENT_RESULT_CONTRACT_VERSION,
        "result_uid": _text(result.get("result_uid")),
        "query_uid": _text(result.get("query_uid")),
        "result_version": int(result.get("result_version") or 1),
        "workspace_uid": _text(result.get("workspace_uid")),
        "source_uid": _text(result.get("source_uid")),
        "source_version": _text(result.get("source_version")),
        "selected_text": _text(result.get("selected_text")),
        "bounded_context": str(result.get("bounded_context") or "")[:MAX_CONTEXT_CHARS],
        "recommended_chinese_concept": recommended,
        "student_explanation": student_explanations[status],
        "student_risk_summary": student_risk_summaries[status],
        "evidence_complete": bool(base["english_evidence"] and base["chinese_evidence"]),
        "generated_hint_present": bool(base["generated_hints"]),
        "personal_state": dict(result.get("personal_state") or {}),
        "created_at": _text(result.get("created_at")),
        "updated_at": _text(result.get("updated_at")),
    }


def build_raw_alignment_result(
    workflow_result: Any,
    *,
    query_uid: str,
    result_uid: str,
    workspace_scope: str,
    workspace_uid: str,
    source_uid: str,
    source_version: str,
    selection: ValidatedSelection,
    created_at: str,
) -> dict[str, Any]:
    """Adapt the existing Task 12 workflow output to the student read model."""
    qualification = getattr(workflow_result, "evidence_qualification", None)
    selected = getattr(workflow_result, "selected_chinese_candidate", None) or {}
    candidates = []
    for item in getattr(workflow_result, "chinese_term_candidates", []) or []:
        candidate = dict(item)
        candidate["text"] = candidate.get("text") or candidate.get("chinese_term")
        candidate["evidence_backed"] = bool(
            candidate.get("source_uid") and candidate.get("chunk_uid")
        )
        candidate["generated"] = False
        candidates.append(candidate)
    if not selected:
        production_pairs = list(
            getattr(workflow_result, "bilingual_pair_candidates", []) or []
        )
        top1 = next(
            (
                item for item in production_pairs
                if int(item.get("rank") or 0) == 1
            ),
            None,
        )
        if top1 is not None:
            selected_uid = _text(top1.get("chinese_candidate_uid"))
            selected = next(
                (
                    candidate for candidate in candidates
                    if _text(candidate.get("candidate_uid")) == selected_uid
                ),
                {},
            )
    english_evidence = [
        dict(item) for item in getattr(workflow_result, "english_evidence_candidates", []) or []
    ]
    chinese_evidence = [
        dict(item) for item in getattr(workflow_result, "chinese_evidence_candidates", []) or []
    ]
    return {
        "query_uid": query_uid,
        "result_uid": result_uid,
        "result_version": 1,
        "workspace_scope": workspace_scope,
        "workspace_uid": workspace_uid,
        "source_uid": source_uid,
        "source_version": source_version,
        "english_term": getattr(workflow_result, "english_term", selection.selected_text),
        "selected_text": selection.selected_text,
        "bounded_context": selection.bounded_context,
        "english_evidence": english_evidence,
        "chinese_evidence": chinese_evidence,
        "chinese_candidates": candidates,
        "selected_candidate": selected,
        "qualification": qualification,
        "risk_labels": list(getattr(workflow_result, "risk_labels", []) or []),
        "generated_hints": [],
        "created_at": created_at,
        "updated_at": created_at,
    }
