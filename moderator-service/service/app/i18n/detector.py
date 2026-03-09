import re
from langdetect import detect_langs, DetectorFactory

from app.schemas.i18n import LanguageContext

# Enforce consistent results for the same string
DetectorFactory.seed = 0

SUPPORTED_LANGUAGES = {"en", "hi", "ta", "te", "kn", "ml"}

# Regex for detecting Devanagari characters
DEVANAGARI_RE = re.compile(r'[\u0900-\u097F]')

class LanguageDetector:
    
    @staticmethod
    def detect(text: str) -> LanguageContext:
        """
        Detects the language of the provided text.
        Handles Hinglish heuristics (Devanagari characters + English detection -> hi-en).
        Returns 'en' if confidence is below 0.70.
        """
        if not text or not text.strip():
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
            
            # Map macro-languages if necessary (langdetect sometimes returns 'ur' or 'mr' for Hindi text)
            if lang_code in ("ur", "mr", "ne"):
                lang_code = "hi"
            if lang_code not in SUPPORTED_LANGUAGES:
                # If unsupported, fallback to English but keep the confidence of the unsupported lang
                lang_code = "en"
                
            # Hinglish heuristic: 
            # If langdetect says 'en' but we see Devanagari chars, it's code-mixed Hinglish
            if lang_code == "en" and DEVANAGARI_RE.search(text):
                lang_code = "hi-en"
                # Artificially boost confidence since we have strong regex evidence
                confidence = max(confidence, 0.85)
                
            # Low confidence fallback
            if confidence < 0.70:
                # In a real app we would log this low-confidence detection
                # logger.info(f"Low confidence detection ({lang_code}: {confidence:.2f}) -> falling back to 'en'")
                lang_code = "en"
                confidence = 1.0 # Reset to 1.0 since we are forcefully falling back to English
                
            return LanguageContext(
                code=lang_code,
                confidence=confidence,
                is_transliterated=False,
                normalised_text=text
            )
            
        except Exception:
            # Fallback on any langdetect error (e.g., text with no letters)
            return LanguageContext(
                code="en",
                confidence=1.0,
                is_transliterated=False,
                normalised_text=text
            )
