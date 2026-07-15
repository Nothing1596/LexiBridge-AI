import os
import re


FORMULA_SYMBOLS = (
    "∫", "∑", "√", "∞", "≤", "≥", "≠", "≈", "θ", "λ", "μ", "σ", "ω",
    "π", "α", "β", "γ", "Δ", "∂", "^", "_", "=", "+", "-", "/", "(", ")",
    "[", "]"
)

FORMULA_WORDS = {
    "frac", "sqrt", "int", "sum", "lim", "sin", "cos", "tan", "log", "ln",
    "exp", "theta", "lambda", "omega", "alpha", "beta", "gamma", "sigma",
    "pi", "mu", "delta"
}


def contains_formula_text(text):
    text = str(text or "")
    if any(symbol in text for symbol in FORMULA_SYMBOLS):
        return True
    tokens = re.findall(r"[A-Za-z]+", text.lower())
    return any(token in FORMULA_WORDS for token in tokens)


def looks_like_formula_image(image_path, ocr_text=""):
    """
    Lightweight formula-region heuristic.
    It intentionally avoids claiming formula OCR success; it only decides whether
    a region should be handed to a formula OCR provider or recorded as needing one.
    """
    if contains_formula_text(ocr_text):
        return True

    mode = os.environ.get("FORMULA_DETECTION_MODE", "heuristic").strip().lower()
    if mode == "off":
        return False

    basename = os.path.basename(str(image_path or "")).lower()
    if any(marker in basename for marker in ("formula", "equation", "math")):
        return True

    # In absence of CV dependencies, use file-size and OCR emptiness as a weak
    # signal only for explicit formula-ish filenames. Empty OCR alone is too broad.
    return False
