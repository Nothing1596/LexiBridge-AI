from io import BytesIO


def test_knowledge_upload_rejects_oversized_file(app_module, client):
    app_module.app.config["MAX_CONTENT_LENGTH"] = 1

    response = client.post(
        "/api/knowledge/upload",
        data={
            "file": (BytesIO(b"x" * 128), "too-large.pdf"),
            "course": "Signals",
            "title": "Too Large",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    payload = response.get_json()
    assert payload["status"] == "error"
    assert payload["error_code"] == "FILE_TOO_LARGE"
