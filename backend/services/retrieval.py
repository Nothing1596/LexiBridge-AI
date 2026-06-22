import re


LATIN_TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
CHINESE_SEQUENCE_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
ENGLISH_TOKEN_PATTERN = re.compile(r"^[a-z0-9]+$")
MIN_EVIDENCE_SCORE = 0.65

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def normalize_text(value):
    if not value:
        return ""

    return re.sub(r"\s+", " ", value.lower()).strip()


def tokenize_query(value):
    tokens = []
    seen = set()
    normalized = normalize_text(value)

    for token in LATIN_TOKEN_PATTERN.findall(normalized):
        if token in STOPWORDS:
            continue

        if token not in seen:
            seen.add(token)
            tokens.append(token)

    for sequence in CHINESE_SEQUENCE_PATTERN.findall(normalized):
        if len(sequence) == 1:
            chinese_tokens = [sequence]
        elif len(sequence) == 2:
            chinese_tokens = [sequence]
        else:
            chinese_tokens = [
                sequence[index:index + 2]
                for index in range(len(sequence) - 1)
            ]

        for token in chinese_tokens:
            if token not in seen:
                seen.add(token)
                tokens.append(token)

    return tokens


def _content_token_set(content):
    return set(LATIN_TOKEN_PATTERN.findall(normalize_text(content)))


def _token_matches_content(token, content_normalized, content_tokens):
    if ENGLISH_TOKEN_PATTERN.match(token):
        return token in content_tokens

    return token in content_normalized


def _is_specific_single_token_query(tokens, query):
    if len(tokens) != 1:
        return False

    token = tokens[0]
    raw_query = (query or "").strip()

    return token.isupper() or raw_query.isupper() or bool(CHINESE_SEQUENCE_PATTERN.fullmatch(raw_query))


def score_knowledge_evidence(content, query):
    """
    Deterministic lexical evidence scoring for the v0.1 knowledge search.

    Multi-token queries must match most of their meaningful tokens unless the
    exact phrase appears. This avoids returning weakly related chunks that only
    share one generic word with the query.
    """
    content_normalized = normalize_text(content)
    query_normalized = normalize_text(query)

    result = {
        "score": 0,
        "evidence_score": 0,
        "matched_terms": [],
        "score_breakdown": {
            "term_exact": 0,
            "lexical": 0,
            "semantic": None,
            "scope": None,
            "discipline": None,
            "source": None,
            "scoring_version": "lexical_v1",
            "phrase_match": False,
            "token_coverage": 0,
            "matched_token_count": 0,
            "query_token_count": 0,
        },
    }

    if not content_normalized or not query_normalized:
        return result

    query_tokens = tokenize_query(query_normalized)

    if not query_tokens:
        return result

    content_tokens = _content_token_set(content_normalized)
    matched_terms = [
        token
        for token in query_tokens
        if _token_matches_content(token, content_normalized, content_tokens)
    ]
    phrase_match = query_normalized in content_normalized
    token_coverage = len(matched_terms) / len(query_tokens)

    if not phrase_match:
        required_matches = max(1, round(len(query_tokens) * 0.65))

        if len(matched_terms) < required_matches:
            return result

    evidence_score = token_coverage

    if phrase_match:
        evidence_score = max(evidence_score, 1.0)

    if len(query_tokens) == 1 and not _is_specific_single_token_query(query_tokens, query):
        evidence_score = min(evidence_score, 0.6)

    evidence_score = round(min(1.0, evidence_score), 3)

    if evidence_score < MIN_EVIDENCE_SCORE:
        return result

    score = int(round(evidence_score * 100))

    result["score"] = score
    result["evidence_score"] = evidence_score
    result["matched_terms"] = matched_terms
    result["score_breakdown"] = {
        "term_exact": 1.0 if phrase_match else 0.0,
        "lexical": round(token_coverage, 3),
        "semantic": None,
        "scope": None,
        "discipline": None,
        "source": None,
        "scoring_version": "lexical_v1",
        "phrase_match": phrase_match,
        "token_coverage": round(token_coverage, 3),
        "matched_token_count": len(matched_terms),
        "query_token_count": len(query_tokens),
    }

    return result
