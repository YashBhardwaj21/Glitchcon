import re
import time
from pathlib import Path
from redis.asyncio import Redis
from better_profanity import profanity

from app.schemas.pipeline import PreFilterResult
from app.schemas.profile import RulesProfileResponse
from app.schemas.i18n import LanguageContext

# Compile PII Regexes once at module load
PII_PATTERNS = {
    "phone": re.compile(r"\b[6-9]\d{9}\b"),
    "email": re.compile(r"[\w.-]+@[\w.-]+\.\w{2,}"),
    "aadhaar": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    "pan": re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    "upi": re.compile(r"[\w.+-]+@[a-z]+"),
    "api_key": re.compile(r"(?:sk|pk|api)[_-][a-zA-Z0-9]{20,}")
}

class ProfanityChecker:
    _lists_loaded = False
    _indic_profanity: dict[str, set[str]] = {
        "hi": set(), "ta": set(), "te": set(), "kn": set(), "ml": set()
    }
    
    @classmethod
    def load_lists(cls):
        if cls._lists_loaded: return
        
        # Load English better_profanity
        profanity.load_censor_words()
        
        # Load Indic lists from files
        lists_dir = Path(__file__).parent.parent / "i18n" / "profanity_lists"
        for lang in cls._indic_profanity.keys():
            file_path = lists_dir / f"{lang}_profanity.txt"
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    # Ignore comments and empty lines
                    words = [line.strip().lower() for line in f 
                             if line.strip() and not line.startswith("#")]
                    cls._indic_profanity[lang].update(words)
                    
        cls._lists_loaded = True

    @classmethod
    def check(cls, text: str, lang_ctx: LanguageContext) -> tuple[bool, str | None]:
        cls.load_lists()
        
        text_lower = text.lower()
        
        # 1. Check English (always check unless purely native indic script without ASCII)
        if profanity.contains_profanity(text_lower):
            return True, "profanity_en"
            
        # 2. Check detected Indic language
        lang = lang_ctx.code
        
        langs_to_check = []
        if lang in cls._indic_profanity:
            langs_to_check.append(lang)
        elif lang == "hi-en":
            # Code-mixed Hinglish: Check Hindi romanised abuse words
            langs_to_check.append("hi")
            
        for l in langs_to_check:
            for word in cls._indic_profanity[l]:
                # Simple substring match for basic Indic profanity
                # A more robust system would tokenize words properly
                if word in text_lower:
                    return True, f"profanity_{l}"
                    
        return False, None


class PIIChecker:
    @staticmethod
    def check(text: str) -> tuple[bool, str | None]:
        for pii_type, pattern in PII_PATTERNS.items():
            if pattern.search(text):
                return True, pii_type
        return False, None


class KeywordChecker:
    @staticmethod
    async def check(text: str, profile: RulesProfileResponse, lang_ctx: LanguageContext, redis: Redis) -> tuple[bool, str | None]:
        text_lower = text.lower()
        words = text_lower.split()
        if not words:
            return False, None
            
        lang = lang_ctx.code if lang_ctx.code in profile.supported_languages else "en"
        set_key = f"banned:{profile.profile_id}:{lang}"
        
        # We can optimize by checking the exact words in the redis set, 
        # or scanning the redis set to check if they exist in the text.
        # For small banned lists (hundreds of words), smembers and local matching is fast.
        
        banned_words = await redis.smembers(set_key)
        
        for banned_word in banned_words:
            # simple substring search for keywords (e.g. "dotnet" matches "I need dotnet help")
            if banned_word in text_lower:
                return True, banned_word
                
        # If the text was transliterated from roman script, check the original text too
        # Example: if "nahi karna" → "नहीं करना" didn't match native Hindi list, 
        # check if "nahi karna" matches the Hinglish list.
        if lang_ctx.is_transliterated and lang_ctx.normalised_text != text:
            # Check using Hinglish keywords if hi-en is supported
            if "hi-en" in profile.supported_languages:
                hien_set_key = f"banned:{profile.profile_id}:hi-en"
                hien_banned = await redis.smembers(hien_set_key)
                # Use original un-normalised text
                orig_lower = text.lower()
                for banned_word in hien_banned:
                    if banned_word in orig_lower:
                        return True, banned_word
                        
        return False, None


class SpamChecker:
    @staticmethod
    async def check(user_id: str | None, profile: RulesProfileResponse, redis: Redis) -> bool:
        if not user_id:
            return False
            
        # Sliding window rate limit for spam flood detection
        window = profile.spam_window_s
        limit = profile.spam_limit
        
        now = int(time.time())
        window_start = now - window
        
        spam_key = f"spam:{profile.profile_id}:{user_id}"
        
        pipe = redis.pipeline()
        pipe.zremrangebyscore(spam_key, "-inf", window_start) # Remove old
        pipe.zadd(spam_key, {str(now): now})                  # Add current
        pipe.zcount(spam_key, "-inf", "+inf")                 # Count remaining
        pipe.expire(spam_key, window)                         # Set TTL
        
        results = await pipe.execute()
        count = results[2]
        
        return count > limit


class Stage1Prefilter:
    """
    Stage 1 — Fast Pre-filter (Multilingual)
    Executes Spam, PII, Profanity, and Keyword checks.
    Takes < 10 ms. Blocks ~70% of violations without LLM calls.
    """
    
    @staticmethod
    async def process(
        text: str, 
        profile: RulesProfileResponse,
        lang_ctx: LanguageContext,
        user_id: str | None,
        redis: Redis
    ) -> PreFilterResult:
        
        # 1. Spam flood check (Language-agnostic)
        is_spam = await SpamChecker.check(user_id, profile, redis)
        if is_spam:
            return PreFilterResult(blocked=True, stage="stage1", matched="spam_limit_exceeded", template_key="spam", detected_language=lang_ctx.code)
            
        # 2. PII Check (Language-agnostic)
        has_pii, pii_type = PIIChecker.check(text)
        if has_pii:
            return PreFilterResult(blocked=True, stage="stage1", matched=pii_type, template_key="pii", detected_language=lang_ctx.code)
            
        # 3. Profanity Check (Multilingual)
        has_profanity, p_type = ProfanityChecker.check(lang_ctx.normalised_text, lang_ctx)
        if has_profanity:
            return PreFilterResult(blocked=True, stage="stage1", matched=p_type, template_key="profanity", detected_language=lang_ctx.code)
            
        # 4. Keyword Check (Per-language Redis SETs)
        has_keyword, k_word = await KeywordChecker.check(lang_ctx.normalised_text, profile, lang_ctx, redis)
        if has_keyword:
            return PreFilterResult(blocked=True, stage="stage1", matched=k_word, template_key="keyword", detected_language=lang_ctx.code)
            
        # Passed all fast checks -> Allow it to proceed to LLM
        return PreFilterResult(blocked=False, stage="stage1", detected_language=lang_ctx.code)
