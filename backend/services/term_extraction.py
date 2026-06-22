import re

from .text_quality import (
    candidate_quality_flags,
    has_blocking_placeholder,
    is_valid_term_candidate,
    looks_like_ocr_merged_article,
    normalize_space,
)


TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-/][A-Za-z0-9]+)*")
MAX_TERM_WORDS = 4


def _token_spans(text):
    return [(match.group(0), match.start(), match.end()) for match in TOKEN_PATTERN.finditer(text or "")]


def _normalize_key(term):
    return normalize_space(term).lower()


def _extract_context(text, start, end, window=140):
    context_start = max(0, start - window)
    context_end = min(len(text), end + window)
    return normalize_space(text[context_start:context_end])


def _is_title_case_phrase(term):
    words = term.split()

    if len(words) < 2:
        return False

    return all(word[:1].isupper() for word in words if word)


def _score_candidate(term, count, context):
    words = term.split()
    score = 45

    if count >= 2:
        score += min(25, 8 + count * 3)

    if len(words) >= 2:
        score += 12

    if len(words) >= 3:
        score += 4

    if term.isupper() and len(term) >= 3:
        score += 10

    if _is_title_case_phrase(term):
        score += 14

    if "-" in term:
        score += 5

    morphology_suffixes = (
        "tion", "sion", "ment", "ness", "ity", "ics",
        "ism", "ance", "ence", "ing", "al", "ive", "ous",
    )
    if any(word.lower().endswith(morphology_suffixes) for word in words):
        score += 6

    definition_clues = (
        "is called", "is defined as", "means", "refers to",
        "denoted by", "known as", "consists of",
    )
    lower_context = context.lower()
    if any(clue in lower_context for clue in definition_clues):
        score += 5

    return max(0, min(score, 95))


def _iter_candidate_phrases(text):
    tokens = _token_spans(text)

    for start_index in range(len(tokens)):
        for length in range(1, MAX_TERM_WORDS + 1):
            end_index = start_index + length

            if end_index > len(tokens):
                break

            phrase_tokens = tokens[start_index:end_index]
            if _has_sentence_boundary_between_tokens(text, phrase_tokens):
                break

            if _sentence_has_ocr_merged_artifact(text, phrase_tokens[0][1], phrase_tokens[-1][2]):
                continue

            if _sentence_has_blocking_placeholder(text, phrase_tokens[0][1], phrase_tokens[-1][2]):
                continue

            phrase = " ".join(token for token, _, _ in phrase_tokens)
            yield phrase, phrase_tokens[0][1], phrase_tokens[-1][2]


def _has_sentence_boundary_between_tokens(text, phrase_tokens):
    for previous, current in zip(phrase_tokens, phrase_tokens[1:]):
        gap = text[previous[2]:current[1]]

        if re.search(r"[.!?;:\n\r]", gap):
            return True

    return False


def _sentence_has_ocr_merged_artifact(text, start, end):
    sentence = _sentence_for_span(text, start, end)

    return any(looks_like_ocr_merged_article(token) for token in TOKEN_PATTERN.findall(sentence))


def _sentence_has_blocking_placeholder(text, start, end):
    return has_blocking_placeholder(_sentence_for_span(text, start, end))


def _sentence_for_span(text, start, end):
    sentence_start = max(
        text.rfind(".", 0, start),
        text.rfind("!", 0, start),
        text.rfind("?", 0, start),
        text.rfind(";", 0, start),
        text.rfind("\n", 0, start),
        text.rfind("\r", 0, start),
    ) + 1
    following_boundaries = [
        index
        for index in (
            text.find(".", end),
            text.find("!", end),
            text.find("?", end),
            text.find(";", end),
            text.find("\n", end),
            text.find("\r", end),
        )
        if index != -1
    ]
    sentence_end = min(following_boundaries) if following_boundaries else len(text)
    return text[sentence_start:sentence_end]


def _is_acronym(term):
    return term.isupper() and 2 <= len(term) <= 10


def _has_morphology_signal(term):
    morphology_suffixes = (
        "tion", "sion", "ment", "ness", "ity", "ics",
        "ism", "ance", "ence", "ing", "al", "ive", "ous",
    )
    return any(word.lower().endswith(morphology_suffixes) for word in term.split())


def _has_termhood_signal(term, count):
    return (
        count >= 2
        or _is_title_case_phrase(term)
        or _is_acronym(term)
        or "-" in term
        or _has_morphology_signal(term)
    )


def extract_terms_from_text(text):
    """
    Extract deterministic English term candidates for the local MVP.

    The implementation intentionally stays dependency-free for PR-2. It uses
    noun-phrase-like surface cues, frequency, title-case/acronym signals, and
    text quality filters to avoid full sentences, verb phrases, OCR placeholders,
    and merged OCR artifacts such as "convertsa signal".
    """
    if not text or not text.strip():
        return []

    raw_counts = {}
    display_form = {}
    contexts = {}

    for term, start, end in _iter_candidate_phrases(text):
        term = normalize_space(term)

        if len(term) < 4 and not _is_acronym(term):
            continue

        if len(term) > 80:
            continue

        if len(term.split()) > MAX_TERM_WORDS:
            continue

        if not is_valid_term_candidate(term):
            continue

        key = _normalize_key(term)
        raw_counts[key] = raw_counts.get(key, 0) + 1

        if key not in display_form:
            display_form[key] = term

        if key not in contexts:
            contexts[key] = _extract_context(text, start, end)

    scored = []

    for key, count in raw_counts.items():
        term = display_form[key]
        words = term.split()
        context = contexts.get(key, "")

        if len(words) == 1 and term.islower() and count < 2:
            continue

        if len(words) == 1 and not term.isupper() and not term[:1].isupper() and count < 3:
            continue

        if not _has_termhood_signal(term, count):
            continue

        score = _score_candidate(term, count, context)

        if score < 55:
            continue

        flags = candidate_quality_flags(term)
        if flags:
            continue

        scored.append((score, count, len(words), len(term), term, context))

    scored.sort(key=lambda item: (item[0], item[1], item[2], item[3]), reverse=True)

    candidates = []
    seen = set()

    for score, count, _, _, term, context in scored:
        key = _normalize_key(term)

        if key in seen:
            continue

        seen.add(key)

        candidates.append({
            "english_term": term,
            "chinese_term": "待教师审核",
            "explanation": "待教师审核：系统仅完成候选术语抽取，尚未生成正式专业译名。",
            "context": context,
            "confidence": score,
            "status": "pending",
        })

    return candidates
