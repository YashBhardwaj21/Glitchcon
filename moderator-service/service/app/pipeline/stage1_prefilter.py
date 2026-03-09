import re
import time
from pathlib import Path
from redis.asyncio import Redis

from app.schemas.pipeline import PreFilterResult, KeywordResult
from app.schemas.profile import RulesProfileResponse
from app.schemas.i18n import LanguageContext

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
    text = re.sub(r'(?<![a-z])(?:[a-z]\s+)+[a-z](?![a-z])', lambda m: m.group(0).replace(' ', ''), text)
    # Strip dots/dashes/underscores/asterisks between any two letters: "f.u.c.k.i.n.g" → "fucking"
    text = re.sub(r'(?<=[a-z])[.\-_*](?=[a-z])', '', text)
    return text


PII_PATTERNS = {
    "phone":        re.compile(r"\b[6-9]\d{9}\b"),
    "phone_intl":   re.compile(r"\b(?:\+?91[\s-]?)?[6-9]\d{9}\b"),
    "email":        re.compile(r"[\w.-]+@[\w.-]+\.\w{2,4}"),
    "aadhaar":      re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    "pan":          re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    "upi":          re.compile(r"[\w.+-]+@(?:okicici|oksbi|okaxis|okhdfcbank|ybl|ibl|axl|paytm|apl)"),
    "api_key":      re.compile(r"(?:sk|pk|api)[_-][a-zA-Z0-9]{20,}"),
    "whatsapp":     re.compile(r"https?://(?:wa\.me|api\.whatsapp\.com)/\d+"),
    "card_number":  re.compile(r"\b\d{4}[\s-]\d{4}[\s-]\d{4}[\s-]\d{4}\b"),
}

# Racial/identity slurs → HATE_SPEECH category
HARD_EN_HATE_SPEECH = {
    "nigger", "nigga",
    "kike",
    "spic",
    "chink", "gook",
    "faggot",
    "bhangi",
}

# Severe profanity → PROFANITY category
HARD_EN_PROFANITY = {
    "motherfucker", "motherfucking", "cunt",
    "fucking", "fuckyou", "fuckoff",
    "asshole", "bastard", "bitch", "dickhead",
}

# Hindi/Hinglish slurs → PROFANITY category
HARD_HI_PROFANITY = {
    "madarchod", "bhenchod", "behenchod", "chutiya", "chutiye",
    "gaandu", "gandu", "randi", "bhosdike", "bhosdika",
    "lodu", "laude", "lavde",
}

# Hindi threat phrases → THREAT category
# Checked BEFORE profanity so "maar do sala harami" → THREAT not PROFANITY
HARD_HI_THREAT = {
    "maar do",
    "maar dalo",
    "jaan se maar",
    "khatam kar do",
    "khatam kar",
    "thok do",
    "utha lo",
    "khoon kar",
    "sar kaato",
}

# When a Hindi threat phrase targets a GROUP rather than an individual,
# it should be HATE_SPEECH not THREAT.
# These are plural/group indicators in Hinglish: "these people", "them all", etc.
GROUP_INDICATORS_HI = {
    "saale", "saalo",   # plural derogatory
    "inko", "unko",     # them (object)
    "logo", "log",      # people
    "sab ko", "sabko",  # everyone
    "inhe", "unhe",     # them
}


class ProfanityChecker:
    _lists_loaded = False
    _indic_profanity: dict[str, set[str]] = {
        "hi": set(), "ta": set(), "te": set(), "kn": set(), "ml": set()
    }

    @classmethod
    def load_lists(cls):
        if cls._lists_loaded:
            return
        lists_dir = Path(__file__).parent.parent / "i18n" / "profanity_lists"
        for lang in cls._indic_profanity.keys():
            file_path = lists_dir / f"{lang}_profanity.txt"
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    words = [line.strip().lower() for line in f
                             if line.strip() and not line.startswith("#")]
                    cls._indic_profanity[lang].update(words)
        cls._lists_loaded = True

    @classmethod
    def check(cls, text: str, lang_ctx: LanguageContext) -> tuple[bool, str | None]:
        cls.load_lists()
        text_lower = text.lower()
        normalised = normalise_for_lookup(text_lower)
        words_in_text = set(text_lower.split())

        # 1. Hindi threat phrases — checked first, takes priority
        for phrase in HARD_HI_THREAT:
            if phrase in text_lower:
                # Disambiguate: threat against a GROUP → HATE_SPEECH
                # "ye saale log maar do" targets a group, not an individual
                if words_in_text & GROUP_INDICATORS_HI:
                    return True, "hate_speech_group_threat"
                return True, "threat_hi"

        # 2. English hate speech slurs
        for word in HARD_EN_HATE_SPEECH:
            if word in normalised or word in text_lower:
                return True, "hate_speech_en"

        # 3. English profanity
        for word in HARD_EN_PROFANITY:
            if word in normalised or word in text_lower:
                return True, "profanity_en"

        # 4. Hindi profanity
        for word in HARD_HI_PROFANITY:
            if word in normalised or word in text_lower:
                return True, "profanity_hi"

        # 5. File-loaded Indic profanity lists
        lang = lang_ctx.code
        langs_to_check = []
        if lang in cls._indic_profanity:
            langs_to_check.append(lang)
        elif lang == "hi-en":
            langs_to_check.append("hi")

        for lang_code in langs_to_check:
            for word in cls._indic_profanity[lang_code]:
                if re.search(rf"\b{re.escape(word)}\b", text_lower):
                    return True, f"profanity_{lang_code}"

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
        words = set(normalise_for_lookup(text).lower().split()) | set(text.lower().split())

        lang = lang_ctx.code if lang_ctx.code in profile.supported_languages else "en"
        hard_set_key = f"keywords:{lang}:hard"
        soft_set_key = f"keywords:{lang}:soft"

        for word in words:
            if await redis.sismember(hard_set_key, word):
                return KeywordResult(decision="BLOCK", matched=word, confidence=1.0)

        soft_matches = [w for w in words if await redis.sismember(soft_set_key, w)]
        if soft_matches:
            return KeywordResult(
                decision="HINT",
                matched=soft_matches[0],
                confidence=0.5,
                hint=f"Message contains potentially toxic term: '{soft_matches[0]}'"
            )

        if lang_ctx.is_transliterated and lang_ctx.normalised_text != text:
            if "hi-en" in profile.supported_languages:
                hien_hard = "keywords:hi-en:hard"
                hien_soft = "keywords:hi-en:soft"
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

        window = profile.spam_window_s
        limit = profile.spam_limit

        spam_key = f"spam:{profile.profile_id}:{user_id}"
        now = int(time.time())
        window_start = now - window

        pipe = redis.pipeline()
        pipe.zremrangebyscore(spam_key, "-inf", window_start)
        pipe.zadd(spam_key, {str(now): now})
        pipe.zcount(spam_key, "-inf", "+inf")
        pipe.expire(spam_key, window)
        results = await pipe.execute()
        return results[2] > limit


# Maps v_type strings returned by ProfanityChecker to (category, template_key)
_VIOLATION_CATEGORY_MAP = {
    "hate_speech_en":           ("HATE_SPEECH", "hate_speech"),
    "hate_speech_group_threat": ("HATE_SPEECH", "hate_speech"),
    "threat_hi":                ("THREAT",      "threat"),
}

def _resolve_violation_category(v_type: str) -> tuple[str, str]:
    """
    Maps a violation type string to (category, template_key).
    Falls back to PROFANITY for all profanity_* types.
    """
    if v_type in _VIOLATION_CATEGORY_MAP:
        return _VIOLATION_CATEGORY_MAP[v_type]
    return ("PROFANITY", "profanity")


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

        # 1. Spam flood check
        is_spam = await SpamChecker.check(user_id, profile, redis)
        if is_spam:
            return PreFilterResult(
                blocked=True,
                stage="stage1",
                matched="spam_limit_exceeded",
                template_key="spam",
                detected_language=lang_ctx.code,
                category="SPAM"
            )

        # 2. PII check
        has_pii, pii_type = PIIChecker.check(text)
        if has_pii:
            return PreFilterResult(
                blocked=True,
                stage="stage1",
                matched=pii_type,
                template_key="pii",
                detected_language=lang_ctx.code,
                category="PII"
            )

        # 3. Profanity / Hate Speech / Threat check
        has_violation, v_type = ProfanityChecker.check(lang_ctx.normalised_text, lang_ctx)
        if has_violation:
            category, template_key = _resolve_violation_category(v_type)
            return PreFilterResult(
                blocked=True,
                stage="stage1",
                matched=v_type,
                template_key=template_key,
                detected_language=lang_ctx.code,
                category=category
            )

        # 4. Keyword check (Redis TF-IDF SETs)
        keyword_result = await KeywordChecker.check(lang_ctx.normalised_text, profile, lang_ctx, redis)

        if keyword_result.decision == "BLOCK":
            return PreFilterResult(
                blocked=True,
                stage="stage1",
                matched=keyword_result.matched,
                template_key="keyword",
                detected_language=lang_ctx.code,
                category="HATE_SPEECH"
            )
        elif keyword_result.decision == "HINT":
            return PreFilterResult(
                blocked=False,
                stage="stage1",
                matched=keyword_result.matched,
                template_key="keyword",
                detected_language=lang_ctx.code,
                keyword_hint=keyword_result.hint,
                category="NONE"
            )

        # Passed all fast checks — proceed to FAISS/LLM
        return PreFilterResult(
            blocked=False,
            stage="stage1",
            detected_language=lang_ctx.code,
            category="NONE"
        )