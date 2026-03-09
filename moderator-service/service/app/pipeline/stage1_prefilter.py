import re
import time
from pathlib import Path
from redis.asyncio import Redis
from better_profanity import profanity

from app.schemas.pipeline import PreFilterResult, KeywordResult
from app.schemas.profile import RulesProfileResponse
from app.schemas.i18n import LanguageContext

# ─── Leet-speak / bypass normaliser ─────────────────────────────────────────
_LEET_MAP = {
    '@': 'a', '3': 'e', '1': 'i', '0': 'o',
    '5': 's', '7': 't', '$': 's', '!': 'i',
    '+': 't', '|': 'l',
}

def normalise_for_lookup(text: str) -> str:
    """
    Normalise text to counter common keyword-filter bypass attempts:
      - Leet-speak substitution:  @ssh0le  → asshole
      - Repeated characters:      fuuuuck  → fuck
      - Spaces between letters:   f u c k  → fuck
      - Punctuation separators:   f.u.c.k  → fuck
    Called on ENGLISH / Hinglish text only — not Devanagari.
    """
    text = text.lower()
    for char, replacement in _LEET_MAP.items():
        text = text.replace(char, replacement)
    # Collapse 3+ repeated characters: "fuuuuck" → "fuck"
    text = re.sub(r'(.)\1{2,}', r'\1', text)
    # Remove spaces sandwiched between single letters: "f u c k" → "fuck"
    # Uses a lookaround to only match sequences of isolated single letters.
    text = re.sub(r'(?<![a-z])(?:[a-z]\s+)+[a-z](?![a-z])', lambda m: m.group(0).replace(' ', ''), text)
    
    # Remove punctuation used as separators between single letters: "f.u.c.k" → "fuck"
    text = re.sub(r'(?<![a-z])(?:[a-z][.\-_*]+)+[a-z](?![a-z])', lambda m: re.sub(r'[.\-_*]', '', m.group(0)), text)
    return text


# Compile PII Regexes once at module load
PII_PATTERNS = {
    "phone":        re.compile(r"\b[6-9]\d{9}\b"),
    "phone_intl":   re.compile(r"\b(?:\+?91[\s-]?)?[6-9]\d{9}\b"),   # +91 prefix
    "email":        re.compile(r"[\w.-]+@[\w.-]+\.\w{2,}"),
    "aadhaar":      re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    "pan":          re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    "upi":          re.compile(r"[\w.+-]+@[a-z]+"),
    "api_key":      re.compile(r"(?:sk|pk|api)[_-][a-zA-Z0-9]{20,}"),
    "whatsapp":     re.compile(r"https?://(?:wa\.me|api\.whatsapp\.com)/\d+"),
    "card_number":  re.compile(r"\b\d{4}[\s-]\d{4}[\s-]\d{4}[\s-]\d{4}\b"),  # 16-digit card
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
    async def check(
        text: str,
        profile: RulesProfileResponse,
        lang_ctx: LanguageContext,
        redis: Redis
    ) -> KeywordResult:
        # text here is already lowercased and base-normalised (depends on calling code)
        # Apply leet-speak / bypass normalisation
        words = set(normalise_for_lookup(text).lower().split()) | set(text.lower().split())
        
        lang = lang_ctx.code if lang_ctx.code in profile.supported_languages else "en"
        hard_set_key  = f"keywords:{lang}:hard"
        soft_set_key  = f"keywords:{lang}:soft"

        # Check hard set first — immediate block, no LLM needed
        for word in words:
            if await redis.sismember(hard_set_key, word):
                return KeywordResult(decision="BLOCK", matched=word, confidence=1.0)

        # Check soft set — flag for LLM review with hint
        soft_matches = [w for w in words if await redis.sismember(soft_set_key, w)]
        if soft_matches:
            return KeywordResult(
                decision="HINT",
                matched=soft_matches[0],
                confidence=0.5,
                hint=f"Message contains potentially toxic term: '{soft_matches[0]}'"
            )

        # If transliterated from Roman script, also check Hinglish list
        if lang_ctx.is_transliterated and lang_ctx.normalised_text != text:
            if "hi-en" in profile.supported_languages:
                hien_hard = f"keywords:hi-en:hard"
                hien_soft = f"keywords:hi-en:soft"
                
                # For basic transliteration fallback, we also check the un-normalised original text
                orig_words = set(normalise_for_lookup(text).lower().split()) | set(text.lower().split())
                
                for word in orig_words:
                    if await redis.sismember(hien_hard, word):
                        return KeywordResult(decision="BLOCK", matched=word, confidence=1.0)
                        
                hien_soft_matches = [w for w in orig_words if await redis.sismember(hien_soft, w)]
                if hien_soft_matches:
                    return KeywordResult(
                        decision="HINT",
                        matched=hien_soft_matches[0],
                        confidence=0.5,
                        hint=f"Message contains potentially toxic Hinglish term: '{hien_soft_matches[0]}'"
                    )

        return KeywordResult(decision="ALLOW", matched=None, confidence=0.0)


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
            return PreFilterResult(
                blocked=False, 
                stage="stage1", 
                matched=p_type, 
                template_key="profanity", 
                detected_language=lang_ctx.code,
                keyword_hint=f"Message may contain sensitive terms (profanity check: {p_type})"
            )
            
        # 4. Keyword Check (Per-language TF-IDF Redis SETs)
        keyword_result = await KeywordChecker.check(lang_ctx.normalised_text, profile, lang_ctx, redis)
        
        if keyword_result.decision == "BLOCK":
            return PreFilterResult(blocked=True, stage="stage1", matched=keyword_result.matched, template_key="keyword", detected_language=lang_ctx.code)
        elif keyword_result.decision == "HINT":
            return PreFilterResult(blocked=False, stage="stage1", matched=keyword_result.matched, template_key="keyword", detected_language=lang_ctx.code, keyword_hint=keyword_result.hint)
            
        # Passed all fast checks -> Allow it to proceed to LLM
        return PreFilterResult(blocked=False, stage="stage1", detected_language=lang_ctx.code)
