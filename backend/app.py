from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text as sql_text
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

import json
import os
import re
import uuid
import zipfile
from datetime import datetime

try:
    from .services.layout import (
        SKIPPED_TEXT_LAYOUT_TYPES,
        extract_pdf_text_with_layout,
        extract_pdf_text_with_layout_result,
    )
    from .services.retrieval import score_knowledge_evidence
    from .services.term_extraction import extract_terms_from_text as extract_terms_from_text_service
except ImportError:
    from services.layout import (
        SKIPPED_TEXT_LAYOUT_TYPES,
        extract_pdf_text_with_layout,
        extract_pdf_text_with_layout_result,
    )
    from services.retrieval import score_knowledge_evidence
    from services.term_extraction import extract_terms_from_text as extract_terms_from_text_service


# ============================================================
# LexiBridge AI v0.1
# 教师审核型专业术语标准化平台 MVP
#
# 当前版本定位：
# 1. 不伪造 AI 专业翻译
# 2. 不写死具体学科术语
# 3. 后端只做文件解析、候选术语抽取、数据库存储
# 4. 最终中文译名和解释由教师审核确认
# 5. 后续可以在 generate_term_suggestion() 位置接入 AI API / RAG
# ============================================================


app = Flask(__name__)
CORS(app)


# ============================================================
# 路径与数据库配置
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MAX_UPLOAD_SIZE_MB = 50


def positive_int_env(name, default):
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default

    return value if value > 0 else default

# 上传目录放在用户目录，避免 Windows 中误把 uploads 建成文件后报错
DEFAULT_UPLOAD_FOLDER = os.path.join(os.path.expanduser("~"), "LexiBridge-AI-uploads")
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "").strip() or DEFAULT_UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
MAX_UPLOAD_SIZE_MB = positive_int_env("MAX_UPLOAD_SIZE_MB", DEFAULT_MAX_UPLOAD_SIZE_MB)

DEFAULT_DATABASE_FOLDER = os.path.join(os.path.expanduser("~"), "LexiBridge-AI-data")
DATABASE_FOLDER = os.environ.get("DATABASE_FOLDER", "").strip() or DEFAULT_DATABASE_FOLDER

DATABASE_PATH = os.path.join(DATABASE_FOLDER, "lexibridge.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if not DATABASE_URL:
    os.makedirs(DATABASE_FOLDER, exist_ok=True)
    DATABASE_URL = "sqlite:///" + DATABASE_PATH

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE_MB * 1024 * 1024

db = SQLAlchemy(app)
migrate = Migrate(app, db, render_as_batch=True, compare_type=True)

ALLOWED_EXTENSIONS = {"pdf", "docx", "pptx"}
OOXML_REQUIRED_MEMBERS = {
    "docx": "word/document.xml",
    "pptx": "ppt/presentation.xml",
}


# ============================================================
# 数据表
# ============================================================

class Term(db.Model):
    """
    术语表：
    pending  = 候选术语，等待教师审核
    approved = 教师审核通过，学生端可见
    """
    id = db.Column(db.Integer, primary_key=True)

    course = db.Column(db.String(120), nullable=False, default="Data Structures and Algorithms")
    chapter = db.Column(db.String(120), nullable=False, default="Chapter 4 - Hashing")

    english_term = db.Column(db.String(200), nullable=False)
    chinese_term = db.Column(db.String(200), default="待教师审核")
    explanation = db.Column(db.Text, default="待教师审核：系统仅完成候选术语抽取，尚未生成正式专业译名。")
    context = db.Column(db.Text, default="")

    confidence = db.Column(db.Integer, default=60)
    status = db.Column(db.String(30), default="pending")
class Feedback(db.Model):
    """
    学生反馈表：
    用于记录学生对已审核术语提出的问题。
    """
    id = db.Column(db.Integer, primary_key=True)

    term_id = db.Column(db.Integer, nullable=False)

    course = db.Column(db.String(120), default="")
    chapter = db.Column(db.String(120), default="")

    english_term = db.Column(db.String(200), default="")
    chinese_term = db.Column(db.String(200), default="")

    feedback_type = db.Column(db.String(80), default="其他问题")
    feedback_content = db.Column(db.Text, default="")

    status = db.Column(db.String(30), default="open")
    created_at = db.Column(db.String(40), default="")

class KnowledgeDocument(db.Model):
    """
    课程知识库文档表：
    用于记录教师上传的中文教材、中文课件、中文参考资料。
    """
    id = db.Column(db.Integer, primary_key=True)

    course = db.Column(db.String(120), nullable=False, default="")
    title = db.Column(db.String(200), nullable=False, default="")
    filename = db.Column(db.String(260), default="")
    saved_filename = db.Column(db.String(260), default="")
    file_type = db.Column(db.String(30), default="")

    language = db.Column(db.String(30), default="zh")
    source_type = db.Column(db.String(80), default="教师上传资料")

    text_length = db.Column(db.Integer, default=0)
    chunk_count = db.Column(db.Integer, default=0)
    layout_provider = db.Column(db.String(80), default="")
    layout_status = db.Column(db.String(40), default="not_run")
    layout_warnings_json = db.Column(db.Text, default="[]")

    created_at = db.Column(db.String(40), default="")


class KnowledgeChunk(db.Model):
    """
    课程知识库片段表：
    每个文档会被切分为多个 chunk，后续用于检索和 RAG。
    """
    id = db.Column(db.Integer, primary_key=True)

    document_id = db.Column(db.Integer, nullable=False)

    course = db.Column(db.String(120), nullable=False, default="")
    title = db.Column(db.String(200), default="")

    chunk_index = db.Column(db.Integer, default=0)
    content = db.Column(db.Text, nullable=False, default="")

    source_page = db.Column(db.String(80), default="")
    page_number = db.Column(db.Integer, nullable=True)
    bbox_json = db.Column(db.Text, default="{}")
    layout_type = db.Column(db.String(64), default="")
    reading_order = db.Column(db.Integer, nullable=True)
    layout_provider = db.Column(db.String(80), default="")
    layout_confidence = db.Column(db.Float, nullable=True)
    quality_flags_json = db.Column(db.Text, default="[]")
    created_at = db.Column(db.String(40), default="")


class TerminologyCard(db.Model):
    """
    v1.0 terminology card persistence model.

    The legacy Term table remains the local MVP glossary surface. This table is
    the evidence-backed card schema used by the alignment/QC pipeline.
    """
    __tablename__ = "terminology_card"
    __table_args__ = (
        db.UniqueConstraint(
            "course_id",
            "normalized_english_term",
            "scope_type",
            name="uq_terminology_card_course_term_scope",
        ),
        db.UniqueConstraint(
            "owner_user_id",
            "normalized_english_term",
            "source_document_id",
            "scope_type",
            name="uq_terminology_card_personal_term_source",
        ),
        db.Index("ix_terminology_card_scope_type", "scope_type"),
        db.Index("ix_terminology_card_course_id", "course_id"),
        db.Index("ix_terminology_card_owner_user_id", "owner_user_id"),
        db.Index(
            "ix_terminology_card_normalized_english_term",
            "normalized_english_term",
        ),
        db.Index("ix_terminology_card_final_chinese_term", "final_chinese_term"),
        db.Index(
            "ix_terminology_card_normalized_chinese_term",
            "normalized_chinese_term",
        ),
        db.Index(
            "ix_terminology_card_english_evidence_chunk_id",
            "english_evidence_chunk_id",
        ),
        db.Index(
            "ix_terminology_card_chinese_evidence_chunk_id",
            "chinese_evidence_chunk_id",
        ),
        db.Index("ix_terminology_card_alignment_status", "alignment_status"),
        db.Index("ix_terminology_card_status", "status"),
        db.Index("ix_terminology_card_feedback_count", "feedback_count"),
    )

    id = db.Column(db.Integer, primary_key=True)

    scope_type = db.Column(db.String(32), nullable=False, default="course")
    course_id = db.Column(db.Integer, nullable=True)
    owner_user_id = db.Column(db.Integer, nullable=True)
    source_document_id = db.Column(db.Integer, nullable=True)

    english_term = db.Column(db.String(255), nullable=False)
    normalized_english_term = db.Column(db.String(255), nullable=False)
    final_chinese_term = db.Column(db.String(255), nullable=True)
    normalized_chinese_term = db.Column(db.String(255), nullable=True)
    courseware_sentence = db.Column(db.Text, nullable=True)

    english_evidence_chunk_id = db.Column(db.Integer, nullable=True)
    chinese_evidence_chunk_id = db.Column(db.Integer, nullable=True)
    english_evidence_snapshot = db.Column(db.Text, nullable=True)
    chinese_evidence_snapshot = db.Column(db.Text, nullable=True)
    english_evidence_score = db.Column(db.Float, default=0)
    chinese_evidence_score = db.Column(db.Float, default=0)

    alignment_status = db.Column(
        db.String(64),
        nullable=False,
        default="unverified_translation",
    )
    confidence_score = db.Column(db.Float, nullable=False, default=0)
    status = db.Column(
        db.String(64),
        nullable=False,
        default="pending_quality_control",
    )

    ai_provider = db.Column(db.String(64), nullable=True)
    ai_model = db.Column(db.String(128), nullable=True)
    prompt_version = db.Column(db.String(64), nullable=True)
    score_breakdown_json = db.Column(db.Text, default="{}")
    quality_flags_json = db.Column(db.Text, default="[]")
    risk_note = db.Column(db.Text, nullable=True)

    feedback_count = db.Column(db.Integer, nullable=False, default=0)
    approved_by = db.Column(db.Integer, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


# ============================================================
# 工具函数：文件类型、文本清洗、文本解析
# ============================================================

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def file_extension(filename):
    if "." not in filename:
        return ""

    return filename.rsplit(".", 1)[1].lower()


def is_allowed_upload_content(file_storage):
    ext = file_extension(file_storage.filename)
    stream = file_storage.stream
    position = stream.tell()

    try:
        stream.seek(0)

        if ext == "pdf":
            return stream.read(5) == b"%PDF-"

        required_member = OOXML_REQUIRED_MEMBERS.get(ext)

        if not required_member:
            return False

        try:
            with zipfile.ZipFile(stream) as archive:
                members = set(archive.namelist())
        except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError):
            return False

        return "[Content_Types].xml" in members and required_member in members
    finally:
        stream.seek(position)


def unsupported_file_response(message="文件格式不支持，目前只支持 PDF、DOCX、PPTX。"):
    return jsonify({
        "status": "error",
        "error_code": "UNSUPPORTED_FILE_TYPE",
        "message": message
    }), 400


def invalid_file_content_response():
    return jsonify({
        "status": "error",
        "error_code": "INVALID_FILE_CONTENT",
        "message": "文件内容与扩展名不匹配，无法安全解析。"
    }), 400


def clean_text(text):
    """
    对 PDF / Word / PPT 抽取出的文本做基础清洗。
    这里不做语义判断，只做格式规整。
    """
    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_from_pdf(path):
    """
    PDF 文本解析。
    依赖 PyMuPDF：pip install pymupdf
    """
    layout_text = extract_pdf_text_with_layout(path)

    if layout_text:
        return clean_text(layout_text)

    try:
        import fitz
    except ImportError as exc:
        raise ImportError("缺少 PyMuPDF，请运行：pip install pymupdf") from exc

    parts = []
    with fitz.open(path) as doc:
        for index, page in enumerate(doc, start=1):
            page_text = page.get_text("text") or ""
            if page_text.strip():
                parts.append(f"[Page {index}]\n{page_text}")

    return clean_text("\n\n".join(parts))


def extract_text_from_docx(path):
    """
    DOCX 文本解析。
    依赖 python-docx：pip install python-docx
    """
    try:
        from docx import Document
    except ImportError as exc:
        raise ImportError("缺少 python-docx，请运行：pip install python-docx") from exc

    document = Document(path)
    parts = []

    for paragraph in document.paragraphs:
        content = paragraph.text.strip()
        if content:
            parts.append(content)

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    return clean_text("\n".join(parts))


def extract_text_from_pptx(path):
    """
    PPTX 文本解析。
    依赖 python-pptx：pip install python-pptx
    """
    try:
        from pptx import Presentation
    except ImportError as exc:
        raise ImportError("缺少 python-pptx，请运行：pip install python-pptx") from exc

    presentation = Presentation(path)
    parts = []

    for slide_index, slide in enumerate(presentation.slides, start=1):
        slide_parts = [f"[Slide {slide_index}]"]

        for shape in slide.shapes:
            if hasattr(shape, "text"):
                content = shape.text.strip()
                if content:
                    slide_parts.append(content)

        if len(slide_parts) > 1:
            parts.append("\n".join(slide_parts))

    return clean_text("\n\n".join(parts))

def extract_text(path):
    ext = path.rsplit(".", 1)[1].lower()

    if ext == "pdf":
        return extract_text_from_pdf(path)

    if ext == "docx":
        return extract_text_from_docx(path)

    if ext == "pptx":
        return extract_text_from_pptx(path)

    raise ValueError("不支持的文件格式")


def extract_text_with_layout(path):
    ext = path.rsplit(".", 1)[1].lower()

    if ext != "pdf":
        return extract_text(path), None

    layout_text, layout_result = extract_pdf_text_with_layout_result(path)

    if layout_text:
        return clean_text(layout_text), layout_result

    if layout_result and layout_result.needs_ocr_engine:
        return "", layout_result

    try:
        import fitz
    except ImportError as exc:
        raise ImportError("缺少 PyMuPDF，请运行：pip install pymupdf") from exc

    parts = []
    with fitz.open(path) as doc:
        for index, page in enumerate(doc, start=1):
            page_text = page.get_text("text") or ""
            if page_text.strip():
                parts.append(f"[Page {index}]\n{page_text}")

    return clean_text("\n\n".join(parts)), layout_result

def split_text_into_chunks(text, max_chars=700, overlap=80):
    """
    将知识库文本切分为较小片段。
    后续 RAG 检索时，不应该直接检索整本文档，而应该检索 chunk。
    """
    text = clean_text(text)

    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    chunks = []
    current = ""

    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= max_chars:
            current = (current + "\n\n" + paragraph).strip()
        else:
            if current:
                chunks.append(current)

            if len(paragraph) <= max_chars:
                current = paragraph
            else:
                start = 0
                while start < len(paragraph):
                    end = min(start + max_chars, len(paragraph))
                    part = paragraph[start:end].strip()

                    if part:
                        chunks.append(part)

                    if end >= len(paragraph):
                        break

                    start = max(0, end - overlap)

                current = ""

    if current:
        chunks.append(current)

    cleaned_chunks = []

    for chunk in chunks:
        chunk = re.sub(r"\s+", " ", chunk).strip()

        if len(chunk) >= 30:
            cleaned_chunks.append(chunk)

    return cleaned_chunks


def build_knowledge_chunk_payloads(text, layout_result=None):
    if not layout_result:
        return [{"content": chunk} for chunk in split_text_into_chunks(text)]

    payloads = []
    reading_order = 1

    for block in sorted(layout_result.blocks, key=lambda item: (item.page_number, item.reading_order)):
        content = clean_text(block.text)

        if not content or block.layout_type in SKIPPED_TEXT_LAYOUT_TYPES:
            continue

        for chunk_text in split_layout_block_text(content):
            payloads.append({
                "content": chunk_text,
                "source_page": f"Page {block.page_number}",
                "page_number": block.page_number,
                "bbox_json": _json_dumps(block.bbox.to_dict()),
                "layout_type": block.layout_type,
                "reading_order": reading_order,
                "layout_provider": block.provider,
                "layout_confidence": block.confidence,
            })
            reading_order += 1

    if payloads:
        return payloads

    if layout_result.needs_ocr_engine:
        return []

    return [{"content": chunk} for chunk in split_text_into_chunks(text)]


def split_layout_block_text(text):
    chunks = split_text_into_chunks(text)

    if chunks:
        return chunks

    text = clean_text(text)

    if len(text) >= 3:
        return [text]

    return []


def layout_status_for_result(layout_result):
    if not layout_result:
        return "not_applicable"

    if layout_result.needs_ocr_engine:
        return "needs_ocr"

    if layout_result.blocks:
        return "parsed"

    return "no_blocks"


def _json_dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

def score_knowledge_chunk(content, query):
    """
    保留旧函数名，具体评分逻辑由 services.retrieval 负责。
    """
    return score_knowledge_evidence(content, query)["score"]

# ============================================================
# 候选术语抽取
# ============================================================

def extract_terms_from_text(text):
    """
    通用候选术语抽取版本：
    1. 不写死具体专业术语；
    2. 不预设数学 / 物理 / 通信 / 计算机等学科关键词；
    3. 不伪造中文翻译；
    4. 只根据词组形态、出现频率、大小写、上下文等通用特征筛选候选术语；
    5. 最终术语是否成立，由教师审核或后续 AI API / RAG 决定。
    """
    return extract_terms_from_text_service(text)


# ============================================================
# 预留：后续接入 AI API / RAG 的位置
# ============================================================

def generate_term_suggestion(english_term, context, course):
    """
    v0.2 可在这里接入 AI API。
    目标输入：英文术语 + 上下文 + 课程名称
    目标输出：中文译名 + 专业解释 + 置信度 + 依据
    当前 v0.1 不调用，避免伪造专业翻译。
    """
    return {
        "chinese_term": "待教师审核",
        "explanation": "待教师审核：当前版本未接入 AI API。",
        "confidence": 60
    }


def serialize_term(term):
    return {
        "id": term.id,
        "course": term.course,
        "chapter": term.chapter,
        "english_term": term.english_term,
        "chinese_term": term.chinese_term,
        "explanation": term.explanation,
        "context": term.context,
        "confidence": term.confidence,
        "status": term.status
    }
def serialize_feedback(feedback):
    return {
        "id": feedback.id,
        "term_id": feedback.term_id,
        "course": feedback.course,
        "chapter": feedback.chapter,
        "english_term": feedback.english_term,
        "chinese_term": feedback.chinese_term,
        "feedback_type": feedback.feedback_type,
        "feedback_content": feedback.feedback_content,
        "status": feedback.status,
        "created_at": feedback.created_at
    }
def serialize_knowledge_document(doc):
    return {
        "id": doc.id,
        "course": doc.course,
        "title": doc.title,
        "filename": doc.filename,
        "saved_filename": doc.saved_filename,
        "file_type": doc.file_type,
        "language": doc.language,
        "source_type": doc.source_type,
        "text_length": doc.text_length,
        "chunk_count": doc.chunk_count,
        "layout_provider": doc.layout_provider,
        "layout_status": doc.layout_status,
        "layout_warnings": _safe_json_loads(doc.layout_warnings_json, []),
        "created_at": doc.created_at
    }


def serialize_knowledge_chunk(chunk):
    return {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "course": chunk.course,
        "title": chunk.title,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "source_page": chunk.source_page,
        "page_number": chunk.page_number,
        "bbox": _safe_json_loads(chunk.bbox_json, {}),
        "layout_type": chunk.layout_type,
        "reading_order": chunk.reading_order,
        "layout_provider": chunk.layout_provider,
        "layout_confidence": chunk.layout_confidence,
        "quality_flags": _safe_json_loads(chunk.quality_flags_json, []),
        "created_at": chunk.created_at
    }


def _safe_json_loads(value, default):
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return default


LAYOUT_SCHEMA_ADDITIONS = {
    "knowledge_document": {
        "layout_provider": "VARCHAR(80) DEFAULT ''",
        "layout_status": "VARCHAR(40) DEFAULT 'not_run'",
        "layout_warnings_json": "TEXT DEFAULT '[]'",
    },
    "knowledge_chunk": {
        "page_number": "INTEGER",
        "bbox_json": "TEXT DEFAULT '{}'",
        "layout_type": "VARCHAR(64) DEFAULT ''",
        "reading_order": "INTEGER",
        "layout_provider": "VARCHAR(80) DEFAULT ''",
        "layout_confidence": "FLOAT",
        "quality_flags_json": "TEXT DEFAULT '[]'",
    },
}


def ensure_layout_schema():
    """
    Lightweight SQLite compatibility helper until Alembic lands.

    New test databases get the columns from SQLAlchemy create_all(); this helper
    only protects existing local SQLite databases from missing layout columns.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return

    with db.engine.begin() as connection:
        for table_name, columns in LAYOUT_SCHEMA_ADDITIONS.items():
            existing_columns = {
                row[1]
                for row in connection.execute(sql_text(f"PRAGMA table_info({table_name})"))
            }

            if not existing_columns:
                continue

            for column_name, definition in columns.items():
                if column_name not in existing_columns:
                    connection.execute(
                        sql_text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
                    )


# ============================================================
# API 路由
# ============================================================

@app.route("/")
def home():
    return jsonify({
        "message": "LexiBridge AI backend is running.",
        "version": "0.1.0"
    })


@app.route("/api/test", methods=["GET"])
def test():
    return jsonify({
        "status": "success",
        "project": "智桥术语云 LexiBridge AI",
        "message": "前端和后端连接测试成功。"
    })


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(_exc):
    return jsonify({
        "status": "error",
        "error_code": "FILE_TOO_LARGE",
        "message": f"文件过大，最大允许 {MAX_UPLOAD_SIZE_MB} MB。"
    }), 413


@app.route("/api/knowledge/documents", methods=["GET"])
def get_knowledge_documents():
    """
    教师端：读取课程知识库文档列表。
    可选参数：
    - course
    """
    course = request.args.get("course", "").strip()

    query = KnowledgeDocument.query

    if course:
        query = query.filter_by(course=course)

    documents = query.order_by(KnowledgeDocument.id.desc()).all()

    return jsonify({
        "status": "success",
        "count": len(documents),
        "documents": [serialize_knowledge_document(doc) for doc in documents]
    })

@app.route("/api/knowledge/upload", methods=["POST"])
def upload_knowledge_document():
    """
    教师端上传课程知识库资料：
    1. 接收 PDF / DOCX / PPTX
    2. 解析文本
    3. 切分为知识片段
    4. 写入 KnowledgeDocument 和 KnowledgeChunk
    """
    file = request.files.get("file")

    if file is None:
        return jsonify({
            "status": "error",
            "message": "没有收到知识库文件。"
        }), 400

    if file.filename == "":
        return jsonify({
            "status": "error",
            "message": "文件名为空。"
        }), 400

    if not allowed_file(file.filename):
        return unsupported_file_response()

    if not is_allowed_upload_content(file):
        return invalid_file_content_response()

    course = request.form.get("course", "").strip()
    title = request.form.get("title", "").strip()
    language = request.form.get("language", "zh").strip()
    source_type = request.form.get("source_type", "教师上传资料").strip()

    if not course:
        return jsonify({
            "status": "error",
            "message": "课程不能为空。"
        }), 400

    original_filename = secure_filename(file.filename)

    if not title:
        title = file.filename

    ext = file.filename.rsplit(".", 1)[1].lower()

    unique_prefix = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    saved_filename = f"knowledge_{unique_prefix}_{original_filename}"
    save_path = os.path.join(UPLOAD_FOLDER, saved_filename)

    file.save(save_path)

    try:
        extracted_text, layout_result = extract_text_with_layout(save_path)
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": "知识库文件已上传，但解析失败。",
            "error": str(exc)
        }), 500

    chunk_payloads = build_knowledge_chunk_payloads(extracted_text, layout_result)

    if len(chunk_payloads) == 0:
        return jsonify({
            "status": "error",
            "message": "文件解析成功，但没有得到有效知识片段。请确认文件不是扫描版图片 PDF。"
        }), 400

    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    document = KnowledgeDocument(
        course=course,
        title=title,
        filename=file.filename,
        saved_filename=saved_filename,
        file_type=ext,
        language=language or "zh",
        source_type=source_type or "教师上传资料",
        text_length=len(extracted_text),
        chunk_count=len(chunk_payloads),
        layout_provider=layout_result.provider if layout_result else "",
        layout_status=layout_status_for_result(layout_result),
        layout_warnings_json=_json_dumps(layout_result.warnings if layout_result else []),
        created_at=now_text
    )

    db.session.add(document)
    db.session.commit()

    chunk_records = []

    for index, chunk_payload in enumerate(chunk_payloads, start=1):
        chunk = KnowledgeChunk(
            document_id=document.id,
            course=course,
            title=title,
            chunk_index=index,
            content=chunk_payload["content"],
            source_page=chunk_payload.get("source_page", ""),
            page_number=chunk_payload.get("page_number"),
            bbox_json=chunk_payload.get("bbox_json", "{}"),
            layout_type=chunk_payload.get("layout_type", ""),
            reading_order=chunk_payload.get("reading_order"),
            layout_provider=chunk_payload.get("layout_provider", ""),
            layout_confidence=chunk_payload.get("layout_confidence"),
            quality_flags_json=chunk_payload.get("quality_flags_json", "[]"),
            created_at=now_text
        )

        db.session.add(chunk)
        chunk_records.append(chunk)

    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"知识库资料上传成功，已解析 {len(extracted_text)} 个字符，生成 {len(chunk_records)} 个知识片段。",
        "document": serialize_knowledge_document(document),
        "preview": extracted_text[:800],
        "sample_chunks": [
            serialize_knowledge_chunk(chunk) for chunk in chunk_records[:3]
        ]
    })

@app.route("/api/knowledge/search", methods=["GET"])
def search_knowledge_chunks():
    """
    知识库片段检索接口。
    用于后续 AI 翻译前，从课程知识库中找中文依据。

    参数：
    - q: 搜索关键词，必填
    - course: 课程，可选
    - limit: 返回数量，默认 8
    """
    q = (request.args.get("q", "") or request.args.get("query", "")).strip()
    course = request.args.get("course", "").strip()
    limit_raw = request.args.get("limit", "8").strip()

    if not q:
        return jsonify({
            "status": "error",
            "message": "搜索关键词 q 不能为空。"
        }), 400

    try:
        limit = int(limit_raw)
    except ValueError:
        limit = 8

    limit = max(1, min(limit, 30))

    query = KnowledgeChunk.query

    if course:
        query = query.filter_by(course=course)

    chunks = query.all()

    scored_results = []

    for chunk in chunks:
        evidence = score_knowledge_evidence(chunk.content, q)
        score = evidence["score"]

        if score > 0:
            scored_results.append((score, chunk, evidence))

    scored_results.sort(key=lambda item: (-item[0], item[1].id or 0))

    top_results = scored_results[:limit]

    return jsonify({
        "status": "success",
        "query": q,
        "course": course,
        "count": len(top_results),
        "results": [
            {
                "score": score,
                "evidence_score": evidence["evidence_score"],
                "matched_terms": evidence["matched_terms"],
                "score_breakdown": evidence["score_breakdown"],
                "chunk": serialize_knowledge_chunk(chunk)
            }
            for score, chunk, evidence in top_results
        ]
    })

@app.route("/api/upload", methods=["POST"])
def upload_file():
    """
    教师上传文件：
    1. 接收 PDF / DOCX / PPTX
    2. 保存到本地上传目录
    3. 解析文字
    4. 抽取候选术语
    5. 写入 SQLite 数据库
    6. 返回解析预览和候选术语
    """
    file = request.files.get("file")

    if file is None:
        return jsonify({
            "status": "error",
            "message": "没有收到文件。"
        }), 400

    if file.filename == "":
        return jsonify({
            "status": "error",
            "message": "文件名为空。"
        }), 400

    if not allowed_file(file.filename):
        return unsupported_file_response()

    if not is_allowed_upload_content(file):
        return invalid_file_content_response()

    course = request.form.get("course", "Data Structures and Algorithms").strip()
    chapter = request.form.get("chapter", "Chapter 4 - Hashing").strip()

    if not course:
        course = "Data Structures and Algorithms"

    if not chapter:
        chapter = "未指定章节"

    original_filename = secure_filename(file.filename)
    unique_prefix = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    filename = f"{unique_prefix}_{original_filename}"
    save_path = os.path.join(UPLOAD_FOLDER, filename)

    file.save(save_path)

    try:
        extracted_text = extract_text(save_path)
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": "文件已上传，但解析失败。",
            "error": str(exc)
        }), 500

    preview = extracted_text[:800]
    terms = extract_terms_from_text(extracted_text)

    if len(terms) == 0:
        return jsonify({
            "status": "success",
            "message": f"文件上传并解析成功，共提取 {len(extracted_text)} 个字符，但没有抽取到候选术语。旧的待审核术语不会被清空。",
            "filename": original_filename,
            "saved_filename": filename,
            "text_length": len(extracted_text),
            "preview": preview,
            "terms": [],
            "upload_folder": UPLOAD_FOLDER
        })

    # 只清空同一课程、同一章节下的 pending，避免误删其他章节待审核内容
    Term.query.filter_by(course=course, chapter=chapter, status="pending").delete()

    saved_terms = []

    for item in terms:
        # 已审核过的同名术语不再重复进入 pending
        approved_existing = Term.query.filter_by(
            course=course,
            chapter=chapter,
            english_term=item["english_term"],
            status="approved"
        ).first()

        if approved_existing:
            continue

        term_record = Term(
            course=course,
            chapter=chapter,
            english_term=item["english_term"],
            chinese_term=item.get("chinese_term", "待教师审核"),
            explanation=item.get("explanation", "待教师审核：系统仅完成候选术语抽取，尚未生成正式专业译名。"),
            context=item.get("context", ""),
            confidence=int(item.get("confidence", 60)),
            status="pending"
        )

        db.session.add(term_record)
        saved_terms.append(term_record)

    db.session.commit()

    saved_terms_json = [serialize_term(term) for term in saved_terms]

    return jsonify({
        "status": "success",
        "message": f"文件上传、解析并抽取术语成功，共提取 {len(extracted_text)} 个字符，发现 {len(saved_terms_json)} 个新的候选术语。",
        "filename": original_filename,
        "saved_filename": filename,
        "text_length": len(extracted_text),
        "preview": preview,
        "terms": saved_terms_json,
        "upload_folder": UPLOAD_FOLDER
    })


@app.route("/api/terms/pending", methods=["GET"])
def get_pending_terms():
    """
    教师端：读取待审核候选术语。
    可选参数：
    - course
    - chapter
    """
    course = request.args.get("course", "").strip()
    chapter = request.args.get("chapter", "").strip()

    query = Term.query.filter_by(status="pending")

    if course:
        query = query.filter_by(course=course)

    if chapter:
        query = query.filter_by(chapter=chapter)

    terms = query.order_by(Term.id.desc()).all()

    return jsonify({
        "status": "success",
        "count": len(terms),
        "terms": [serialize_term(term) for term in terms]
    })


@app.route("/api/terms/<int:term_id>/approve", methods=["POST"])
def approve_term(term_id):
    """
    教师审核术语：
    1. 根据 ID 找到候选术语
    2. 更新中文译名和解释
    3. 将状态改为 approved
    """
    term = db.session.get(Term, term_id)

    if term is None:
        return jsonify({
            "status": "error",
            "message": "术语不存在。"
        }), 404

    data = request.get_json() or {}

    chinese_term = str(data.get("chinese_term", "")).strip()
    explanation = str(data.get("explanation", "")).strip()

    if not chinese_term:
        return jsonify({
            "status": "error",
            "message": "中文译名不能为空。"
        }), 400

    if not explanation:
        return jsonify({
            "status": "error",
            "message": "解释不能为空。"
        }), 400

    term.chinese_term = chinese_term
    term.explanation = explanation
    term.status = "approved"

    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "术语已审核通过。",
        "term": serialize_term(term)
    })

@app.route("/api/terms/batch-approve", methods=["POST"])
def batch_approve_terms():
    """
    教师端批量审核术语：
    接收多个术语 ID，以及每个术语对应的中文译名和解释。
    只有中文译名和解释都不为空的术语才允许批量通过。
    """
    data = request.get_json() or {}
    items = data.get("terms", [])

    if not isinstance(items, list) or len(items) == 0:
        return jsonify({
            "status": "error",
            "message": "没有收到需要批量审核的术语。"
        }), 400

    approved_terms = []
    failed_items = []

    for item in items:
        term_id = item.get("id")
        chinese_term = str(item.get("chinese_term", "")).strip()
        explanation = str(item.get("explanation", "")).strip()

        if not term_id:
            failed_items.append({
                "id": term_id,
                "reason": "缺少术语 ID"
            })
            continue

        term = db.session.get(Term, int(term_id))

        if term is None:
            failed_items.append({
                "id": term_id,
                "reason": "术语不存在"
            })
            continue

        if not chinese_term or chinese_term == "待教师审核":
            failed_items.append({
                "id": term_id,
                "english_term": term.english_term,
                "reason": "中文译名为空或仍为待教师审核"
            })
            continue

        if not explanation or explanation.startswith("待教师审核"):
            failed_items.append({
                "id": term_id,
                "english_term": term.english_term,
                "reason": "解释为空或仍为待教师审核"
            })
            continue

        term.chinese_term = chinese_term
        term.explanation = explanation
        term.status = "approved"
        approved_terms.append(term)

    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"批量审核完成，成功审核 {len(approved_terms)} 条，跳过 {len(failed_items)} 条。",
        "approved_count": len(approved_terms),
        "failed_count": len(failed_items),
        "failed_items": failed_items,
        "terms": [serialize_term(term) for term in approved_terms]
    })

@app.route("/api/terms/<int:term_id>", methods=["GET"])
def get_term_detail(term_id):
    """
    读取单个术语详情：
    用于教师根据学生反馈修改术语前，获取当前术语内容。
    """
    term = db.session.get(Term, term_id)

    if term is None:
        return jsonify({
            "status": "error",
            "message": "术语不存在。"
        }), 404

    return jsonify({
        "status": "success",
        "term": serialize_term(term)
    })

@app.route("/api/terms/<int:term_id>/update", methods=["POST"])
def update_term(term_id):
    """
    教师端修改术语：
    用于根据学生反馈修正已审核术语的中文译名和专业解释。
    """
    term = db.session.get(Term, term_id)

    if term is None:
        return jsonify({
            "status": "error",
            "message": "术语不存在。"
        }), 404

    data = request.get_json() or {}

    chinese_term = str(data.get("chinese_term", "")).strip()
    explanation = str(data.get("explanation", "")).strip()

    if not chinese_term:
        return jsonify({
            "status": "error",
            "message": "中文译名不能为空。"
        }), 400

    if not explanation:
        return jsonify({
            "status": "error",
            "message": "专业解释不能为空。"
        }), 400

    term.chinese_term = chinese_term
    term.explanation = explanation
    term.status = "approved"

    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "术语已修改并保持为已审核状态。",
        "term": serialize_term(term)
    })

@app.route("/api/terms/<int:term_id>/delete", methods=["DELETE"])
def delete_term(term_id):
    """
    删除术语：
    可删除误抽取、误审核或测试产生的垃圾数据。
    """
    term = db.session.get(Term, term_id)

    if term is None:
        return jsonify({
            "status": "error",
            "message": "术语不存在。"
        }), 404

    db.session.delete(term)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "术语已删除。",
        "deleted_id": term_id
    })


@app.route("/api/glossary", methods=["GET"])
def get_glossary():
    """
    学生端：读取教师审核通过的词汇表。
    可选参数：
    - course
    - chapter
    - q 搜索英文术语 / 中文译名 / 解释
    """
    course = request.args.get("course", "").strip()
    chapter = request.args.get("chapter", "").strip()
    q = request.args.get("q", "").strip().lower()

    query = Term.query.filter_by(status="approved")

    if course:
        query = query.filter_by(course=course)

    if chapter:
        query = query.filter_by(chapter=chapter)

    terms = query.order_by(Term.id.desc()).all()

    if q:
        terms = [
            term for term in terms
            if q in term.english_term.lower()
            or q in term.chinese_term.lower()
            or q in term.explanation.lower()
        ]

    return jsonify({
        "status": "success",
        "count": len(terms),
        "terms": [serialize_term(term) for term in terms]
    })

@app.route("/api/feedback", methods=["POST"])
def submit_feedback():
    """
    学生端提交术语反馈：
    学生可以对已审核术语提出问题，例如：
    1. 中文译名不准确
    2. 专业解释不清楚
    3. 原文上下文不匹配
    4. 其他问题
    """
    data = request.get_json() or {}

    term_id = data.get("term_id")
    feedback_type = str(data.get("feedback_type", "其他问题")).strip()
    feedback_content = str(data.get("feedback_content", "")).strip()

    if not term_id:
        return jsonify({
            "status": "error",
            "message": "缺少术语 ID。"
        }), 400

    if not feedback_content:
        return jsonify({
            "status": "error",
            "message": "反馈内容不能为空。"
        }), 400

    term = db.session.get(Term, int(term_id))

    if term is None:
        return jsonify({
            "status": "error",
            "message": "反馈对应的术语不存在。"
        }), 404

    if term.status != "approved":
        return jsonify({
            "status": "error",
            "message": "只能对教师已审核的术语提交反馈。"
        }), 400

    feedback = Feedback(
        term_id=term.id,
        course=term.course,
        chapter=term.chapter,
        english_term=term.english_term,
        chinese_term=term.chinese_term,
        feedback_type=feedback_type or "其他问题",
        feedback_content=feedback_content,
        status="open",
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    db.session.add(feedback)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "反馈已提交，教师端稍后可以查看。",
        "feedback": serialize_feedback(feedback)
    })

@app.route("/api/feedback", methods=["GET"])
def get_feedback_list():
    """
    教师端读取学生反馈列表。
    可选参数：
    - status=open
    - status=resolved
    - course=...
    - chapter=...
    """
    status = request.args.get("status", "").strip()
    course = request.args.get("course", "").strip()
    chapter = request.args.get("chapter", "").strip()

    query = Feedback.query

    if status:
        query = query.filter_by(status=status)

    if course:
        query = query.filter_by(course=course)

    if chapter:
        query = query.filter_by(chapter=chapter)

    feedbacks = query.order_by(Feedback.id.desc()).all()

    return jsonify({
        "status": "success",
        "count": len(feedbacks),
        "feedbacks": [serialize_feedback(feedback) for feedback in feedbacks]
    })

@app.route("/api/feedback/<int:feedback_id>/resolve", methods=["POST"])
def resolve_feedback(feedback_id):
    """
    教师端将学生反馈标记为已处理。
    """
    feedback = db.session.get(Feedback, feedback_id)

    if feedback is None:
        return jsonify({
            "status": "error",
            "message": "反馈记录不存在。"
        }), 404

    feedback.status = "resolved"
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "反馈已标记为已处理。",
        "feedback": serialize_feedback(feedback)
    })

@app.route("/api/terms/clear-pending", methods=["DELETE"])
def clear_pending_terms():
    """
    开发辅助接口：清空 pending 候选术语。
    默认只建议本地开发使用。
    """
    course = request.args.get("course", "").strip()
    chapter = request.args.get("chapter", "").strip()

    query = Term.query.filter_by(status="pending")

    if course:
        query = query.filter_by(course=course)

    if chapter:
        query = query.filter_by(chapter=chapter)

    deleted_count = query.delete()
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"已清空 {deleted_count} 条待审核术语。",
        "deleted_count": deleted_count
    })


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        ensure_layout_schema()

    app.run(debug=True, port=5000, use_reloader=False)
