import time

from app.schemas.i18n import LanguageContext
from app.i18n.detector import LanguageDetector
from app.i18n.normaliser import IndicNormaliser

class Stage0Language:
    """
    Stage 0 — Language Detection & Normalisation
    Runs before all other moderation stages.
    Takes < 3 ms.
    """
    
    @staticmethod
    def process(text: str) -> tuple[LanguageContext, int]:
        """
        Detects language, applies Hinglish heuristics, normalises transliterated
        text, and returns the full LanguageContext and the latency of this stage.
        """
        start_time = time.perf_counter()
        
        # 1. Detect language
        ctx = LanguageDetector.detect(text)
        
        # 2. Normalise if transliterated Indic text
        if ctx.code in ["hi", "ta", "te", "kn", "ml"] and not ctx.is_transliterated:
            ctx = IndicNormaliser.normalise(text, ctx)
            
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        
        return ctx, latency_ms
