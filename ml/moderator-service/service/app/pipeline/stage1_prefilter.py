import re
import time
import unicodedata
import logging
from pathlib import Path
from typing import Dict, Pattern, Set, Optional, Tuple
from redis.asyncio import Redis

from app.schemas.pipeline import PreFilterResult, KeywordResult
from app.schemas.profile import RulesProfileResponse
from app.schemas.i18n import LanguageContext

log = logging.getLogger(__name__)
if not log.handlers:
    # simple default handler; your app may configure logging differently
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(handler)
log.setLevel(logging.INFO)

# -------------------------
# Configuration / caches
# -------------------------
_WORDLIST_DIR = Path(__file__).parent.parent / "i18n" / "profanity_lists"
_PATTERN_CACHE: Dict[str, Pattern] = {}
_WORDLIST_CACHE: Dict[str, Dict[str, Set[str]]] = {}  # keyed by lang code

# small normalization maps (conservative)
_LEET_MAP = {'@': 'a', '3': 'e', '1': 'i', '0': 'o', '5': 's', '7': 't', '$': 's', '!': 'i', '+': 't', '|': 'l',
             '9': 'g', '4': 'a', '8': 'b', '6': 'b'}
_HOMOGLYPH_MAP = {'\u0456': 'i', '\u0435': 'e', '\u0430': 'a', '\u043E': 'o', '\u0441': 'c', '\u0440': 'p',
                  '\u043A': 'k', '\u0445': 'x', '\u0443': 'y', '\u043C': 'm', '\u0442': 't', '\u043D': 'n', '\u0432': 'v'}

# zero-width/invisible characters class
_ZERO_WIDTH_CHARS = ''.join(['\u200B', '\u200C', '\u200D', '\u200E', '\u200F', '\u2060', '\uFEFF'])

# PII regexes (unchanged)
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

# Map v_type strings to category/template
_VIOLATION_CATEGORY_MAP = {
    "hate_speech_en":           ("HATE_SPEECH", "hate_speech"),
    "hate_speech_group_threat": ("HATE_SPEECH", "hate_speech"),
    "threat_hi":                ("THREAT",      "threat"),
}

def _resolve_violation_category(v_type: str) -> tuple[str, str]:
    if v_type in _VIOLATION_CATEGORY_MAP:
        return _VIOLATION_CATEGORY_MAP[v_type]
    # default for other v_types (e.g. profanity_hi, profanity_en, threat)
    if v_type and v_type.startswith("profanity"):
        return ("PROFANITY", "profanity")
    if v_type and v_type.startswith("threat"):
        return ("THREAT", "threat")
    return ("PROFANITY", "profanity")


# -------------------------
# Normalization utilities
# -------------------------
def normalise_for_lookup(text: str) -> str:
    """
    Normalize text for reliable lookup:
     - unicode NFKC
     - lowercasing
     - remove zero-width / invisible chars
     - apply small homoglyph and leet mappings
     - strip separators between letters (b*tch -> bitch, f.u.c.k -> fuck)
     - collapse repeated chars (fuuuuck -> fuuck)
     - collapse spaced letters and short-fragment obfuscations ("b a s t a r d", "sh it")
    """
    if not text:
        return text

    text = unicodedata.normalize("NFKC", text)
    text = text.lower()

    # remove zero-width/invisible characters
    if any(c in text for c in _ZERO_WIDTH_CHARS):
        text = re.sub(f"[{re.escape(_ZERO_WIDTH_CHARS)}]", "", text)

    # homoglyphs
    for src, dst in _HOMOGLYPH_MAP.items():
        if src in text:
            text = text.replace(src, dst)

    # small leet map pass
    for k, v in _LEET_MAP.items():
        if k in text:
            text = text.replace(k, v)

    # remove punctuation sequences between word characters: b*tch, f.u.c.k
    text = re.sub(r'(?<=\w)[^\w\s]+(?=\w)', '', text)

    # collapse long runs of a char (>=3) to two (fuuuuck -> fuuck)
    text = re.sub(r'(.)\1{2,}', r'\1\1', text)

    # collapse spaced single-letter sequences: "f u c k" -> "fuck"
    text = re.sub(r'(?<![a-zA-Z])(?:[a-zA-Z]\s+){1,}[a-zA-Z](?![a-zA-Z])',
                  lambda m: m.group(0).replace(' ', ''), text)

    # collapse short multi-fragment obfuscations: "sh it", "bas tard", "b a s t a r d"
    # We conservatively transform sequences of letters separated by spaces/punct where the collapsed form length >=3 and <= 25
    def _collapse_fragments(m):
        s = m.group(0)
        collapsed = re.sub(r'[\s\W_]+', '', s)
        if 3 <= len(collapsed) <= 25:
            return collapsed
        return s

    # match words that contain at least two letter groups separated by punctuation/spaces
    text = re.sub(r'\b(?:[a-zA-Z][\s\W_]{0,6}){2,}\b', _collapse_fragments, text)

    # normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# -------------------------
# Wordlist loading (file-backed)
# -------------------------
def _sanitize_word(w: str) -> Optional[str]:
    """
    Apply simple sanitization rules for words loaded from files:
      - strip, lowercase
      - must be alpha or contain only allowed chars (letters, hyphen, apostrophe)
      - exclude tokens with digits
      - length >= 3 (conservative)
    """
    if not w:
        return None
    w = w.strip().lower()
    if not w or w.startswith("#"):
        return None
    # skip entries containing digits (likely noise)
    if re.search(r'\d', w):
        return None
    # allow letters, hyphen and apostrophe
    if not re.match(r"^[a-zA-Z'\-]+$", w):
        return None
    if len(w) < 3:
        return None
    return w


def _load_wordlists(lang: str) -> Dict[str, Set[str]]:
    """
    Load wordlists for a language from _WORDLIST_DIR.
    Returns a dict: {'profanity', 'hate', 'threat', 'combined', 'group_indicators'} - sets of lowercase terms.
    Caches results in _WORDLIST_CACHE.
    """
    if lang in _WORDLIST_CACHE:
        return _WORDLIST_CACHE[lang]

    data = {"profanity": set(), "hate": set(), "threat": set(), "combined": set(), "group_indicators": set()}

    try:
        if _WORDLIST_DIR.exists():
            p_profanity = _WORDLIST_DIR / f"{lang}_profanity.txt"
            p_hate = _WORDLIST_DIR / f"{lang}_hate.txt"
            p_threat = _WORDLIST_DIR / f"{lang}_threat.txt"
            p_group = _WORDLIST_DIR / f"{lang}_group_indicators.txt"
            p_combined = _WORDLIST_DIR / "profanity.txt"

            for p, key in ((p_profanity, "profanity"), (p_hate, "hate"), (p_threat, "threat"), (p_group, "group_indicators")):
                if p.exists():
                    with p.open("r", encoding="utf-8") as fh:
                        for line in fh:
                            w = _sanitize_word(line)
                            if not w:
                                continue
                            if key == "group_indicators":
                                data["group_indicators"].add(w)
                            else:
                                data[key].add(w)

            # combined fallback (more permissive; sanitized)
            if p_combined.exists():
                with p_combined.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        w = _sanitize_word(line)
                        if not w:
                            continue
                        data["combined"].add(w)
    except Exception as e:
        log.warning("wordlist load failed for %s: %s", lang, e)

    # If per-category lists are missing but combined present, fallback
    if not data["profanity"] and data["combined"]:
        # copy combined into profanity (already sanitized)
        data["profanity"] = set(data["combined"])

    _WORDLIST_CACHE[lang] = data
    log.info("Loaded wordlists for %s: profanity=%d hate=%d threat=%d combined=%d group_indicators=%d",
             lang, len(data["profanity"]), len(data["hate"]), len(data["threat"]), len(data["combined"]), len(data["group_indicators"]))
    return data


# -------------------------
# Obfuscation-tolerant pattern builder
# -------------------------
def _make_obf_pattern(word: str) -> Pattern:
    """
    Build and cache a regex to match obfuscated forms of `word`.
    Pattern specifics:
      - permit limited separators between letters (punctuation, underscores, zero-width)
      - allow optional trailing 's' (plural)
      - use word boundaries to reduce false positives
    """
    key = word.lower()
    if key in _PATTERN_CACHE:
        return _PATTERN_CACHE[key]

    between = r'(?:[^\w\s' + re.escape(_ZERO_WIDTH_CHARS) + r']{0,4}[\s' + re.escape(_ZERO_WIDTH_CHARS) + r']*)'
    parts = [re.escape(ch) + between for ch in key]
    body = ''.join(parts)
    pat = rf'\b{body}s?\b'
    try:
        compiled = re.compile(pat, flags=re.IGNORECASE)
    except re.error:
        # fallback to simple word boundary match
        compiled = re.compile(rf'\b{re.escape(key)}s?\b', flags=re.IGNORECASE)
    _PATTERN_CACHE[key] = compiled
    return compiled


def _matches_any(words: Set[str], text_norm: str, use_obf: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Check if any term in `words` appears in normalized text (exact token or obfuscated match).
    Returns (True, matched_word) or (False, None).
    Strategy:
      - token membership first for speed
      - obfuscated regex patterns next
      - conservative fuzzy fallback (only long words; higher threshold to avoid false positives)
    """
    if not words:
        return False, None

    text_low = text_norm.lower()
    tokens = set(re.findall(r'\w+', text_low))

    # exact membership (fast)
    for w in words:
        if w in tokens:
            log.debug("Exact token match for '%s' in text", w)
            return True, w

    # obfuscated pattern matching
    if use_obf:
        for w in words:
            pat = _make_obf_pattern(w)
            if pat.search(text_low):
                log.debug("Obfuscated pattern matched for '%s'", w)
                return True, w

    # very conservative fuzzy fallback (only for words length >=5)
    import difflib
    for w in words:
        if len(w) >= 5 and len(w) <= 20:
            for t in tokens:
                # require a higher ratio to avoid accidental matches (0.92)
                if difflib.SequenceMatcher(None, w, t).ratio() > 0.92:
                    log.debug("Fuzzy match: '%s' ~= '%s'", w, t)
                    return True, w
    return False, None


# -------------------------
# Profanity / hate / threat checker (dynamic)
# -------------------------
class ProfanityChecker:
    """
    Loads wordlists from files (cached). Does language-aware checks and
    returns (has_violation: bool, v_type: str | None).
    v_type examples: 'profanity_hi', 'profanity_en', 'hate_speech_en', 'threat_hi', 'hate_speech_group_threat'
    """
    @classmethod
    def check(cls, text: str, lang_ctx: LanguageContext) -> (bool, Optional[str]):
        if not text:
            return False, None

        # prefer upstream normalised_text when present (e.g., earlier pipeline stages)
        input_text = getattr(lang_ctx, "normalised_text", None) or text
        norm = normalise_for_lookup(input_text)
        lang = (lang_ctx.code or "en").lower()

        lists = _load_wordlists(lang)

        # 1) Threat phrases (language-specific)
        if lists.get("threat"):
            matched = _matches_any(lists["threat"], norm, use_obf=True)
            if matched[0]:
                # if group indicators present -> hate_speech_group_threat
                if lists.get("group_indicators"):
                    gi_matched = _matches_any(lists["group_indicators"], norm, use_obf=False)
                    if gi_matched[0]:
                        log.info("Matched threat '%s' with group indicator '%s'", matched[1], gi_matched[1])
                        return True, "hate_speech_group_threat"
                log.info("Matched threat: %s", matched[1])
                return True, ("threat_hi" if lang.startswith("hi") else "threat")

        # 2) Hate speech (language-specific)
        if lists.get("hate"):
            matched = _matches_any(lists["hate"], norm, use_obf=True)
            if matched[0]:
                log.info("Matched hate word: %s", matched[1])
                return True, ("hate_speech_en" if lang.startswith("en") else "hate_speech")

        # 3) Profanity (language-specific)
        if lists.get("profanity"):
            matched = _matches_any(lists["profanity"], norm, use_obf=True)
            if matched[0]:
                log.info("Matched profanity: %s", matched[1])
                return True, f"profanity_{lang}"

        # 4) Combined fallback list
        if lists.get("combined"):
            matched = _matches_any(lists["combined"], norm, use_obf=True)
            if matched[0]:
                log.info("Matched combined profanity: %s", matched[1])
                return True, f"profanity_{lang}"

        # 5) small Hinglish heuristics (token-based): catch threat verbs not listed explicitly
        if lang.startswith("hi") or lang == "hi-en":
            hinglish_threat_tokens = {"maar", "maarunga", "maarunga", "marunga", "marunga", "khatam", "khatamkar", "thok", "dhundh", "dhundo", "dekh", "dekhunga", "pohonch", "pohanch", "pohonch"}
            for t in hinglish_threat_tokens:
                if re.search(rf'\b{re.escape(t)}', norm):
                    log.info("Matched hinglish threat-token: %s", t)
                    # check group indicator
                    gi_matched = _matches_any(lists.get("group_indicators", set()), norm, use_obf=False)
                    if gi_matched[0]:
                        return True, "hate_speech_group_threat"
                    return True, "threat_hi"

        return False, None


# -------------------------
# Other checkers (PII unchanged) and KeywordChecker (uses token checks first)
# -------------------------
class PIIChecker:
    @staticmethod
    def check(text: str) -> (bool, Optional[str]):
        for pii_type, pattern in PII_PATTERNS.items():
            if pattern.search(text):
                return True, pii_type
        return False, None


class KeywordChecker:
    @staticmethod
    async def check(text: str, profile: RulesProfileResponse, lang_ctx: LanguageContext, redis: Redis) -> KeywordResult:
        """
        Minimal changes: token-based Redis checks (fast), with obfuscated fallback if needed.
        Keeps the same return type as before.
        """
        if not text:
            return KeywordResult(decision="ALLOW", matched=None, confidence=0.0)

        full_norm = normalise_for_lookup(text)
        tokens = set(re.findall(r'\w+', full_norm)) | set(re.findall(r'\w+', text.lower()))

        lang = lang_ctx.code if lang_ctx.code in profile.supported_languages else "en"
        hard_set_key = f"keywords:{lang}:hard"
        soft_set_key = f"keywords:{lang}:soft"

        # quick token membership checks
        try:
            for tok in tokens:
                if await redis.sismember(hard_set_key, tok):
                    return KeywordResult(decision="BLOCK", matched=tok, confidence=1.0)
        except Exception:
            # don't block on redis errors
            log.debug("Redis hard set check failed, continuing", exc_info=True)

        # obfuscated fallback: try scanning hard set members if available (costly)
        try:
            members = await redis.smembers(hard_set_key)
            if members:
                members_str = {m.decode() if isinstance(m, (bytes, bytearray)) else str(m) for m in members}
                for kw in members_str:
                    if _make_obf_pattern(kw).search(full_norm):
                        return KeywordResult(decision="BLOCK", matched=kw, confidence=1.0)
        except Exception:
            log.debug("Redis smembers fallback failed", exc_info=True)

        # soft hints
        try:
            for tok in tokens:
                if await redis.sismember(soft_set_key, tok):
                    return KeywordResult(decision="HINT", matched=tok, confidence=0.5,
                                         hint=f"Message contains potentially toxic term: '{tok}'")
        except Exception:
            log.debug("Redis soft set check failed", exc_info=True)

        # transliteration fallback (if available)
        if getattr(lang_ctx, "is_transliterated", False) and getattr(lang_ctx, "normalised_text", None) and lang_ctx.normalised_text != text:
            translit_norm = normalise_for_lookup(lang_ctx.normalised_text)
            translit_tokens = set(re.findall(r'\w+', translit_norm))
            for tok in translit_tokens:
                try:
                    if await redis.sismember(hard_set_key, tok):
                        return KeywordResult(decision="BLOCK", matched=tok, confidence=1.0)
                except Exception:
                    continue

        return KeywordResult(decision="ALLOW", matched=None, confidence=0.0)


# -------------------------
# SpamChecker - fixed off-by-one
# -------------------------
class SpamChecker:
    @staticmethod
    async def check(user_id: Optional[str], profile: RulesProfileResponse, redis: Redis) -> bool:
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

        current = int(results[2])
        # allow up to `limit` messages; block when count > limit (i.e., on (limit+1)th message)
        return current > limit


# -------------------------
# Stage1Prefilter.process (public API preserved)
# -------------------------
class Stage1Prefilter:
    """
    Stage 1 — Fast Pre-filter (Multilingual)
    Executes Spam, PII, Profanity/HateSpeech/Threat, and Keyword checks.
    """

    @staticmethod
    async def process(text: str, profile: RulesProfileResponse, lang_ctx: LanguageContext,
                      user_id: Optional[str], redis: Redis) -> PreFilterResult:

        # 1. Spam
        is_spam = await SpamChecker.check(user_id, profile, redis)
        if is_spam:
            return PreFilterResult(blocked=True, stage="stage1", matched="spam_limit_exceeded",
                                   template_key="spam", detected_language=lang_ctx.code, category="SPAM")

        # 2. PII
        has_pii, pii_type = PIIChecker.check(text)
        if has_pii:
            return PreFilterResult(blocked=True, stage="stage1", matched=pii_type,
                                   template_key="pii", detected_language=lang_ctx.code, category="PII")

        # 3. Profanity / Hate / Threat
        input_for_profanity = getattr(lang_ctx, 'normalised_text', None) or text
        has_violation, v_type = ProfanityChecker.check(input_for_profanity, lang_ctx)
        if has_violation:
            category, template_key = _resolve_violation_category(v_type)
            return PreFilterResult(blocked=True, stage="stage1", matched=v_type,
                                   template_key=template_key, detected_language=lang_ctx.code, category=category)

        # 4. Keyword check
        keyword_result = await KeywordChecker.check(input_for_profanity, profile, lang_ctx, redis)
        if keyword_result.decision == "BLOCK":
            return PreFilterResult(blocked=True, stage="stage1", matched=keyword_result.matched,
                                   template_key="keyword", detected_language=lang_ctx.code, category="HATE_SPEECH")
        elif keyword_result.decision == "HINT":
            return PreFilterResult(blocked=False, stage="stage1", matched=keyword_result.matched,
                                   template_key="keyword", detected_language=lang_ctx.code,
                                   keyword_hint=keyword_result.hint, category="NONE")

        return PreFilterResult(blocked=False, stage="stage1", detected_language=lang_ctx.code, category="NONE")