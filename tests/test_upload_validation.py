from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from werkzeug.datastructures import FileStorage


def _file_storage(content, filename):
    return FileStorage(stream=BytesIO(content), filename=filename)


def _ooxml_archive(required_member):
    buffer = BytesIO()

    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr(required_member, "<xml></xml>")

    return buffer.getvalue()


def test_upload_content_validation_accepts_supported_signatures(app_module):
    assert app_module.is_allowed_upload_content(_file_storage(b"%PDF-1.7\n", "notes.pdf"))
    assert app_module.is_allowed_upload_content(
        _file_storage(_ooxml_archive("word/document.xml"), "notes.docx")
    )
    assert app_module.is_allowed_upload_content(
        _file_storage(_ooxml_archive("ppt/presentation.xml"), "slides.pptx")
    )


def test_upload_content_validation_rejects_mismatched_content(app_module):
    assert not app_module.is_allowed_upload_content(_file_storage(b"not a pdf", "notes.pdf"))
    assert not app_module.is_allowed_upload_content(
        _file_storage(_ooxml_archive("ppt/presentation.xml"), "notes.docx")
    )


def test_knowledge_upload_rejects_spoofed_pdf_before_saving(app_module, client):
    response = client.post(
        "/api/knowledge/upload",
        data={
            "file": (BytesIO(b"not a pdf"), "spoofed.pdf"),
            "course": "Signals",
            "title": "Spoofed",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert payload["error_code"] == "INVALID_FILE_CONTENT"

    with app_module.app.app_context():
        assert app_module.KnowledgeDocument.query.count() == 0
        assert app_module.KnowledgeChunk.query.count() == 0

    upload_dir = Path(app_module.UPLOAD_FOLDER)
    assert not list(upload_dir.glob("*spoofed*"))
