from services.term_extraction import extract_terms_from_text


def terms_from(text):
    return [item["english_term"] for item in extract_terms_from_text(text)]


def test_extracts_fourier_transform_from_definition_text():
    text = (
        "The Fourier Transform converts a signal from the time domain to the "
        "frequency domain. Fourier Transform is used in signal processing."
    )

    terms = terms_from(text)

    assert "Fourier Transform" in terms


def test_ocr_required_placeholder_does_not_generate_terms():
    text = "OCR_REQUIRED OCR_REQUIRED This scanned page has no embedded text."

    assert extract_terms_from_text(text) == []


def test_placeholder_words_do_not_discard_valid_domain_terms():
    text = (
        "Null Pointer is a common programming concept. "
        "Undefined Behavior is a C language concept. "
        "Na Transport is discussed in chemistry."
    )

    terms = terms_from(text)

    assert "Null Pointer" in terms
    assert "Undefined Behavior" in terms
    assert "Na Transport" in terms


def test_ocr_merged_convertsa_signal_is_filtered():
    text = (
        "The parser produced convertsa signal after OCR. "
        "convertsa signal appears again as noisy extracted text."
    )

    assert extract_terms_from_text(text) == []


def test_sentence_fragments_with_verbs_are_filtered():
    text = (
        "The algorithm converts a signal into frequency components. "
        "Fourier Transform converts signals into frequency components."
    )

    terms = [term.lower() for term in terms_from(text)]

    assert "algorithm converts" not in terms
    assert "fourier transform converts" not in terms


def test_terms_with_search_sort_and_map_are_not_treated_as_verbs():
    text = (
        "Binary Search is a classic algorithm. "
        "Binary Search runs in log n time. "
        "Merge Sort divides the list. "
        "Hash Map stores key value pairs."
    )

    terms = terms_from(text)
    lower_terms = [term.lower() for term in terms]

    assert "Binary Search" in terms
    assert "Merge Sort" in terms
    assert "Hash Map" in terms
    assert "classic algorithm" not in lower_terms
    assert "runs in log" not in lower_terms


def test_candidates_do_not_cross_sentence_boundaries():
    text = (
        "The Fourier Transform maps signals to the frequency domain. "
        "Fourier Transform is a linear transform."
    )

    terms = [term.lower() for term in terms_from(text)]

    assert "frequency domain fourier transform" not in terms


def test_lowercase_ngram_fragments_are_suppressed():
    text = (
        "Insertion sort builds the final sorted array one item at a time. "
        "It is much less efficient on large lists than Merge Sort."
    )

    terms = [term.lower() for term in terms_from(text)]

    assert "builds the final" not in terms
    assert "much less efficient" not in terms
    assert "array one item" not in terms
    assert "merge sort" in terms


def test_short_acronyms_are_allowed():
    text = "SQL is used with API integrations. FFT is common in signal processing."

    terms = terms_from(text)

    assert "SQL" in terms
    assert "API" in terms
    assert "FFT" in terms


def test_app_wrapper_uses_term_extraction_service(app_module):
    text = "The Fourier Transform converts a signal into frequency components."

    terms = [item["english_term"] for item in app_module.extract_terms_from_text(text)]

    assert "Fourier Transform" in terms
