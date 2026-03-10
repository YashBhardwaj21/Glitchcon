from pydantic import BaseModel

class LanguageContext(BaseModel):
    code: str                  # Detected language code (e.g., "en", "hi", "hi-en", "ta")
    confidence: float          # Detection confidence score (0.0 to 1.0)
    is_transliterated: bool    # True if the text was Roman Indic and we transliterated it
    normalised_text: str       # Original text if not transliterated, else the native script version
