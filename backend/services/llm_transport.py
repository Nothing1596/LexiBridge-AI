"""Transport abstractions for guarded alignment LLM providers.

No transport in this module performs network I/O by default. HTTPTransport is a
placeholder and returns a controlled provider_disabled error until a later task
explicitly enables and tests real external calls.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMTransportResult:
    status: str
    raw_output: str = ""
    error_code: str = ""
    error_message: str = ""
    latency_ms: int = 0
    retry_count: int = 0


class BaseLLMTransport:
    """Base transport interface for alignment providers."""

    def generate(self, prompt: str, config: dict[str, Any], request_options: dict[str, Any] | None = None) -> LLMTransportResult:
        raise NotImplementedError


class DisabledLLMTransport(BaseLLMTransport):
    def generate(self, prompt: str, config: dict[str, Any], request_options: dict[str, Any] | None = None) -> LLMTransportResult:
        del prompt, request_options
        return LLMTransportResult(
            status="error",
            error_code="provider_disabled",
            error_message=f"External LLM provider is disabled: {config.get('provider_name', '')}",
            retry_count=0,
        )


class FakeLLMTransport(BaseLLMTransport):
    def generate(self, prompt: str, config: dict[str, Any], request_options: dict[str, Any] | None = None) -> LLMTransportResult:
        del prompt, config
        options = request_options or {}
        response_type = str(options.get("fake_response_type") or "valid").strip()
        return LLMTransportResult(status="success", raw_output=build_fixture_response(response_type), retry_count=0)


class ReplayLLMTransport(BaseLLMTransport):
    def generate(self, prompt: str, config: dict[str, Any], request_options: dict[str, Any] | None = None) -> LLMTransportResult:
        del prompt, config
        options = request_options or {}
        response_type = str(options.get("replay_response_type") or "valid").strip()
        return LLMTransportResult(status="success", raw_output=build_fixture_response(response_type), retry_count=0)


class HTTPTransport(BaseLLMTransport):
    def generate(self, prompt: str, config: dict[str, Any], request_options: dict[str, Any] | None = None) -> LLMTransportResult:
        del prompt, config, request_options
        return LLMTransportResult(
            status="error",
            error_code="provider_disabled",
            error_message="HTTP transport is not enabled in this task.",
            retry_count=0,
        )


def build_fixture_response(response_type: str = "valid") -> str:
    if response_type == "non_json":
        return "non-json replay response"
    if response_type == "output_too_long":
        return "x" * 10000
    response = {
        "alignment_decision": "likely_aligned",
        "alignment_confidence": 0.69,
        "recommendation": "ready_for_human_review",
        "risk_labels": [
            "bilingual_alignment_not_verified",
            "candidate_not_alignment_verified",
        ],
        "evidence_assessment": {
            "english_evidence_supported": True,
            "chinese_evidence_supported": True,
            "cross_language_support": "moderate",
            "evidence_limitations": [
                "replay_fixture_only",
                "not_a_production_llm_judgment",
            ],
        },
        "term_assessment": {
            "english_term_ok": True,
            "chinese_term_ok": True,
            "candidate_ambiguity": "none",
            "notes": "Replay fixture response.",
        },
        "course_context_assessment": {
            "course_match": True,
            "chapter_match": True,
            "notes": "Replay fixture context.",
        },
        "explanation": "Replay fixture for guarded external provider parsing. This is not production output.",
        "limitations": [
            "replay_fixture_only",
            "no_external_model_called",
            "requires_human_review",
        ],
        "auto_approve": True,
    }
    if response_type == "missing_fields":
        response.pop("recommendation", None)
    elif response_type == "confidence_out_of_range":
        response["alignment_confidence"] = 1.5
    elif response_type == "insufficient_evidence":
        response.update({
            "alignment_decision": "insufficient_evidence",
            "alignment_confidence": 0.2,
            "recommendation": "insufficient_evidence",
            "risk_labels": [
                "bilingual_alignment_not_verified",
                "candidate_not_alignment_verified",
                "no_english_evidence",
                "no_chinese_evidence",
            ],
        })
        response["evidence_assessment"]["english_evidence_supported"] = False
        response["evidence_assessment"]["chinese_evidence_supported"] = False
        response["evidence_assessment"]["cross_language_support"] = "missing"
    elif response_type == "ambiguous_candidate":
        response.update({
            "alignment_decision": "uncertain",
            "alignment_confidence": 0.41,
            "recommendation": "candidate_ambiguous",
            "risk_labels": [
                "bilingual_alignment_not_verified",
                "candidate_not_alignment_verified",
                "ambiguous_chinese_candidates",
            ],
        })
        response["term_assessment"]["candidate_ambiguity"] = "high"
    return json.dumps(response, ensure_ascii=False, sort_keys=True)
