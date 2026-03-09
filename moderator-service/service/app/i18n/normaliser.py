from indic_transliteration import sanscript
from app.schemas.i18n import LanguageContext

# Mapping of detected lang code to native indic_transliteration script constant
LANG_TO_SCRIPT = {
    "hi": sanscript.DEVANAGARI,
    "ta": sanscript.TAMIL,
    "te": sanscript.TELUGU,
    "kn": sanscript.KANNADA,
    "ml": sanscript.MALAYALAM,
}

class IndicNormaliser:
    
    @staticmethod
    def is_romanised(text: str) -> bool:
        """
        Naive check: if text is mostly within ASCII range, it's likely romanised.
        Since Indic scripts use higher unicode planes, text without them is Roman.
        """
        # Remove whitespace & punctuation for check
        cleaned = "".join(c for c in text if c.isalnum())
        if not cleaned:
            return False
            
        # If all characters are ASCII (e.g., english letters or numbers)
        return all(ord(c) < 128 for c in cleaned)

    @staticmethod
    def normalise(text: str, ctx: LanguageContext) -> LanguageContext:
        """
        Takes a LanguageContext returned by LanguageDetector.
        If the language is an Indic macro-lang AND the text is Romanised,
        it transliterates the text to the native script so keyword lists will match.
        """
        lang = ctx.code
        
        # We only normalise known Indic languages, not english or code-mixed hinglish (hi-en)
        if lang not in LANG_TO_SCRIPT:
            return ctx
            
        # Only transliterate if it looks like Roman script
        if not IndicNormaliser.is_romanised(text):
            return ctx
            
        try:
            native_script = LANG_TO_SCRIPT[lang]
            # Assumes ITRANS encoding for typed input (e.g., 'nahi karna' -> Devanagari)
            normalised = sanscript.transliterate(text, sanscript.ITRANS, native_script)
            
            # Return updated context
            return LanguageContext(
                code=ctx.code,
                confidence=ctx.confidence,
                is_transliterated=True,
                normalised_text=normalised
            )
        except Exception:
            # On mapping errors, return original context
            return ctx
