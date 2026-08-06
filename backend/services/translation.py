"""Optional small-LLM term translation providers.

The default provider is ``none``: the module stays importable and every call
degrades to a clear ``translation_unavailable`` status without raising. The
``ollama`` provider talks to a local Ollama server running a translation
specialist model (e.g. TranslateGemma) over its native HTTP API. Translation
is always provenance-tagged and never blocks the calling pipeline.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request


TRANSLATION_PROVIDER_ENV = "TRANSLATION_PROVIDER"
OLLAMA_BASE_URL_ENV = "OLLAMA_BASE_URL"
OLLAMA_MODEL_ENV = "OLLAMA_MODEL"
TRANSLATION_TIMEOUT_ENV = "TRANSLATION_TIMEOUT_SECONDS"
PROVIDER_NONE = "none"
PROVIDER_OLLAMA = "ollama"
PROVIDER_AUTO = "auto"
TRANSLATION_PROVIDER_CHAIN_ENV = "TRANSLATION_PROVIDER_CHAIN"
DEFAULT_PROVIDER_CHAIN = "ollama"
ROUTABLE_PROVIDERS = {PROVIDER_OLLAMA}
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "translategemma:12b"
DEFAULT_TIMEOUT_SECONDS = 30

SYSTEM_PROMPT = (
    "You are a technical translation engine for bilingual course materials. "
    "Translate the given English technical term into Simplified Chinese. "
    "Reply with the Chinese translation only: no explanations, no pinyin, "
    "no alternative translations, no punctuation at the end."
)


def _env_int(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def normalize_provider_name(value):
    provider = (value or PROVIDER_NONE).strip().lower()
    if provider in {"", "none", "off", "disabled"}:
        return PROVIDER_NONE
    return provider


def clean_translated_term(text):
    """Reduce a raw model response to a single candidate term."""
    first_line = str(text or "").strip().splitlines()[0] if str(text or "").strip() else ""
    cleaned = first_line.strip().strip('"\'`“”‘’。.;；,，')
    cleaned = re.sub(r"[。.;；,，]+$", "", cleaned).strip().strip('"\'`“”‘’')
    if not cleaned or len(cleaned) > 60:
        return ""
    return cleaned


class TranslationProvider:
    provider_name = "none"

    def is_available(self):
        return False

    def translate_term(self, english_term, context_sentence=""):
        return {
            "status": "translation_unavailable",
            "chinese_term": "",
            "provider": self.provider_name,
            "model": "",
            "error": "No translation provider is configured.",
        }


class NoneTranslationProvider(TranslationProvider):
    provider_name = PROVIDER_NONE


class OllamaTranslationProvider(TranslationProvider):
    provider_name = PROVIDER_OLLAMA

    def __init__(self, base_url=None, model=None):
        self.base_url = (base_url or os.environ.get(OLLAMA_BASE_URL_ENV, DEFAULT_OLLAMA_BASE_URL)).rstrip("/")
        self.model = (model or os.environ.get(OLLAMA_MODEL_ENV, DEFAULT_OLLAMA_MODEL)).strip()
        self.timeout_seconds = max(3, min(_env_int(TRANSLATION_TIMEOUT_ENV, DEFAULT_TIMEOUT_SECONDS), 120))

    def _urlopen_json(self, request, timeout):
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def is_available(self):
        request = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
        try:
            payload = self._urlopen_json(request, timeout=min(3, self.timeout_seconds))
        except (urllib.error.URLError, OSError, ValueError):
            return False
        models = {str(item.get("name", "")) for item in payload.get("models", []) or []}
        if not models:
            return False
        if self.model in models:
            return True
        # Allow tags without an explicit ":latest" suffix mismatch.
        return any(name.split(":")[0] == self.model.split(":")[0] for name in models)

    def translate_term(self, english_term, context_sentence=""):
        term = str(english_term or "").strip()
        if not term:
            return {
                "status": "translation_failed",
                "chinese_term": "",
                "provider": self.provider_name,
                "model": self.model,
                "error": "Empty English term.",
            }

        if not self.is_available():
            return {
                "status": "translation_unavailable",
                "chinese_term": "",
                "provider": self.provider_name,
                "model": self.model,
                "error": f"Ollama server or model '{self.model}' is not available at {self.base_url}.",
            }

        user_content = term
        context = str(context_sentence or "").strip()
        if context:
            user_content = f"{term}\n\nContext sentence (for disambiguation only): {context[:500]}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "options": {"temperature": 0},
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            raw = self._urlopen_json(request, timeout=self.timeout_seconds)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return {
                "status": "translation_failed",
                "chinese_term": "",
                "provider": self.provider_name,
                "model": self.model,
                "error": f"Ollama translation request failed: {exc}",
            }

        chinese_term = clean_translated_term((raw.get("message") or {}).get("content", ""))
        if not chinese_term:
            return {
                "status": "translation_failed",
                "chinese_term": "",
                "provider": self.provider_name,
                "model": self.model,
                "error": "Ollama returned an empty or unusable translation.",
            }

        return {
            "status": "ok",
            "chinese_term": chinese_term,
            "provider": self.provider_name,
            "model": self.model,
            "error": "",
        }


def get_translation_provider(name=None):
    provider = normalize_provider_name(name or os.environ.get(TRANSLATION_PROVIDER_ENV, PROVIDER_NONE))
    if provider == PROVIDER_OLLAMA:
        return OllamaTranslationProvider()
    return NoneTranslationProvider()


def parse_provider_chain(value):
    """Parse an ordered provider chain, dropping blanks and unknown names."""
    chain = []
    for item in str(value or "").split(","):
        provider = normalize_provider_name(item)
        if provider in ROUTABLE_PROVIDERS and provider not in chain:
            chain.append(provider)
    return chain


def _translate_term_single(english_term, context_sentence, requested):
    try:
        return get_translation_provider(requested).translate_term(english_term, context_sentence)
    except Exception as exc:  # defensive: translation must never break parsing/alignment
        return {
            "status": "translation_failed",
            "chinese_term": "",
            "provider": requested,
            "model": "",
            "error": f"Translation provider raised unexpectedly: {exc}",
        }


def _translate_term_auto(english_term, context_sentence):
    chain = parse_provider_chain(os.environ.get(TRANSLATION_PROVIDER_CHAIN_ENV, DEFAULT_PROVIDER_CHAIN))
    if not chain:
        result = NoneTranslationProvider().translate_term(english_term, context_sentence)
        result["error"] = "Translation provider chain is empty."
        result["attempted"] = []
        return result

    attempted = []
    errors = []
    for name in chain:
        attempted.append(name)
        result = _translate_term_single(english_term, context_sentence, name)
        if result.get("status") == "ok" and result.get("chinese_term"):
            result["attempted"] = attempted
            return result
        errors.append(f"{name}: {result.get('error') or result.get('status')}")

    return {
        "status": "translation_unavailable",
        "chinese_term": "",
        "provider": PROVIDER_AUTO,
        "model": "",
        "error": "; ".join(errors) or "No translation provider in the chain succeeded.",
        "attempted": attempted,
    }


def translate_term(english_term, context_sentence="", provider=None):
    """Translate one English term, degrading gracefully.

    Never raises: an unconfigured, unknown, or unreachable provider yields
    ``translation_unavailable`` so callers can fall back to their local
    deterministic candidate. With ``provider="auto"`` the providers listed in
    ``TRANSLATION_PROVIDER_CHAIN`` are tried in order and the first successful
    translation wins; the result records every attempted provider.
    """
    requested = normalize_provider_name(
        provider if provider is not None else os.environ.get(TRANSLATION_PROVIDER_ENV, PROVIDER_NONE)
    )
    if requested == PROVIDER_AUTO:
        return _translate_term_auto(english_term, context_sentence)
    if requested not in {PROVIDER_NONE, PROVIDER_OLLAMA}:
        result = NoneTranslationProvider().translate_term(english_term, context_sentence)
        result["error"] = f"Unknown translation provider: {requested}."
        return result
    return _translate_term_single(english_term, context_sentence, requested)
