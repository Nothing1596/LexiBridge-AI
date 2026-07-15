"""Create safe ConceptAlignmentCard drafts from bilingual evidence retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services import audit_records
from services import bilingual_evidence_workflow
from services import concept_alignment_cards
from services import parse_quality_risk


class ConceptCardDraftError(ValueError):
    """Raised for controlled Concept Card draft creation failures."""


@dataclass(frozen=True)
class ConceptCardDraftResult:
    card: Any | None
    bilingual_result: bilingual_evidence_workflow.BilingualEvidenceResult
    draft_payload: dict[str, Any]
    created: bool
    reused: bool = False


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def determine_draft_status_from_evidence_risks(
    risk_labels: list[str],
    english_candidates: list[dict[str, Any]],
    chinese_candidates: list[dict[str, Any]],
) -> str:
    del english_candidates, chinese_candidates
    if "bilingual_alignment_not_verified" in set(risk_labels or []):
        return "needs_review"
    return "needs_review"


def validate_draft_payload_safety(payload: dict[str, Any]) -> dict[str, Any]:
    draft = dict(payload or {})
    risk_labels = parse_quality_risk.normalize_labels(draft.get("risk_labels", []))
    risk_labels = parse_quality_risk.merge_risk_labels(risk_labels, ["bilingual_alignment_not_verified"])
    draft["risk_labels"] = risk_labels
    draft["status"] = determine_draft_status_from_evidence_risks(
        risk_labels,
        draft.get("english_evidence", []) or [],
        draft.get("chinese_evidence", []) or [],
    )
    draft["confidence_score"] = None
    draft["model_name"] = None
    draft["prompt_version"] = None
    draft["alignment_reason"] = _text(draft.get("alignment_reason"))
    if draft.get("status") == "approved":
        raise ConceptCardDraftError("draft-from-evidence cannot create approved ConceptAlignmentCard.")
    if not _text(draft.get("english_term")):
        raise ConceptCardDraftError("english_term is required.")
    if not _text(draft.get("course")):
        raise ConceptCardDraftError("course is required.")
    return draft


def build_draft_payload_from_bilingual_evidence(
    session: Any,
    chunk_model: Any,
    source_model: Any,
    input_data: dict[str, Any],
    *,
    concept_card_model: Any | None = None,
    term_model: Any | None = None,
    terminology_card_model: Any | None = None,
    audit_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bilingual_evidence_workflow.BilingualEvidenceResult]:
    query = bilingual_evidence_workflow.build_bilingual_evidence_query(input_data)
    bilingual_result = bilingual_evidence_workflow.retrieve_bilingual_evidence(
        session,
        chunk_model,
        source_model,
        query["english_term"],
        chinese_term=query["chinese_term"],
        course=query["course"],
        chapter=query["chapter"],
        concept_scope=query["concept_scope"],
        limit=query["limit"],
        filters=query["filters"],
        auto_generate_chinese_candidates=query["auto_generate_chinese_candidates"],
        candidate_limit=query["candidate_limit"],
        selected_chinese_candidate_uid=query["selected_chinese_candidate_uid"],
        concept_card_model=concept_card_model,
        term_model=term_model,
        terminology_card_model=terminology_card_model,
        audit_context=audit_context,
    )
    draft_payload = validate_draft_payload_safety(bilingual_result.draft_payload)
    if _text(input_data.get("status")).lower() == "approved":
        draft_payload["risk_labels"] = parse_quality_risk.merge_risk_labels(
            draft_payload.get("risk_labels", []),
            ["requested_approved_downgraded"],
        )
        draft_payload["status"] = "needs_review"
    return draft_payload, bilingual_result


def find_existing_draft(session: Any, card_model: Any, draft_payload: dict[str, Any]) -> Any | None:
    return card_model.query.filter_by(
        english_term=_text(draft_payload.get("english_term")),
        chinese_term=_text(draft_payload.get("chinese_term")),
        course=_text(draft_payload.get("course")),
        chapter=_text(draft_payload.get("chapter")),
        retrieval_version=_text(draft_payload.get("retrieval_version")),
    ).filter(card_model.status.in_(["draft", "needs_review"])).order_by(card_model.id.desc()).first()


def _audit_summary_payload(
    draft_payload: dict[str, Any],
    bilingual_result: bilingual_evidence_workflow.BilingualEvidenceResult,
    *,
    card_uid: str = "",
    created: bool = False,
) -> dict[str, Any]:
    english_candidates = bilingual_result.english_evidence_candidates
    chinese_candidates = bilingual_result.chinese_evidence_candidates
    return {
        "card_uid": card_uid,
        "created": created,
        "english_result_count": len(english_candidates),
        "chinese_result_count": len(chinese_candidates),
        "top_english_chunk_uids": [item.get("chunk_uid", "") for item in english_candidates[:5]],
        "top_chinese_chunk_uids": [item.get("chunk_uid", "") for item in chinese_candidates[:5]],
        "risk_labels": draft_payload.get("risk_labels", []),
        "status": draft_payload.get("status", ""),
        "retrieval_version": draft_payload.get("retrieval_version", ""),
    }


def record_draft_audit(
    session: Any,
    audit_model: Any | None,
    *,
    event_type: str,
    draft_payload: dict[str, Any] | None = None,
    bilingual_result: bilingual_evidence_workflow.BilingualEvidenceResult | None = None,
    card_uid: str = "",
    created: bool = False,
    result: str = "success",
    error_code: str = "",
    error_message: str = "",
    audit_context: dict[str, Any] | None = None,
    now_fn=None,
    commit: bool = False,
) -> Any | None:
    if audit_model is None:
        return None
    draft_payload = dict(draft_payload or {})
    output_payload = {}
    if bilingual_result is not None:
        output_payload = _audit_summary_payload(
            draft_payload,
            bilingual_result,
            card_uid=card_uid,
            created=created,
        )
    return audit_records.create_audit_record(
        session,
        audit_model,
        {
            "event_type": event_type,
            "target_type": "concept_alignment_card",
            "target_uid": card_uid,
            "source": "api" if audit_context else "service",
            "input_payload": {
                "english_term": _text(draft_payload.get("english_term"))[:240],
                "chinese_term": _text(draft_payload.get("chinese_term"))[:240],
                "course": _text(draft_payload.get("course"))[:160],
                "chapter": _text(draft_payload.get("chapter"))[:160],
            },
            "output_payload": output_payload,
            "changed_fields": [],
            "result": result,
            "error_code": error_code,
            "error_message": error_message,
        },
        audit_context=audit_context,
        now_fn=now_fn,
        commit=commit,
    )


def create_concept_card_draft_from_evidence(
    session: Any,
    *,
    card_model: Any,
    chunk_model: Any,
    source_model: Any,
    input_data: dict[str, Any],
    term_model: Any | None = None,
    terminology_card_model: Any | None = None,
    audit_model: Any | None = None,
    actor: Any = None,
    audit_context: dict[str, Any] | None = None,
    now_fn=None,
    force_create: bool = False,
    commit: bool = True,
) -> ConceptCardDraftResult:
    try:
        draft_payload, bilingual_result = build_draft_payload_from_bilingual_evidence(
            session,
            chunk_model,
            source_model,
            input_data,
            concept_card_model=card_model,
            term_model=term_model,
            terminology_card_model=terminology_card_model,
            audit_context=audit_context,
        )
        record_draft_audit(
            session,
            audit_model,
            event_type="concept_card_draft_payload_created",
            draft_payload=draft_payload,
            bilingual_result=bilingual_result,
            created=False,
            audit_context=audit_context,
            now_fn=now_fn,
            commit=False,
        )
        if not force_create:
            existing = find_existing_draft(session, card_model, draft_payload)
            if existing is not None:
                record_draft_audit(
                    session,
                    audit_model,
                    event_type="concept_card_draft_reused",
                    draft_payload=draft_payload,
                    bilingual_result=bilingual_result,
                    card_uid=getattr(existing, "card_uid", ""),
                    created=False,
                    audit_context=audit_context,
                    now_fn=now_fn,
                    commit=False,
                )
                if commit:
                    session.commit()
                else:
                    session.flush()
                return ConceptCardDraftResult(
                    card=existing,
                    bilingual_result=bilingual_result,
                    draft_payload=draft_payload,
                    created=False,
                    reused=True,
                )
        create_payload = dict(draft_payload)
        create_payload["created_by"] = input_data.get("created_by")
        card = concept_alignment_cards.create_concept_card(
            session,
            card_model,
            create_payload,
            audit_model=audit_model,
            actor=actor,
            audit_context=audit_context,
            source="api" if audit_context else "service",
            now_fn=now_fn,
            commit=False,
        )
        record_draft_audit(
            session,
            audit_model,
            event_type="concept_card_draft_created",
            draft_payload=draft_payload,
            bilingual_result=bilingual_result,
            card_uid=getattr(card, "card_uid", ""),
            created=True,
            audit_context=audit_context,
            now_fn=now_fn,
            commit=False,
        )
        if commit:
            session.commit()
        else:
            session.flush()
        return ConceptCardDraftResult(
            card=card,
            bilingual_result=bilingual_result,
            draft_payload=draft_payload,
            created=True,
            reused=False,
        )
    except Exception as exc:
        session.rollback()
        record_draft_audit(
            session,
            audit_model,
            event_type="concept_card_draft_creation_failed",
            draft_payload=input_data or {},
            result="error",
            error_code="concept_card_draft_creation_failed",
            error_message=str(exc),
            audit_context=audit_context,
            now_fn=now_fn,
            commit=True if audit_model is not None else False,
        )
        raise


def serialize_concept_card_draft_result(
    card: Any | None,
    bilingual_result: bilingual_evidence_workflow.BilingualEvidenceResult,
    *,
    draft_payload: dict[str, Any] | None = None,
    card_serializer=None,
    created: bool = True,
    reused: bool = False,
) -> dict[str, Any]:
    return {
        "created": bool(created),
        "reused": bool(reused),
        "card": card_serializer(card) if card is not None and card_serializer else None,
        "draft_payload": dict(draft_payload or bilingual_result.draft_payload),
        "english_evidence_candidates": [
            dict(candidate) for candidate in bilingual_result.english_evidence_candidates
        ],
        "chinese_evidence_candidates": [
            dict(candidate) for candidate in bilingual_result.chinese_evidence_candidates
        ],
        "chinese_term_candidates": [
            dict(candidate) for candidate in bilingual_result.chinese_term_candidates
        ],
        "selected_chinese_candidate": (
            dict(bilingual_result.selected_chinese_candidate)
            if bilingual_result.selected_chinese_candidate else None
        ),
        "risk_labels": list((draft_payload or bilingual_result.draft_payload).get("risk_labels", bilingual_result.risk_labels)),
    }
