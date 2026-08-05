"""Bounded English-to-Chinese semantic retrieval using the qualified backend."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable

from services.local_multilingual_embedding import (
    BACKEND_UNAVAILABLE,
    MODEL_ID,
    MODEL_REVISION,
    cache_key,
)

MAX_CONTEXT_CHARS = 800
MAX_QUERY_CHARS = 1100
MAX_TOP_K = 10
MAX_PASSAGE_CANDIDATES = 200


class CrossLanguageRetrievalError(RuntimeError):
    pass


@dataclass(frozen=True)
class CrossLanguageRetrievalQuery:
    english_candidate_uid: str
    canonical_english_term: str
    normalized_english_term: str
    english_context: str
    discipline: str
    allowed_chinese_source_uids: tuple[str, ...]
    top_k: int = 5
    retrieval_budget: int = 100


@dataclass(frozen=True)
class SemanticPassage:
    source_uid: str
    chunk_uid: str
    content: str
    language: str
    source_status: str
    quality_status: str
    content_hash: str


@dataclass(frozen=True)
class CrossLanguageRetrievalResult:
    source_uid: str
    chunk_uid: str
    score: float
    rank: int
    retrieval_method: str
    backend_id: str
    model_id: str
    model_revision: str
    query_hash: str
    language: str
    source_status: str
    quality_status: str
    snippet: str
    provenance: dict[str, str]


def build_query_text(query: CrossLanguageRetrievalQuery) -> str:
    context = str(query.english_context or "").strip()[:MAX_CONTEXT_CHARS]
    text = (
        f"term:\n{query.canonical_english_term.strip()}\n\n"
        f"discipline:\n{query.discipline.strip()}\n\ncontext:\n{context}"
    )
    return text[:MAX_QUERY_CHARS]


def _vector(
    backend: Any, text: str, representation_type: str, cache: dict[str, list[float]]
) -> list[float]:
    key = f"{representation_type}:{cache_key(MODEL_ID, MODEL_REVISION, text)}"
    if key not in cache:
        encoded = (
            backend.embed_queries([text])
            if representation_type == "query"
            else backend.embed_passages([text])
        )
        if not encoded or not encoded[0]:
            raise CrossLanguageRetrievalError(BACKEND_UNAVAILABLE)
        cache[key] = list(encoded[0])
    return cache[key]


def rank_chinese_passages(
    query: CrossLanguageRetrievalQuery,
    passages: Iterable[SemanticPassage],
    backend: Any,
    *,
    representation_cache: dict[str, list[float]] | None = None,
) -> list[CrossLanguageRetrievalResult]:
    readiness = backend.readiness()
    if not readiness.ready:
        raise CrossLanguageRetrievalError(BACKEND_UNAVAILABLE)
    allowed = set(query.allowed_chinese_source_uids)
    bounded = [
        p for p in passages
        if p.language == "zh"
        and p.source_status == "active"
        and p.quality_status not in {"blocked", "rejected", "withdrawn", "ocr_required"}
        and (not allowed or p.source_uid in allowed)
        and p.content.strip()
    ]
    budget = max(1, min(int(query.retrieval_budget or 1), MAX_PASSAGE_CANDIDATES))
    bounded = sorted(bounded, key=lambda p: (p.source_uid, p.chunk_uid))[:budget]
    if not bounded:
        return []
    cache = representation_cache if representation_cache is not None else {}
    query_text = build_query_text(query)
    query_vector = _vector(backend, query_text, "query", cache)
    scored = []
    for passage in bounded:
        vector = _vector(backend, passage.content, "passage", cache)
        score = round(sum(a * b for a, b in zip(query_vector, vector)), 8)
        scored.append((score, passage))
    scored.sort(key=lambda item: (-item[0], item[1].source_uid, item[1].chunk_uid))
    top_k = max(1, min(int(query.top_k or 1), MAX_TOP_K))
    query_hash = hashlib.sha256(query_text.encode()).hexdigest()
    results = []
    for rank, (score, passage) in enumerate(scored[:top_k], 1):
        results.append(CrossLanguageRetrievalResult(
            source_uid=passage.source_uid, chunk_uid=passage.chunk_uid,
            score=score, rank=rank, retrieval_method="multilingual_e5_cosine",
            backend_id=backend.backend_id, model_id=backend.model_id,
            model_revision=backend.model_revision, query_hash=query_hash,
            language=passage.language, source_status=passage.source_status,
            quality_status=passage.quality_status,
            snippet=passage.content[:180],
            provenance={"source_uid": passage.source_uid, "chunk_uid": passage.chunk_uid,
                        "content_hash": passage.content_hash},
        ))
    return results
