import csv
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from io import StringIO


def _env_int(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _normalize_language(language):
    language = (language or "").strip().lower()
    if language in {"zh", "cn", "chinese", "chi_sim", "bilingual", "mixed"}:
        return "zh"
    if language in {"en", "english", "eng"}:
        return "en"
    return language or "bilingual"


@dataclass
class OCRTextResult:
    status: str
    text: str = ""
    confidence: float = 0
    provider: str = ""
    language: str = ""
    error: str = ""
    blocks: list = field(default_factory=list)
    quality_flags: list = field(default_factory=list)

    @property
    def ok(self):
        return self.status == "ok" and bool(self.text.strip())


# Backward compatible name used by older imports/tests.
OCRResult = OCRTextResult


class OCRProvider:
    provider_name = "none"

    def is_available(self):
        return False

    def recognize_image(self, image_path, language=""):
        return OCRTextResult(
            status="ocr_unavailable",
            provider=self.provider_name,
            language=_normalize_language(language),
            error="No OCR provider is configured."
        )


class NoneOCRProvider(OCRProvider):
    provider_name = "none"


class MockOCRProvider(OCRProvider):
    provider_name = "mock"

    def recognize_image(self, image_path, language=""):
        return OCRTextResult(
            status="ocr_unavailable",
            provider=self.provider_name,
            language=_normalize_language(language),
            error="Real OCR engine is not configured."
        )


class TesseractOCRProvider(OCRProvider):
    provider_name = "tesseract"

    def __init__(self):
        self.binary = shutil.which("tesseract")
        self.ocr_langs = os.environ.get("OCR_LANGS", "eng+chi_sim").strip() or "eng+chi_sim"
        self.min_confidence = _env_int("OCR_MIN_CONFIDENCE", 60)

    def is_available(self):
        return bool(self.binary)

    def recognize_image(self, image_path, language=""):
        normalized_language = _normalize_language(language)
        if not self.is_available():
            return OCRTextResult(
                status="ocr_unavailable",
                provider=self.provider_name,
                language=normalized_language,
                error="Tesseract executable was not found in PATH."
            )

        if not os.path.exists(image_path):
            return OCRTextResult(
                status="ocr_failed",
                provider=self.provider_name,
                language=normalized_language,
                error=f"Image file not found: {image_path}"
            )

        cmd = [
            self.binary,
            image_path,
            "stdout",
            "-l",
            self.ocr_langs,
            "--psm",
            "6",
            "tsv"
        ]
        try:
            completed = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=60
            )
        except Exception as exc:
            return OCRTextResult(
                status="ocr_failed",
                provider=self.provider_name,
                language=normalized_language,
                error=f"Tesseract execution failed: {exc}"
            )

        if completed.returncode != 0:
            return OCRTextResult(
                status="ocr_failed",
                provider=self.provider_name,
                language=normalized_language,
                error=completed.stderr.strip() or "Tesseract returned a non-zero exit code."
            )

        rows = csv.DictReader(StringIO(completed.stdout), delimiter="\t")
        words = []
        confidences = []
        blocks = []
        for row in rows:
            text = (row.get("text") or "").strip()
            if not text:
                continue
            words.append(text)
            try:
                conf = float(row.get("conf", "-1"))
            except ValueError:
                conf = -1
            if conf >= 0:
                confidences.append(conf)
            blocks.append({
                "text": text,
                "confidence": max(0, min(conf, 100)) if conf >= 0 else 0,
                "left": row.get("left"),
                "top": row.get("top"),
                "width": row.get("width"),
                "height": row.get("height")
            })

        joined = " ".join(words).strip()
        if not joined:
            return OCRTextResult(
                status="empty_result",
                provider=self.provider_name,
                language=normalized_language,
                error="OCR completed but no text was detected.",
                blocks=blocks
            )

        confidence = round(sum(confidences) / len(confidences), 2) if confidences else 50
        status = "ok"
        quality_flags = []
        if confidence < self.min_confidence:
            status = "low_confidence"
            quality_flags.append("ocr_low_confidence")

        return OCRTextResult(
            status=status,
            text=joined,
            confidence=max(0, min(confidence, 100)),
            provider=self.provider_name,
            language=normalized_language,
            blocks=blocks,
            quality_flags=quality_flags
        )


class PaddleOCRProvider(OCRProvider):
    provider_name = "paddle"

    def __init__(self, language=""):
        self._ocr = None
        self._error = ""
        self.language = _normalize_language(language)
        self.min_confidence = _env_int("OCR_MIN_CONFIDENCE", 60)
        try:
            from paddleocr import PaddleOCR
            paddle_lang = "ch" if self.language in {"zh", "bilingual", "mixed"} else "en"
            self._ocr = PaddleOCR(use_angle_cls=True, lang=paddle_lang, show_log=False)
        except Exception as exc:
            self._error = str(exc)

    def is_available(self):
        return self._ocr is not None

    def recognize_image(self, image_path, language=""):
        normalized_language = _normalize_language(language or self.language)
        if not self.is_available():
            return OCRTextResult(
                status="ocr_unavailable",
                provider=self.provider_name,
                language=normalized_language,
                error=f"PaddleOCR is not available: {self._error}"
            )
        try:
            result = self._ocr.ocr(image_path, cls=True)
        except Exception as exc:
            return OCRTextResult(
                status="ocr_failed",
                provider=self.provider_name,
                language=normalized_language,
                error=f"PaddleOCR execution failed: {exc}"
            )

        texts = []
        confidences = []
        blocks = []
        for page in result or []:
            for item in page or []:
                if len(item) >= 2 and isinstance(item[1], (list, tuple)):
                    text = str(item[1][0]).strip()
                    if text:
                        texts.append(text)
                    try:
                        conf = float(item[1][1]) * 100
                        confidences.append(conf)
                    except Exception:
                        conf = 0
                    blocks.append({
                        "text": text,
                        "confidence": max(0, min(conf, 100)),
                        "bbox": item[0] if item else None
                    })

        joined = " ".join(texts).strip()
        if not joined:
            return OCRTextResult(
                status="empty_result",
                provider=self.provider_name,
                language=normalized_language,
                error="OCR completed but no text was detected.",
                blocks=blocks
            )

        confidence = round(sum(confidences) / len(confidences), 2) if confidences else 50
        status = "ok"
        quality_flags = []
        if confidence < self.min_confidence:
            status = "low_confidence"
            quality_flags.append("ocr_low_confidence")

        return OCRTextResult(
            status=status,
            text=joined,
            confidence=max(0, min(confidence, 100)),
            provider=self.provider_name,
            language=normalized_language,
            blocks=blocks,
            quality_flags=quality_flags
        )


def get_ocr_provider(provider_name, language=""):
    provider_name = (provider_name or "none").strip().lower()
    if provider_name == "tesseract":
        return TesseractOCRProvider()
    if provider_name == "paddle":
        return PaddleOCRProvider(language=language)
    if provider_name == "mock":
        return MockOCRProvider()
    if provider_name == "auto":
        tesseract = TesseractOCRProvider()
        if tesseract.is_available():
            return tesseract
        paddle = PaddleOCRProvider(language=language)
        if paddle.is_available():
            return paddle
        return MockOCRProvider()
    return NoneOCRProvider()
