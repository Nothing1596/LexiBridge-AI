from datetime import datetime


def seed_chunks(app_module, chunks, course="Computer Science"):
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with app_module.app.app_context():
        document = app_module.KnowledgeDocument(
            course=course,
            title="Search Fixture",
            filename="fixture.docx",
            saved_filename="fixture.docx",
            file_type="docx",
            language="en",
            source_type="test",
            text_length=sum(len(content) for content in chunks),
            chunk_count=len(chunks),
            created_at=now_text,
        )
        app_module.db.session.add(document)
        app_module.db.session.flush()

        for index, content in enumerate(chunks, start=1):
            app_module.db.session.add(
                app_module.KnowledgeChunk(
                    document_id=document.id,
                    course=course,
                    title=document.title,
                    chunk_index=index,
                    content=content,
                    source_page="",
                    created_at=now_text,
                )
            )

        app_module.db.session.commit()


def search(client, query, **params):
    query_string = {"q": query}
    query_string.update(params)
    return client.get("/api/knowledge/search", query_string=query_string)


def result_contents(payload):
    return [item["chunk"]["content"] for item in payload["results"]]


def test_fourier_query_excludes_hash_table_weak_match(app_module, client):
    seed_chunks(
        app_module,
        [
            "The Fourier Transform maps a time-domain signal into a frequency-domain representation.",
            "A Hash Table stores key-value pairs. A hash function can transform keys into array indices.",
        ],
    )

    response = search(client, "Fourier Transform")

    assert response.status_code == 200
    payload = response.get_json()
    contents = result_contents(payload)
    assert payload["count"] == 1
    assert "Fourier Transform" in contents[0]
    assert all("Hash Table" not in content for content in contents)


def test_hash_table_query_excludes_fourier_chunk(app_module, client):
    seed_chunks(
        app_module,
        [
            "The Fourier Transform maps a time-domain signal into a frequency-domain representation.",
            "A Hash Table stores key-value pairs and uses a hash function for fast lookup.",
        ],
    )

    response = search(client, "Hash Table")

    assert response.status_code == 200
    payload = response.get_json()
    contents = result_contents(payload)
    assert payload["count"] == 1
    assert "Hash Table" in contents[0]
    assert all("Fourier Transform" not in content for content in contents)


def test_no_relevant_evidence_returns_empty_results(app_module, client):
    seed_chunks(
        app_module,
        [
            "A stack follows last-in first-out order.",
            "A queue follows first-in first-out order.",
        ],
    )

    response = search(client, "Eigenvalue Decomposition")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 0
    assert payload["results"] == []


def test_search_limit_is_applied(app_module, client):
    seed_chunks(
        app_module,
        [
            "Fourier Transform evidence one.",
            "Fourier Transform evidence two.",
            "Fourier Transform evidence three.",
        ],
    )

    response = search(client, "Fourier Transform", limit=1)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    assert len(payload["results"]) == 1


def test_empty_query_returns_clear_error(client):
    response = client.get("/api/knowledge/search", query_string={"q": "  "})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "q 不能为空" in payload["message"]


def test_search_response_keeps_legacy_fields(app_module, client):
    seed_chunks(app_module, ["Fourier Transform converts signals into frequency components."])

    response = search(client, "Fourier Transform")

    assert response.status_code == 200
    payload = response.get_json()
    result = payload["results"][0]
    assert isinstance(result["score"], int)
    assert isinstance(result["chunk"], dict)
    assert isinstance(result["evidence_score"], float)
    assert 0 <= result["evidence_score"] <= 1
    assert result["matched_terms"] == ["fourier", "transform"]
    assert result["score_breakdown"]["phrase_match"] is True
    assert 0 <= result["score_breakdown"]["lexical"] <= 1


def test_single_generic_token_query_is_below_evidence_gate(app_module, client):
    seed_chunks(
        app_module,
        [
            "The Fourier Transform maps a time-domain signal into a frequency-domain representation.",
            "A Hash Table can transform keys into array indices.",
        ],
    )

    response = search(client, "transform")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 0
    assert payload["results"] == []


def test_chinese_query_allows_small_function_word_gap(app_module, client):
    seed_chunks(app_module, ["傅里叶的变换方法可以用于信号分析。"])

    response = search(client, "傅里叶变换")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    assert payload["results"][0]["evidence_score"] >= 0.65
