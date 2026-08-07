import pytest

from services import student_concept_queries as queries


def test_selection_is_verified_against_server_chunk_and_context_is_rebuilt():
    chunk = {
        "chunk_uid": "chunk-en-1",
        "content": "The electric potential at a point is potential energy per unit charge.",
        "page_number": 4,
        "parse_block_uid": "block-en-1",
        "section_title": "Electric potential",
    }
    start = chunk["content"].index("electric potential")
    selection = queries.validate_selection(
        chunk,
        selected_text="electric potential",
        selection_start=start,
        selection_end=start + len("electric potential"),
    )
    assert selection.selected_text == "electric potential"
    assert "potential energy per unit charge" in selection.bounded_context
    assert selection.provenance["chunk_uid"] == "chunk-en-1"
    assert selection.provenance["block_uid"] == "block-en-1"


@pytest.mark.parametrize(
    ("text", "start", "end", "reason"),
    [
        ("", 0, 0, "STUDENT_CONCEPT_SELECTION_EMPTY"),
        ("...", 0, 3, "STUDENT_CONCEPT_SELECTION_NOT_CONCEPT"),
        ("123", 0, 3, "STUDENT_CONCEPT_SELECTION_NOT_CONCEPT"),
        ("potential", -1, 8, "STUDENT_CONCEPT_SELECTION_SPAN_INVALID"),
        ("wrong", 4, 9, "STUDENT_CONCEPT_SELECTION_TEXT_MISMATCH"),
    ],
)
def test_invalid_selection_fails_closed(text, start, end, reason):
    with pytest.raises(queries.StudentConceptQueryError) as exc:
        queries.validate_selection(
            {"chunk_uid": "c1", "content": "electric potential"},
            selected_text=text,
            selection_start=start,
            selection_end=end,
        )
    assert exc.value.reason_code == reason


def test_query_fingerprint_is_stable_and_source_version_sensitive():
    base = dict(
        student_uid="student-1",
        workspace_scope="PERSONAL",
        workspace_uid="personal:student-1",
        source_uid="source-1",
        source_version="1",
        chunk_uid="chunk-1",
        selection_start=0,
        selection_end=18,
        selected_text="electric potential",
        alignment_policy_version="governed-bilingual-evidence-qualification@1.1.0",
    )
    assert queries.build_query_fingerprint(**base) == queries.build_query_fingerprint(**base)
    assert queries.build_query_fingerprint(**base) != queries.build_query_fingerprint(
        **{**base, "source_version": "2"}
    )
