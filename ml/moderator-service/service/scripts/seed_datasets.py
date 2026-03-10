import asyncio
import os
import re
import sys
import time

# ── stdlib path setup first so app.* imports resolve ────────────────────────
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Heavy ML imports are deferred to the functions that need them ────────────
# (datasets, sentence_transformers, sklearn, numpy)
# Importing them here would crash the script if the ML deps aren't installed.

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.db.models import RulesProfile, BannedTopicEmbedding, PromptTemplate, APIKey
import bcrypt
from app.core.config import settings
from app.core.logging import logger

# ─────────────────────────────────────────────────────────────────────────────
# Hardcoded fallback word lists
# Used when GitHub raw content is unreachable (corporate network,
# Windows ConnectionResetError 10054, or rate limiting).
# These are a minimal but functional seed — the GitHub list adds ~400 more words.
# ─────────────────────────────────────────────────────────────────────────────

FALLBACK_EN_WORDS = [
    "fuck", "shit", "bitch", "asshole", "bastard", "cunt", "dick", "pussy",
    "faggot", "nigger", "nigga", "whore", "slut", "retard", "moron", "idiot",
    "kill yourself", "kys", "go die", "hate you", "stupid", "dumbass",
]

FALLBACK_HI_WORDS = [
    "मादरचोद", "भडवा", "रंडी", "हरामी", "कमीना", "बेवकूफ", "गधा",
    "chutiya", "madarchod", "bhadwa", "randi", "harami", "kamina",
]

# ─────────────────────────────────────────────────────────────────────────────
# Dataset-derived keyword filter helpers
# Prevents political names / URLs / @mentions / hashtags entering Redis
# ─────────────────────────────────────────────────────────────────────────────

SKIP_PATTERNS = [
    r'^https?://',   # URLs
    r'^@',           # @mentions
    r'^#',           # hashtags
    r'^\d+$',        # pure numbers
    r'^rt$',         # retweet marker
    r'^\.$',         # lone dot
]

def is_valid_keyword(word: str) -> bool:
    """Return True only for words worth adding to a toxic keyword set."""
    if len(word) < 4:
        return False
    for pattern in SKIP_PATTERNS:
        if re.match(pattern, word):
            return False
    return True

# ─────────────────────────────────────────────────────────────────────────────
# Robust HTTP fetch with retry + browser-like headers
# Fixes Windows ConnectionResetError(10054) from raw.githubusercontent.com
# ─────────────────────────────────────────────────────────────────────────────

def fetch_wordlist(url: str, retries: int = 3, delay: float = 2.0) -> list[str]:
    """
    Fetch a plain-text word list from a URL.
    Retries up to `retries` times with `delay` seconds between attempts.
    Returns a list of stripped, non-empty lines. Returns [] if all retries fail.

    Why browser headers? GitHub's raw content server (raw.githubusercontent.com)
    sometimes forcibly closes connections from plain Python requests on Windows
    (ConnectionResetError 10054). Adding a User-Agent header that looks like a
    browser prevents this reset.
    """
    import requests
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            words = [w.strip() for w in response.text.splitlines() if w.strip()]
            return words
        except Exception as e:
            logger.warning(f"Attempt {attempt}/{retries} failed for {url}: {e}")
            if attempt < retries:
                time.sleep(delay)
    return []


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — Keyword seeding into Redis
# ─────────────────────────────────────────────────────────────────────────────

async def seed_smart_keywords(redis: Redis):
    logger.info("Building TF-IDF smart keyword sets from dataset (English)...")
    from datasets import load_dataset
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    # Load dataset
    en_ds    = load_dataset("textdetox/multilingual_toxicity_dataset", split="en")
    all_rows = list(en_ds)

    texts  = [r["text"] for r in all_rows]
    labels = [r["toxic"] for r in all_rows]  # 0 or 1

    # Fit TF-IDF on unigrams only
    tfidf = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 1),
        min_df=5,           # word must appear in at least 5 documents
        max_df=0.85,        # ignore words in >85% of docs (too common)
        sublinear_tf=True,
    )
    X = tfidf.fit_transform(texts)
    vocab = tfidf.get_feature_names_out()  # list of words in order

    # Fit logistic regression to get per-word toxic signal score
    clf = LogisticRegression(max_iter=1000, C=1.0)
    clf.fit(X, labels)

    # clf.coef_[0] is the weight per word — positive = toxic signal
    coef = clf.coef_[0]

    from collections import Counter
    toxic_doc_freq = Counter()
    for row in [r for r in all_rows if r["toxic"] == 1]:
        unique_words = set(row["text"].lower().split())
        for word in unique_words:
            toxic_doc_freq[word] += 1

    # Separate into hard (high signal) and soft (moderate signal)
    hard_keywords = []
    soft_keywords = []

    for word, weight in zip(vocab, coef):
        # The user specifically requested unigrams. 'word' will be strings
        if len(word) < 3:
            continue
        if weight >= 2.8 and toxic_doc_freq.get(word, 0) >= 20:  # previously 3.5, now 2.8 with robust frequency check
            hard_keywords.append(word)
        elif weight >= 1.5:      # moderately toxic — soft, send to LLM
            soft_keywords.append(word)

    logger.info(f"Hard keywords: {len(hard_keywords)}, Soft keywords: {len(soft_keywords)}")
    logger.info(f"Sample hard: {hard_keywords[:10]}")
    logger.info(f"Sample soft: {soft_keywords[:10]}")

    # Seed into separate Redis sets
    await redis.delete("keywords:en:hard", "keywords:en:soft")

    if hard_keywords:
        await redis.sadd("keywords:en:hard", *hard_keywords)
    if soft_keywords:
        await redis.sadd("keywords:en:soft", *soft_keywords)

    logger.info("Smart keyword seeding (English) complete.")

async def seed_smart_keywords_hindi(redis: Redis):
    logger.info("Building TF-IDF smart keyword sets from dataset (Hindi/Hinglish)...")
    from datasets import load_dataset
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    hi_ds  = load_dataset("textdetox/multilingual_toxicity_dataset", split="hi")
    hin_ds = load_dataset("textdetox/multilingual_toxicity_dataset", split="hin")
    all_rows = list(hi_ds) + list(hin_ds)

    texts  = [r["text"] for r in all_rows]
    labels = [r["toxic"] for r in all_rows]

    # Same TF-IDF + LogReg approach
    # char_wb analyzer works better for Devanagari script and code-mixed
    tfidf = TfidfVectorizer(
        analyzer="char_wb",   # character n-grams for Hindi
        ngram_range=(3, 5),
        min_df=5,
        max_df=0.85,
        sublinear_tf=True,
    )
    X = tfidf.fit_transform(texts)
    vocab = tfidf.get_feature_names_out()

    clf = LogisticRegression(max_iter=1000, C=1.0)
    clf.fit(X, labels)
    coef = clf.coef_[0]

    from collections import Counter
    toxic_doc_freq = Counter()
    for row in [r for r in all_rows if r["toxic"] == 1]:
        unique_words = set(row["text"].lower().split())
        for word in unique_words:
            toxic_doc_freq[word] += 1

    hard_hi = []
    soft_hi = []
    hard_hien = []
    soft_hien = []

    for word, weight in zip(vocab, coef):
        # We strip spaces as character n-grams might include them
        word = word.strip()
        if len(word) < 3:
            continue
            
        # Split into Devanagari (hi) and Roman (hi-en) based on characters
        is_roman = bool(re.search(r'[a-zA-Z]', word))
        if weight >= 2.8 and toxic_doc_freq.get(word, 0) >= 20:
            if is_roman: hard_hien.append(word)
            else: hard_hi.append(word)
        elif weight >= 1.5:
            if is_roman: soft_hien.append(word)
            else: soft_hi.append(word)

    logger.info(f"Hard keywords hi: {len(hard_hi)}, hi-en: {len(hard_hien)}")
    logger.info(f"Soft keywords hi: {len(soft_hi)}, hi-en: {len(soft_hien)}")

    await redis.delete("keywords:hi:hard", "keywords:hi:soft", "keywords:hi-en:hard", "keywords:hi-en:soft")

    if hard_hi: await redis.sadd("keywords:hi:hard", *hard_hi)
    if soft_hi: await redis.sadd("keywords:hi:soft", *soft_hi)
    if hard_hien: await redis.sadd("keywords:hi-en:hard", *hard_hien)
    if soft_hien: await redis.sadd("keywords:hi-en:soft", *soft_hien)

    logger.info("Smart keyword seeding (Hindi/Hinglish) complete.")


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 — FAISS banned topic embeddings
# ─────────────────────────────────────────────────────────────────────────────

async def seed_faiss_topics(db: AsyncSession):
    logger.info("Seeding FAISS Banned Topic Embeddings...")
    from sentence_transformers import SentenceTransformer

    profile_id = "default_test_profile"

    # ── Delete guard: remove stale embeddings before re-seeding ──────────────
    await db.execute(
        delete(BannedTopicEmbedding).where(
            BannedTopicEmbedding.profile_id == profile_id
        )
    )
    await db.flush()
    logger.info(f"Cleared old FAISS embeddings for profile '{profile_id}'.")

    # Expanded from 7 generic labels to 21 specific labels (3 per category).
    # More specific labels = higher cosine similarity scores at inference.
    # The multilingual MiniLM model bridges these English labels to Hindi/Tamil/etc.
    banned_topics = [
        # ── Crypto / financial scams ─────────────────────────────────────────
        "cryptocurrency investment scam quick money high returns",
        "Bitcoin Ethereum pump and dump scheme guaranteed profit",
        "send money crypto wallet get rich quick guaranteed returns",

        # ── Self-harm / suicide ──────────────────────────────────────────────
        "instructions on how to commit suicide or self harm",
        "how many pills to take to overdose on medication",
        "methods to end your life want to die need help",

        # ── Hate speech / racism ─────────────────────────────────────────────
        "racist slurs targeting Black African people hate speech",
        "casteist slurs against Dalit lower caste communities India",
        "communal hatred between Hindus and Muslims religious violence",

        # ── Violence / threats ───────────────────────────────────────────────
        "violent threats to murder assault or physically harm someone",
        "I will find you and kill you death threat",
        "bomb explosion attack planning instructions violence",

        # ── CSAM ────────────────────────────────────────────────────────────
        "child sexual abuse material illegal sexual content minors",
        "sexual content involving underage children exploitation",
        "grooming children for sexual purposes online predator",

        # ── Phishing / fraud ─────────────────────────────────────────────────
        "phishing scams stealing personal banking credentials passwords",
        "OTP bank account password steal fraud impersonation",
        "fake KYC Aadhaar PAN UPI verification fraud India",

        # ── Drug dealing ─────────────────────────────────────────────────────
        "drug dealing illegal substance purchase and sale",
        "buy weed cocaine heroin online home delivery",
        "MDMA LSD ganja charas online order illegal drugs",
    ]

    # Must use the same model as inference (paraphrase-multilingual-mpnet-base-v2)
    # Downloads ~420 MB on first run, cached in ~/.cache/huggingface
    model = SentenceTransformer(settings.EMBEDDING_MODEL)

    for topic in banned_topics:
        embedding_list = model.encode(topic, normalize_embeddings=True).tolist()
        record = BannedTopicEmbedding(
            profile_id=profile_id,
            topic_label=topic[:200],
            embedding=embedding_list,
        )
        db.add(record)

    await db.commit()
    logger.info(f"Seeded {len(banned_topics)} banned topic embeddings into Postgres.")


# ─────────────────────────────────────────────────────────────────────────────
# PROFILE + PROMPT TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────

async def seed_profile(db: AsyncSession):
    logger.info("Seeding Default Rules Profile and Prompt Template...")

    profile_id = "default_test_profile"

    # Idempotency: delete existing records before re-seeding
    await db.execute(delete(PromptTemplate).where(PromptTemplate.profile_id == profile_id))
    await db.execute(delete(BannedTopicEmbedding).where(BannedTopicEmbedding.profile_id == profile_id))
    await db.execute(delete(RulesProfile).where(RulesProfile.profile_id == profile_id))
    await db.flush()

    profile = RulesProfile(
        profile_id=profile_id,
        group_topic="General Educational Programming Community",
        global_rules=[
            "No hate speech, racism, or severe profanity.",
            "No crypto or financial scams.",
            "No threats of violence or self-harm content.",
            "No sharing of personal information (phone, email, Aadhaar, PAN).",
            "Always be respectful to other community members.",
        ],
        group_rules=[
            "Keep discussion focused on Python, JavaScript, and general programming.",
            "No self-promotion or links to external paid courses.",
        ],
        keywords_by_language={},
        spam_limit=5,
        spam_window_s=10,
        llm_confidence_threshold_en=0.85,
        llm_confidence_threshold_indic=0.85,
    )
    db.add(profile)
    await db.flush()

    template = PromptTemplate(
        profile_id=profile_id,
        version=1,
        template_text="""You are a multilingual content moderation engine for a structured learning community.
You support English, Hindi, Tamil, Telugu, Kannada, Malayalam, and Hindi-English code-mix.

DETECTED LANGUAGE: {{ detected_language }}
GROUP CONTEXT: {{ group_topic }}

GLOBAL RULES (apply to all communities, all languages):
{{ global_rules_formatted }}

CRITICAL DISTINCTIONS — read carefully before making any decision:
- Mentioning a race, religion, gender identity, or nationality is NOT hate speech.
- Expressing love, support, or neutral facts about a group is NOT hate speech.
- Hate speech requires ATTACK, DEHUMANIZATION, or SLURS directed AT a group based on protected characteristics (race, religion, etc).
- If someone uses abusive language/swearing AT an individual without mentioning protected groups, it is PROFANITY, NOT HATE_SPEECH.
- If someone threatens to kill or harm an individual without group-based slurs, it is THREAT, NOT HATE_SPEECH.
- A message saying "trans women are beautiful" is SUPPORTIVE, not hateful — ALLOW it.
- A message saying "God bless you" or "Allah is great" is religious expression — ALLOW it.
- A message mentioning someone's ethnicity neutrally is NOT racist — ALLOW it.
- Only BLOCK if the message contains explicit slurs, calls for violence, or direct dehumanization of a group.

GROUP-SPECIFIC RULES:
{{ group_rules_formatted }}

MESSAGE TO EVALUATE: "{{ message }}"{{ extra_instruction }}

INSTRUCTIONS:
1. Evaluate the message considering its language and cultural context.
2. For code-mixed messages (Hinglish), evaluate the combined meaning.
3. The "feedback_message" field MUST be written in {{ detected_language }}.
   If detected_language is "Hindi", respond in Hindi.
   If detected_language is "Tamil", respond in Tamil.
   If detected_language is "English" or unknown, respond in English.
4. Be culturally sensitive — the same phrase may carry different weight in different languages.
5. The "reason" field must always be in English (for admin audit logs).

Return ONLY a valid JSON object with no text outside it:
{
  "decision": "ALLOW" or "BLOCK",
  "category": one of ["HATE_SPEECH", "PROFANITY", "THREAT", "SELF_HARM", 
              "PII", "SPAM", "SCAM", "SEXUAL", "CSAM", "OFF_TOPIC", 
              "MISINFORMATION", "NONE"],
  "confidence": 0.0 to 1.0,
  "violated_rule": "brief rule name or null",
  "reason": "one sentence in English explaining the decision",
  "feedback_message": "polite educational message in {{ detected_language }} or null if ALLOW"
}

CATEGORY GUIDE:
- HATE_SPEECH    : Focuses on protected groups. Slurs, dehumanisation, attacks on race/religion/gender/caste.
- PROFANITY      : General abusive language, swear words, general cursing directed at an individual or general situation.
- THREAT         : Direct threats of physical harm, violence, or doxxing to an individual.
- SELF_HARM      : suicide, self-harm instructions or encouragement  
- PII            : phone numbers, emails, Aadhaar, PAN, UPI, bank details
- SPAM           : repeated messages, flooding, irrelevant promotion
- SCAM           : crypto fraud, phishing, fake investment schemes
- SEXUAL         : explicit sexual content, harassment
- CSAM           : any sexual content involving minors
- OFF_TOPIC      : message outside the group's stated topic
- MISINFORMATION : verifiably false claims presented as fact
- NONE           : message is clean, no violation
"""
    )
    db.add(template)
    await db.commit()
    logger.info("Default profile and prompt template seeded.")


async def seed_api_key(db: AsyncSession):
    """
    UPSERT a test API key. Uses SELECT + UPDATE-or-INSERT instead of
    DELETE + INSERT to avoid UniqueViolation if the record already exists
    and to avoid resetting DB sequences.
    """
    logger.info("Seeding Test API Key...")
    
    # Check if a test key already exists
    result = await db.execute(select(APIKey).where(APIKey.app_name == "Test Internal Key"))
    existing = result.scalar_one_or_none()

    if existing:
        actual_id = existing.id
        test_key = f"{actual_id}.secret123"
        hashed = bcrypt.hashpw(test_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        
        # Update the hash so it matches <id>.secret123
        existing.key_hash = hashed
        existing.rate_limit_per_min = 1000
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        logger.info(f"Existing test API key updated. id={actual_id}  plaintext='{test_key}'")
    else:
        # Insert placeholder hash first to claim the ID
        key = APIKey(
            app_name="Test Internal Key",
            key_hash="placeholder_hash",
            rate_limit_per_min=1000,
        )
        db.add(key)
        await db.flush() # flush to get the ID without committing
        
        # Now hash the real key using the generated ID
        test_key = f"{key.id}.secret123"
        hashed = bcrypt.hashpw(test_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        
        # Update with correctly formatted hash
        key.key_hash = hashed
        await db.commit()
        await db.refresh(key)
        logger.info(f"Test API key created. id={key.id}  use key='{test_key}'")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    logger.info("=== Starting Dataset Seeding ===")
    logger.info("Make sure Docker Compose is running: docker-compose up -d db redis")

    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    async with AsyncSessionLocal() as db:
        try:
            # Order matters: profile must exist before faiss topics (FK constraint)
            await seed_api_key(db)
            await seed_profile(db)
            await seed_faiss_topics(db)
            await seed_smart_keywords(redis)
            await seed_smart_keywords_hindi(redis)
            logger.info("=== Seeding Complete ===")
        except Exception as e:
            logger.error(f"Seeding failed: {e}", exc_info=True)
            raise
        finally:
            await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())

    