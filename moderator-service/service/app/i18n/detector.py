import re
from langdetect import detect_langs, DetectorFactory

from app.schemas.i18n import LanguageContext

# Enforce consistent results for the same string
DetectorFactory.seed = 0

SUPPORTED_LANGUAGES = {"en", "hi", "ta", "te", "kn", "ml"}

# Regex for detecting Devanagari characters
DEVANAGARI_RE = re.compile(r'[\u0900-\u097F]')

# Matches text that has no actual latin/devanagari letters — pure emoji, symbols, numbers
NO_LETTERS_RE = re.compile(r'^[^\w\u0900-\u097F]+$')

class LanguageDetector:

    @staticmethod
    def detect(text: str) -> LanguageContext:
        """
        Detects the language of the provided text.
        Handles Hinglish heuristics (Devanagari characters + English detection -> hi-en).
        Returns 'en' if confidence is below 0.70.
        Gracefully handles pure emoji, symbols, and unsupported unicode.
        """
        if not text or not text.strip():
            return LanguageContext(
                code="en",
                confidence=1.0,
                is_transliterated=False,
                normalised_text=text or ""
            )

        # Pre-check: if text has no actual letters (pure emoji / symbols / numbers)
        # langdetect will crash or return garbage — return "en" immediately
        stripped = text.strip()
        if NO_LETTERS_RE.match(stripped):
            return LanguageContext(
                code="en",
                confidence=1.0,
                is_transliterated=False,
                normalised_text=text
            )

        # Pre-check: if text is extremely short (< 3 chars after stripping non-ascii)
        # langdetect is unreliable on very short strings
        ascii_only = stripped.encode("ascii", errors="ignore").decode("ascii").strip()
        if len(ascii_only) < 3 and not DEVANAGARI_RE.search(stripped):
            return LanguageContext(
                code="en",
                confidence=1.0,
                is_transliterated=False,
                normalised_text=text
            )

        try:
            detections = detect_langs(text)
            if not detections:
                raise ValueError("No language detected")

            best_match = detections[0]
            lang_code = best_match.lang
            confidence = best_match.prob

            # Map macro-languages if necessary
            if lang_code in ("ur", "mr", "ne"):
                lang_code = "hi"
            if lang_code not in SUPPORTED_LANGUAGES:
                lang_code = "en"

            # Hinglish heuristic:
            # If langdetect says 'en' but we see Devanagari chars, it's code-mixed
            if lang_code == "en" and DEVANAGARI_RE.search(text):
                lang_code = "hi-en"
                confidence = max(confidence, 0.85)

            # Low confidence fallback
            if confidence < 0.70:
                lang_code = "en"
                confidence = 1.0

            return LanguageContext(
                code=lang_code,
                confidence=confidence,
                is_transliterated=False,
                normalised_text=text
            )

        except Exception:
            # Fallback on any langdetect error (pure emoji, no-letter text, etc.)
            return LanguageContext(
                code="en",
                confidence=1.0,
                is_transliterated=False,
                normalised_text=text
            )
            