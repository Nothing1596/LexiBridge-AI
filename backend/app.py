from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

import os
import re
import uuid
from datetime import datetime


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

# 上传目录放在用户目录，避免 Windows 中误把 uploads 建成文件后报错
UPLOAD_FOLDER = os.path.join(os.path.expanduser("~"), "LexiBridge-AI-uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATABASE_FOLDER = os.path.join(os.path.expanduser("~"), "LexiBridge-AI-data")
os.makedirs(DATABASE_FOLDER, exist_ok=True)

DATABASE_PATH = os.path.join(DATABASE_FOLDER, "lexibridge.db")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + DATABASE_PATH
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

ALLOWED_EXTENSIONS = {"pdf", "docx", "pptx"}


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
    created_at = db.Column(db.String(40), default="")


# ============================================================
# 工具函数：文件类型、文本清洗、文本解析
# ============================================================

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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

def score_knowledge_chunk(content, query):
    """
    简单关键词检索评分。
    当前是 v0.1 检索版本：
    1. 精确包含 query，加高分
    2. query 中的英文词、数字、中文词片段命中，加分
    3. 后续可替换为 embedding / 向量检索
    """
    if not content or not query:
        return 0

    content_lower = content.lower()
    query_lower = query.lower().strip()

    score = 0

    if query_lower in content_lower:
        score += 100

    tokens = re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{2,}", query_lower)

    for token in tokens:
        if token and token in content_lower:
            score += 20

    # 对中文短词做额外滑窗匹配，例如“收敛级数”
    chinese_chars = re.findall(r"[\u4e00-\u9fff]+", query_lower)

    for phrase in chinese_chars:
        if len(phrase) >= 2:
            for i in range(len(phrase) - 1):
                sub = phrase[i:i + 2]
                if sub in content_lower:
                    score += 6

    return score

# ============================================================
# 候选术语抽取
# ============================================================

def extract_context(text, term, window=140):
    """
    提取术语在原文中的上下文，方便教师审核。
    """
    lower_text = text.lower()
    lower_term = term.lower()
    index = lower_text.find(lower_term)

    if index == -1:
        return ""

    start = max(0, index - window)
    end = min(len(text), index + len(term) + window)

    context = text[start:end]
    context = re.sub(r"\s+", " ", context)
    return context.strip()


def is_probably_noise(term):
    """
    通用噪声过滤。
    注意：这里不写死数学、物理、通信、计算机等具体学科关键词。
    只过滤明显不是术语的句子碎片、页面信息、学校信息、普通功能词。
    """
    lower = term.lower().strip()
    words = lower.split()

    if not lower:
        return True

    blacklist_exact = {
        "page", "slide", "chapter", "section", "example", "problem", "solution",
        "find", "suppose", "therefore", "then", "where", "when", "what",
        "beijing university", "posts and telecommunications",
        "international school", "jianhua yuan"
    }

    if lower in blacklist_exact:
        return True

    bad_starts = {
        "the", "this", "that", "these", "those",
        "a", "an", "and", "or", "but",
        "if", "when", "where", "why", "how", "what", "which",
        "we", "you", "they", "he", "she", "it",
        "suppose", "choose", "find", "show", "prove", "let",
        "in", "on", "at", "for", "with", "by", "from", "to", "of",
        "as", "is", "are", "was", "were"
    }

    bad_ends = {
        "the", "a", "an", "and", "or", "but",
        "is", "are", "was", "were", "be", "been",
        "in", "on", "at", "for", "with", "by", "from", "to", "of",
        "this", "that", "these", "those", "each"
    }

    if words and words[0] in bad_starts:
        return True

    if words and words[-1] in bad_ends:
        return True

    sentence_verbs = {
        "can", "will", "would", "could", "should", "may", "might",
        "must", "have", "has", "had", "do", "does", "did"
    }

    if any(word in sentence_verbs for word in words):
        return True

    # 全小写且过长，通常是句子碎片
    if len(words) >= 3 and term.islower():
        return True

    # 数字比例过高通常不是术语
    letters = sum(ch.isalpha() for ch in term)
    digits = sum(ch.isdigit() for ch in term)
    if digits > letters:
        return True

    return False


def score_candidate(term, count, context):
    """
    给候选术语打分。
    这是启发式评分，不代表真正的 AI 判断。
    """
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

    if all(word[:1].isupper() for word in words if word):
        score += 8

    if "-" in term:
        score += 5

    # 领域无关的学术词形特征：不是学科关键词，只是术语形态线索
    morphology_suffixes = (
        "tion", "sion", "ment", "ness", "ity", "ics",
        "ism", "ance", "ence", "ing", "al", "ive", "ous"
    )
    if any(word.lower().endswith(morphology_suffixes) for word in words):
        score += 6

    definition_clues = (
        "is called", "is defined as", "means", "refers to",
        "denoted by", "known as", "consists of"
    )
    lower_context = context.lower()
    if any(clue in lower_context for clue in definition_clues):
        score += 5

    return max(0, min(score, 95))


def extract_terms_from_text(text):
    """
    通用候选术语抽取版本：
    1. 不写死具体专业术语；
    2. 不预设数学 / 物理 / 通信 / 计算机等学科关键词；
    3. 不伪造中文翻译；
    4. 只根据词组形态、出现频率、大小写、上下文等通用特征筛选候选术语；
    5. 最终术语是否成立，由教师审核或后续 AI API / RAG 决定。
    """
    if not text or not text.strip():
        return []

    # 1 到 5 个英文 token 构成的短语
    phrase_pattern = re.compile(
        r"\b[A-Za-z][A-Za-z0-9]*(?:[-/][A-Za-z0-9]+)*(?:\s+[A-Za-z][A-Za-z0-9]*(?:[-/][A-Za-z0-9]+)*){0,4}\b"
    )

    raw_counts = {}
    display_form = {}
    contexts = {}

    for match in phrase_pattern.findall(text):
        term = " ".join(match.split()).strip()

        if len(term) < 4 or len(term) > 80:
            continue

        words = term.split()
        if len(words) > 5:
            continue

        if is_probably_noise(term):
            continue

        # 单词候选更容易误抽，所以提高门槛：
        # 允许：大写缩写、首字母大写、重复出现的学术词形。
        key = term.lower()

        raw_counts[key] = raw_counts.get(key, 0) + 1

        if key not in display_form:
            display_form[key] = term

        if key not in contexts:
            contexts[key] = extract_context(text, term)

    scored = []

    for key, count in raw_counts.items():
        term = display_form[key]
        words = term.split()
        context = contexts.get(key, "")

        # 单词候选：如果全小写且只出现一次，通常不可靠
        if len(words) == 1 and term.islower() and count < 2:
            continue

        score = score_candidate(term, count, context)

        if score < 55:
            continue

        scored.append((score, count, term, context))

    # 高分优先；同分时出现次数多者优先；再按长度排序
    scored.sort(key=lambda item: (item[0], item[1], len(item[2])), reverse=True)

    candidates = []
    seen = set()

    for score, count, term, context in scored:
        key = term.lower()

        if key in seen:
            continue

        seen.add(key)

        candidates.append({
            "english_term": term,
            "chinese_term": "待教师审核",
            "explanation": "待教师审核：系统仅完成候选术语抽取，尚未生成正式专业译名。",
            "context": context,
            "confidence": score,
            "status": "pending"
        })

    return candidates


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
        "created_at": chunk.created_at
    }


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
        return jsonify({
            "status": "error",
            "message": "文件格式不支持，目前只支持 PDF、DOCX、PPTX。"
        }), 400

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
        extracted_text = extract_text(save_path)
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": "知识库文件已上传，但解析失败。",
            "error": str(exc)
        }), 500

    chunks = split_text_into_chunks(extracted_text)

    if len(chunks) == 0:
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
        chunk_count=len(chunks),
        created_at=now_text
    )

    db.session.add(document)
    db.session.commit()

    chunk_records = []

    for index, chunk_text in enumerate(chunks, start=1):
        chunk = KnowledgeChunk(
            document_id=document.id,
            course=course,
            title=title,
            chunk_index=index,
            content=chunk_text,
            source_page="",
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
    q = request.args.get("q", "").strip()
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
        score = score_knowledge_chunk(chunk.content, q)

        if score > 0:
            scored_results.append((score, chunk))

    scored_results.sort(key=lambda item: item[0], reverse=True)

    top_results = scored_results[:limit]

    return jsonify({
        "status": "success",
        "query": q,
        "course": course,
        "count": len(top_results),
        "results": [
            {
                "score": score,
                "chunk": serialize_knowledge_chunk(chunk)
            }
            for score, chunk in top_results
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
        return jsonify({
            "status": "error",
            "message": "文件格式不支持，目前只支持 PDF、DOCX、PPTX。"
        }), 400

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

    app.run(debug=True, port=5000, use_reloader=False)
