"""Concept Card teacher review route registration.

This module is a staged extraction from ``backend/app.py``. It keeps the
teacher/admin review route handlers thin and delegates review status changes,
policy gates, risk overrides, ReviewRecord creation, and AuditRecord creation
to the existing service layer. It does not import ``backend.app`` or create
application/database objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import request

from routes.shared import RouteCoreDependencies
from services import alignment_verification as alignment_verification_service
from services import concept_alignment_cards as concept_card_service
from services import concept_card_review as concept_card_review_service
from services import course_review_policy as course_review_policy_service


ROUTE_MARKER = "concept_card_review_routes"
TARGET_ROUTES = {
    "/api/concept-cards/review-queue": {
        "endpoint": "concept_card_review_queue_api",
        "method": "GET",
    },
    "/api/concept-cards/<card_uid>/reviews": {
        "endpoint": "concept_card_reviews_api",
        "method": "GET",
    },
    "/api/concept-cards/<card_uid>/review": {
        "endpoint": "concept_card_review_action_api",
        "method": "POST",
    },
    "/api/concept-cards/<card_uid>/assign-reviewer": {
        "endpoint": "concept_card_assign_reviewer_api",
        "method": "POST",
    },
}


@dataclass(frozen=True)
class ConceptCardReviewModels:
    """Domain model dependencies for Concept Card review routes."""

    ConceptAlignmentCard: Any
    ConceptCardReviewRecord: Any
    ConceptCardReviewAssignment: Any
    CourseReviewPolicy: Any
    CourseReviewPermission: Any
    AlignmentVerificationRun: Any


def register_concept_card_review_routes(
    app,
    *,
    core: RouteCoreDependencies,
    models: ConceptCardReviewModels,
) -> None:
    """Register teacher/admin Concept Card review routes on an existing Flask app."""

    registered = app.extensions.setdefault("lexibridge_route_modules", set())
    if ROUTE_MARKER in registered:
        return

    _assert_no_duplicate_target_routes(app)

    db = core.db

    def concept_card_review_error_response(exc, audit_context=None):
        if isinstance(exc, concept_card_service.ConceptCardNotFoundError):
            return core.api_error_with_audit_context(
                "RESOURCE_NOT_FOUND",
                str(exc),
                404,
                audit_context,
                {"audit_error_code": "concept_card_not_found"},
            )
        return core.api_error_with_audit_context(
            "VALIDATION_ERROR",
            str(exc),
            400,
            audit_context,
            {"audit_error_code": "concept_card_review_validation_error"},
        )

    def reviewer_allowed_courses(user):
        if getattr(user, "role", "") == "admin":
            return None
        permissions = course_review_policy_service.get_reviewer_permissions(
            db.session,
            models.CourseReviewPermission,
            reviewer_id=getattr(user, "id", None),
            course=None,
        )
        return sorted({item.course for item in permissions if item.status == "active" and item.can_review})

    def concept_card_review_ui_summary(card):
        latest_review = (
            models.ConceptCardReviewRecord.query.filter_by(card_uid=card.card_uid)
            .order_by(models.ConceptCardReviewRecord.id.desc())
            .first()
        )
        assignment = (
            models.ConceptCardReviewAssignment.query.filter_by(card_uid=card.card_uid, assignment_status="active")
            .order_by(models.ConceptCardReviewAssignment.id.desc())
            .first()
        )
        verification_run = (
            models.AlignmentVerificationRun.query.filter_by(card_uid=card.card_uid)
            .order_by(models.AlignmentVerificationRun.id.desc())
            .first()
        )
        return {
            "latest_review_summary": concept_card_review_service.serialize_review_record(latest_review) if latest_review else None,
            "assignment_summary": concept_card_review_service.serialize_assignment(assignment) if assignment else None,
            "verification_summary": alignment_verification_service.serialize_alignment_verification_run(verification_run) if verification_run else None,
        }

    def concept_card_review_queue_api():
        audit_context = core.get_route_audit_context()
        user, error_response = core.require_current_user({"teacher", "admin"})
        if error_response:
            return core.attach_request_id_to_response(error_response, audit_context)
        audit_context = core.get_route_audit_context(user)
        filters = request.args.to_dict()
        allowed_courses = reviewer_allowed_courses(user)
        if allowed_courses is not None:
            requested_course = str(filters.get("course") or "").strip()
            if requested_course and requested_course not in allowed_courses:
                filters["courses"] = ["__no_course_review_permission__"]
            else:
                filters["courses"] = allowed_courses or ["__no_course_review_permission__"]
        result = concept_card_review_service.get_review_queue(
            db.session,
            models.ConceptAlignmentCard,
            filters,
        )
        items = []
        for card in result.items:
            data = concept_card_review_service.serialize_review_queue_item(card)
            data.update(concept_card_review_ui_summary(card))
            items.append(data)
        return core.api_success_with_audit_context(
            {
                "items": items,
                "pagination": result.pagination,
            },
            audit_context=audit_context,
        )

    def concept_card_reviews_api(card_uid):
        audit_context = core.get_route_audit_context()
        user, error_response = core.require_current_user({"teacher", "admin"})
        if error_response:
            return core.attach_request_id_to_response(error_response, audit_context)
        audit_context = core.get_route_audit_context(user)
        try:
            card = concept_card_service.get_concept_card(db.session, models.ConceptAlignmentCard, card_uid)
        except concept_card_service.ConceptCardError as exc:
            return concept_card_review_error_response(exc, audit_context)
        if user.role != "admin":
            can_review, _, reason = course_review_policy_service.can_reviewer_review_card(
                db.session,
                models.CourseReviewPermission,
                card,
                user,
            )
            if not can_review:
                return core.api_error_with_audit_context(
                    "FORBIDDEN",
                    "Reviewer is not permitted to view reviews for this course.",
                    403,
                    audit_context,
                    {"audit_error_code": reason or "course_review_permission_denied"},
                )
        result = concept_card_review_service.get_card_review_history(
            db.session,
            models.ConceptCardReviewRecord,
            card_uid,
            request.args.to_dict(),
        )
        return core.api_success_with_audit_context(
            {
                "items": [concept_card_review_service.serialize_review_record(item) for item in result.items],
                "pagination": result.pagination,
            },
            audit_context=audit_context,
        )

    def concept_card_review_action_api(card_uid):
        audit_context = core.get_route_audit_context()
        user, error_response = core.require_current_user({"teacher", "admin"})
        if error_response:
            return core.attach_request_id_to_response(error_response, audit_context)
        audit_context = core.get_route_audit_context(user)
        raw_data = request.get_json(silent=True) or {}
        data = dict(raw_data) if isinstance(raw_data, dict) else {}
        action = str(data.get("action") or "").strip()
        try:
            card, review_record = concept_card_review_service.dispatch_review_action(
                db.session,
                models.ConceptAlignmentCard,
                models.ConceptCardReviewRecord,
                card_uid,
                action,
                user,
                data,
                audit_model=core.audit_record_model,
                audit_context=audit_context,
                policy_model=models.CourseReviewPolicy,
                permission_model=models.CourseReviewPermission,
                now_fn=core.current_time_text,
                commit=True,
            )
        except (concept_card_service.ConceptCardError, concept_card_review_service.ConceptCardReviewError, ValueError) as exc:
            db.session.rollback()
            return concept_card_review_error_response(exc, audit_context)
        return core.api_success_with_audit_context(
            {
                "card": concept_card_service.serialize_concept_card(card),
                "review": concept_card_review_service.serialize_review_record(review_record),
            },
            "Concept card review recorded.",
            audit_context,
        )

    def concept_card_assign_reviewer_api(card_uid):
        audit_context = core.get_route_audit_context()
        user, error_response = core.require_current_user({"teacher", "admin"})
        if error_response:
            return core.attach_request_id_to_response(error_response, audit_context)
        audit_context = core.get_route_audit_context(user)
        raw_data = request.get_json(silent=True) or {}
        data = dict(raw_data) if isinstance(raw_data, dict) else {}
        try:
            card, review_record, assignment = concept_card_review_service.assign_card_reviewer(
                db.session,
                models.ConceptAlignmentCard,
                models.ConceptCardReviewRecord,
                models.ConceptCardReviewAssignment,
                card_uid,
                user,
                data,
                audit_model=core.audit_record_model,
                audit_context=audit_context,
                policy_model=models.CourseReviewPolicy,
                permission_model=models.CourseReviewPermission,
                now_fn=core.current_time_text,
                commit=True,
            )
        except (concept_card_service.ConceptCardError, concept_card_review_service.ConceptCardReviewError, ValueError) as exc:
            db.session.rollback()
            return concept_card_review_error_response(exc, audit_context)
        return core.api_success_with_audit_context(
            {
                "card": concept_card_service.serialize_concept_card(card),
                "review": concept_card_review_service.serialize_review_record(review_record),
                "assignment": concept_card_review_service.serialize_assignment(assignment),
            },
            "Concept card reviewer assigned.",
            audit_context,
        )

    app.add_url_rule(
        "/api/concept-cards/review-queue",
        view_func=concept_card_review_queue_api,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/concept-cards/<card_uid>/reviews",
        view_func=concept_card_reviews_api,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/concept-cards/<card_uid>/review",
        view_func=concept_card_review_action_api,
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/concept-cards/<card_uid>/assign-reviewer",
        view_func=concept_card_assign_reviewer_api,
        methods=["POST"],
    )
    registered.add(ROUTE_MARKER)


def _assert_no_duplicate_target_routes(app) -> None:
    for path, route in TARGET_ROUTES.items():
        method = route["method"]
        endpoint = route["endpoint"]
        for rule in app.url_map.iter_rules():
            if rule.rule == path and method in rule.methods:
                raise RuntimeError(
                    f"Cannot register {endpoint}: {method} {path} is already registered as {rule.endpoint}."
                )
