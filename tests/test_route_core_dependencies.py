import ast
import inspect
from dataclasses import FrozenInstanceError, fields, is_dataclass
from pathlib import Path

import pytest
from flask import Flask

from routes.shared import RouteCoreDependencies
from routes.student_concept_cards import (
    StudentConceptCardModels,
    register_student_concept_card_routes,
)
from routes.teacher_learning_analytics import (
    TeacherLearningAnalyticsModels,
    register_teacher_learning_analytics_routes,
)
from routes.concept_card_review import (
    ConceptCardReviewModels,
    register_concept_card_review_routes,
)
from routes.concept_card_feedback import (
    ConceptCardFeedbackModels,
    register_concept_card_feedback_routes,
)


ROOT = Path(__file__).resolve().parents[1]
SHARED_MODULE = ROOT / "backend" / "routes" / "shared.py"
TEACHER_MODULE = ROOT / "backend" / "routes" / "teacher_learning_analytics.py"
STUDENT_MODULE = ROOT / "backend" / "routes" / "student_concept_cards.py"
CONCEPT_REVIEW_MODULE = ROOT / "backend" / "routes" / "concept_card_review.py"
CONCEPT_FEEDBACK_MODULE = ROOT / "backend" / "routes" / "concept_card_feedback.py"

EXPECTED_CORE_FIELDS = {
    "db",
    "audit_record_model",
    "audit_record_service",
    "current_time_text",
    "require_current_user",
    "get_route_audit_context",
    "attach_request_id_to_response",
    "api_success_with_audit_context",
    "api_error_with_audit_context",
}


class DummyDb:
    session = object()


def _imports_for(path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return imports


def _dummy_core():
    return RouteCoreDependencies(
        db=DummyDb(),
        audit_record_model=object,
        audit_record_service=object(),
        current_time_text=lambda: "",
        require_current_user=lambda roles: (None, None),
        get_route_audit_context=lambda user=None: {"request_id": "dummy"},
        attach_request_id_to_response=lambda response, audit_context: response,
        api_success_with_audit_context=lambda data=None, message="", audit_context=None: data,
        api_error_with_audit_context=lambda *args, **kwargs: ({"status": "error"}, 400),
    )


def test_route_core_dependencies_shape_and_immutability():
    assert is_dataclass(RouteCoreDependencies)
    assert getattr(RouteCoreDependencies, "__dataclass_params__").frozen is True
    assert {field.name for field in fields(RouteCoreDependencies)} == EXPECTED_CORE_FIELDS
    assert len(fields(RouteCoreDependencies)) == 9

    core = _dummy_core()
    assert not hasattr(core, "app")
    assert not hasattr(core, "request")
    assert not hasattr(core, "user")
    assert not hasattr(core, "actor")
    assert not hasattr(core, "student_concept_cards_service")
    assert not hasattr(core, "teacher_learning_analytics_service")
    assert not hasattr(core, "concept_card_review_service")
    assert not hasattr(core, "concept_card_feedback_service")
    assert not hasattr(core, "course_review_policy_service")
    assert not hasattr(core, "student_feedback_service")
    with pytest.raises(FrozenInstanceError):
        core.db = object()


def test_shared_route_module_import_boundary():
    imports = set(_imports_for(SHARED_MODULE))
    assert "backend.app" not in imports
    assert "app" not in imports
    assert not any(name.startswith("services") for name in imports)
    assert not any("student" in name or "teacher" in name or "provider" in name for name in imports)


def test_extracted_route_modules_accept_core_and_do_not_import_backend_app():
    for path in [TEACHER_MODULE, STUDENT_MODULE, CONCEPT_REVIEW_MODULE, CONCEPT_FEEDBACK_MODULE]:
        imports = set(_imports_for(path))
        assert "backend.app" not in imports
        assert "app" not in imports

    teacher_sig = inspect.signature(register_teacher_learning_analytics_routes)
    student_sig = inspect.signature(register_student_concept_card_routes)
    review_sig = inspect.signature(register_concept_card_review_routes)
    feedback_sig = inspect.signature(register_concept_card_feedback_routes)
    assert "core" in teacher_sig.parameters
    assert "core" in student_sig.parameters
    assert "core" in review_sig.parameters
    assert "core" in feedback_sig.parameters
    for name in {
        "db",
        "audit_model",
        "audit_record_service",
        "current_time_text",
        "require_current_user",
        "get_route_audit_context",
        "attach_request_id_to_response",
        "api_success_with_audit_context",
        "api_error_with_audit_context",
    }:
        assert name not in teacher_sig.parameters
        assert name not in student_sig.parameters
        assert name not in review_sig.parameters
        assert name not in feedback_sig.parameters
    for service_name in {
        "concept_card_review_service",
        "concept_card_feedback_service",
        "course_review_policy_service",
        "student_feedback_service",
    }:
        assert service_name not in review_sig.parameters
        assert service_name not in feedback_sig.parameters


def test_route_core_can_be_reused_by_extracted_modules_without_duplicate_endpoints():
    app = Flask("route-core-reuse-test")
    core = _dummy_core()
    register_teacher_learning_analytics_routes(
        app,
        core=core,
        models=TeacherLearningAnalyticsModels(
            ConceptAlignmentCard=object,
            StudentConceptCardState=object,
            Feedback=object,
            StudentCourseMembership=object,
            CourseReviewPermission=object,
            CourseStudentVisibilityPolicy=object,
        ),
    )
    register_student_concept_card_routes(
        app,
        core=core,
        models=StudentConceptCardModels(
            ConceptAlignmentCard=object,
            StudentConceptCardState=object,
            Feedback=object,
            StudentCourseMembership=object,
            CourseStudentVisibilityPolicy=object,
        ),
        student_visible_course_names=lambda user: [],
        student_course_access_service=object(),
        record_student_course_access_audit=lambda *args, **kwargs: None,
    )
    register_concept_card_review_routes(
        app,
        core=core,
        models=ConceptCardReviewModels(
            ConceptAlignmentCard=object,
            ConceptCardReviewRecord=object,
            ConceptCardReviewAssignment=object,
            CourseReviewPolicy=object,
            CourseReviewPermission=object,
            AlignmentVerificationRun=object,
        ),
    )
    register_concept_card_feedback_routes(
        app,
        core=core,
        models=ConceptCardFeedbackModels(
            Feedback=object,
            ConceptAlignmentCard=object,
            ConceptCardReviewRecord=object,
            ConceptCardFeedbackTriageRecord=object,
            CourseReviewPermission=object,
            CourseReviewPolicy=object,
        ),
    )
    paths = [
        rule.rule
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith("/api/teacher/learning-analytics")
        or rule.rule.startswith("/api/student/concept-cards")
        or rule.rule.startswith("/api/concept-cards")
    ]
    assert len(paths) == len(set(paths))
    assert "/api/teacher/learning-analytics" in paths
    assert "/api/student/concept-cards" in paths
    assert "/api/concept-cards/review-queue" in paths
    assert "/api/concept-cards/student-feedback-queue" in paths
