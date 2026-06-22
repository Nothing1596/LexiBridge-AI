import json
import os
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from services import layout as layout_service
from services.layout import layout_blocks_to_text, parse_pdf_layout


def _write_pdf(path, draw):
    pdf = canvas.Canvas(str(path), pagesize=letter)
    draw(pdf)
    pdf.save()
    return path


def _draw_line(pdf, x, y, text, size=11, font="Helvetica"):
    pdf.setFont(font, size)
    pdf.drawString(x, y, text)


def test_rule_based_layout_excludes_header_footer_from_text(tmp_path):
    pdf_path = _write_pdf(
        tmp_path / "header-footer.pdf",
        lambda pdf: (
            _draw_line(pdf, 72, 766, "Course Notes", size=9),
            _draw_line(pdf, 72, 710, "Fourier Transform", size=18, font="Helvetica-Bold"),
            _draw_line(pdf, 72, 680, "Maps signals into frequency components.", size=11),
            _draw_line(pdf, 280, 28, "Footer Marker 1", size=9),
            pdf.showPage(),
            _draw_line(pdf, 72, 766, "Course Notes", size=9),
            _draw_line(pdf, 72, 710, "Hash Table", size=18, font="Helvetica-Bold"),
            _draw_line(pdf, 72, 680, "Stores key value pairs for fast lookup.", size=11),
            _draw_line(pdf, 280, 28, "Footer Marker 2", size=9),
        ),
    )

    result = parse_pdf_layout(pdf_path)
    text = layout_blocks_to_text(result.blocks)

    assert result.provider == "rule_based"
    assert result.needs_ocr_engine is False
    assert "Fourier Transform" in text
    assert "Hash Table" in text
    assert "Course Notes" not in text
    assert "Footer Marker 1" not in text
    assert "Footer Marker 2" not in text


def test_rule_based_layout_reads_left_column_before_right_column(tmp_path):
    pdf_path = _write_pdf(
        tmp_path / "two-column.pdf",
        lambda pdf: (
            _draw_line(pdf, 72, 720, "Left column first.", size=11),
            _draw_line(pdf, 72, 700, "Left column second.", size=11),
            _draw_line(pdf, 330, 720, "Right column first.", size=11),
            _draw_line(pdf, 330, 700, "Right column second.", size=11),
        ),
    )

    text = layout_blocks_to_text(parse_pdf_layout(pdf_path).blocks)

    assert text.index("Left column first") < text.index("Right column first")
    assert text.index("Left column second") < text.index("Right column second")


def test_blank_pdf_is_marked_as_needing_ocr_engine(tmp_path):
    pdf_path = _write_pdf(
        tmp_path / "blank.pdf",
        lambda pdf: pdf.showPage(),
    )

    result = parse_pdf_layout(pdf_path)

    assert result.page_count == 1
    assert result.blocks == ()
    assert result.needs_ocr_engine is True
    assert "no_embedded_text_blocks" in result.warnings


def test_doclayout_onnx_without_model_path_falls_back_to_rule_based(tmp_path, monkeypatch):
    monkeypatch.setenv("LAYOUT_PROVIDER", "doclayout_yolo_onnx")
    monkeypatch.delenv("LAYOUT_MODEL_PATH", raising=False)
    pdf_path = _write_pdf(
        tmp_path / "fallback.pdf",
        lambda pdf: _draw_line(pdf, 72, 710, "Fourier Transform", size=18, font="Helvetica-Bold"),
    )

    result = parse_pdf_layout(pdf_path)

    assert result.provider == "rule_based"
    assert result.needs_ocr_engine is False
    assert any("onnx_provider_unavailable:LAYOUT_MODEL_PATH is not set" in warning for warning in result.warnings)


def test_doclayout_onnx_with_real_model_smoke(tmp_path, monkeypatch):
    model_path = os.environ.get("LAYOUT_MODEL_PATH", "").strip()

    if not model_path:
        pytest.skip("Set LAYOUT_MODEL_PATH to run the real DocLayout-YOLO ONNX smoke test.")

    if not Path(model_path).exists():
        pytest.fail(f"LAYOUT_MODEL_PATH does not exist: {model_path}")

    pytest.importorskip("numpy")
    pytest.importorskip("onnxruntime")
    monkeypatch.setenv("LAYOUT_PROVIDER", "doclayout_yolo_onnx")
    pdf_path = _write_pdf(
        tmp_path / "real-model-smoke.pdf",
        lambda pdf: (
            _draw_line(pdf, 72, 766, "Course Notes", size=9),
            _draw_line(pdf, 72, 710, "Fourier Transform", size=18, font="Helvetica-Bold"),
            _draw_line(pdf, 72, 680, "Maps signals into frequency components.", size=11),
            _draw_line(pdf, 72, 630, "Hash Table", size=18, font="Helvetica-Bold"),
            _draw_line(pdf, 72, 600, "Stores key value pairs for fast lookup.", size=11),
            _draw_line(pdf, 280, 28, "Footer Marker", size=9),
        ),
    )

    result = parse_pdf_layout(pdf_path)
    text = layout_blocks_to_text(result.blocks)

    assert result.provider == "doclayout_yolo_onnx"
    assert result.needs_ocr_engine is False
    assert result.warnings == ()
    assert "Fourier Transform" in text
    assert "Hash Table" in text
    assert "Course Notes" not in text
    assert "Footer Marker" not in text
    assert len(text.split("Fourier Transform")) == 2
    assert len(text.split("Hash Table")) == 2


def test_invalid_model_score_threshold_env_uses_default(monkeypatch):
    monkeypatch.setenv("LAYOUT_MODEL_SCORE_THRESHOLD", "not-a-number")

    assert layout_service._model_score_threshold() == 0.25


def test_model_block_dedup_removes_contained_text_duplicate():
    parent = layout_service.LayoutBlock(
        page_number=1,
        text="The Fourier Transform maps a signal into frequency components. It is used in signal processing.",
        bbox=layout_service.BoundingBox(70, 118, 395, 156),
        layout_type="text",
        reading_order=1,
        page_width=612,
        page_height=792,
        provider="doclayout_yolo_onnx",
        confidence=0.29,
    )
    child = layout_service.LayoutBlock(
        page_number=1,
        text="The Fourier Transform maps a signal into frequency components.",
        bbox=layout_service.BoundingBox(71, 119, 393, 133),
        layout_type="text",
        reading_order=2,
        page_width=612,
        page_height=792,
        provider="doclayout_yolo_onnx",
        confidence=0.73,
    )

    blocks = layout_service._deduplicate_model_blocks([parent, child])

    assert len(blocks) == 1
    assert blocks[0].text == parent.text
    assert blocks[0].bbox == parent.bbox
    assert blocks[0].confidence == 0.73


def test_app_pdf_extractor_uses_layout_text_without_header_footer(app_module, tmp_path):
    pdf_path = _write_pdf(
        tmp_path / "app-layout.pdf",
        lambda pdf: (
            _draw_line(pdf, 72, 766, "Course Notes", size=9),
            _draw_line(pdf, 72, 710, "Merge Sort", size=18, font="Helvetica-Bold"),
            _draw_line(pdf, 72, 680, "Divides the input list into smaller lists.", size=11),
            _draw_line(pdf, 280, 28, "Page 1", size=9),
        ),
    )

    text = app_module.extract_text_from_pdf(pdf_path)

    assert "[Page 1]" in text
    assert "Merge Sort" in text
    assert "Course Notes" not in text


def test_header_footer_only_pdf_does_not_fallback_to_raw_chunks(app_module, client, tmp_path, monkeypatch):
    monkeypatch.delenv("LAYOUT_PROVIDER", raising=False)
    monkeypatch.delenv("LAYOUT_MODEL_PATH", raising=False)
    pdf_path = _write_pdf(
        tmp_path / "header-footer-only.pdf",
        lambda pdf: (
            _draw_line(pdf, 72, 766, "Course Notes", size=9),
            _draw_line(pdf, 280, 28, "Footer Marker", size=9),
        ),
    )

    with pdf_path.open("rb") as file_obj:
        response = client.post(
            "/api/knowledge/upload",
            data={
                "file": (file_obj, "header-footer-only.pdf"),
                "course": "Signals",
                "title": "Noise Fixture",
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    assert response.get_json()["status"] == "error"

    with app_module.app.app_context():
        assert app_module.KnowledgeDocument.query.count() == 0
        assert app_module.KnowledgeChunk.query.count() == 0


def test_knowledge_upload_persists_layout_metadata(app_module, client, tmp_path, monkeypatch):
    monkeypatch.delenv("LAYOUT_PROVIDER", raising=False)
    monkeypatch.delenv("LAYOUT_MODEL_PATH", raising=False)
    pdf_path = _write_pdf(
        tmp_path / "knowledge-layout.pdf",
        lambda pdf: (
            _draw_line(pdf, 72, 766, "Course Notes", size=9),
            _draw_line(pdf, 72, 710, "Fourier Transform", size=18, font="Helvetica-Bold"),
            _draw_line(pdf, 72, 680, "Maps signals into frequency components.", size=11),
            _draw_line(pdf, 280, 28, "Footer Marker", size=9),
        ),
    )

    with pdf_path.open("rb") as file_obj:
        response = client.post(
            "/api/knowledge/upload",
            data={
                "file": (file_obj, "knowledge-layout.pdf"),
                "course": "Signals",
                "title": "Layout Fixture",
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["document"]["layout_provider"] == "rule_based"
    assert payload["document"]["layout_status"] == "parsed"

    with app_module.app.app_context():
        document = app_module.KnowledgeDocument.query.one()
        chunks = app_module.KnowledgeChunk.query.order_by(app_module.KnowledgeChunk.chunk_index).all()

    assert document.layout_provider == "rule_based"
    assert document.layout_status == "parsed"
    assert json.loads(document.layout_warnings_json) == []
    assert len(chunks) >= 2
    assert all(chunk.source_page == "Page 1" for chunk in chunks)
    assert all(chunk.layout_provider == "rule_based" for chunk in chunks)
    assert all(chunk.page_number == 1 for chunk in chunks)
    assert any(chunk.layout_type == "title" and chunk.content == "Fourier Transform" for chunk in chunks)
    assert any("frequency components" in chunk.content and chunk.layout_type == "text" for chunk in chunks)
    assert all("Course Notes" not in chunk.content for chunk in chunks)
    assert all("Footer Marker" not in chunk.content for chunk in chunks)
    assert all(json.loads(chunk.bbox_json) for chunk in chunks)
