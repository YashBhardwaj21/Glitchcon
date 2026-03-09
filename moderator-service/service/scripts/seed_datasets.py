import asyncio
import os
import sys
import time
import requests

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from datasets import load_dataset
from sentence_transformers import SentenceTransformer

# Setup path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.db.models import RulesProfile, BannedTopicEmbedding, PromptTemplate
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

async def seed_keywords_redis(redis: Redis):
    logger.info("Seeding Keyword Sets into Redis...")

    # ── English profanity ─────────────────────────────────────────────────────
    # Source: LDNOOBW — raw GitHub file (not on HuggingFace, must use requests)
    # https://github.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words
    logger.info("Downloading English LDNOOBW word list from GitHub...")
    english_bad_words = fetch_wordlist(
        "https://raw.githubusercontent.com/LDNOOBW/"
        "List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/en"
    )
    if english_bad_words:
        english_bad_words = [w.lower() for w in english_bad_words]
        logger.info(f"Downloaded {len(english_bad_words)} English words from LDNOOBW.")
    else:
        logger.warning("LDNOOBW English download failed after retries. Using hardcoded fallback.")
        english_bad_words = FALLBACK_EN_WORDS

    # ── Hindi profanity ───────────────────────────────────────────────────────
    # Source: LDNOOBW Hindi list (same repo, /hi file)
    logger.info("Downloading Hindi LDNOOBW word list from GitHub...")
    hindi_bad_words = fetch_wordlist(
        "https://raw.githubusercontent.com/LDNOOBW/"
        "List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/hi"
    )
    if hindi_bad_words:
        logger.info(f"Downloaded {len(hindi_bad_words)} Hindi words from LDNOOBW.")
    else:
        logger.warning("LDNOOBW Hindi download failed after retries. Using hardcoded fallback.")
        hindi_bad_words = FALLBACK_HI_WORDS

    # ── Hindi-English code-mixed (Hinglish) toxicity ──────────────────────────
    # Source: textdetox/multilingual_toxicity_dataset (HuggingFace, verified)
    # https://huggingface.co/datasets/textdetox/multilingual_toxicity_dataset
    #
    # IMPORTANT: splits are named by language code, NOT "train"
    # Available splits: en, ru, uk, de, es, am, zh, ar, hi, it, fr, he, hin, tt, ja
    # "hi"  = Hindi in Devanagari script
    # "hin" = Hindi in Roman/transliterated script (closest to Hinglish)
    logger.info("Loading Hindi toxic texts from textdetox/multilingual_toxicity_dataset...")
    hinglish_bad_words = []
    try:
        hi_ds  = load_dataset("textdetox/multilingual_toxicity_dataset", split="hi")
        hin_ds = load_dataset("textdetox/multilingual_toxicity_dataset", split="hin")

        # Each row: { text: str, toxic: int (0 or 1) }
        # No "lang" column — split name IS the language
        hinglish_bad_words = [
            row["text"].strip()
            for row in list(hi_ds) + list(hin_ds)
            if row.get("toxic") == 1
            and isinstance(row.get("text"), str)
            and row.get("text", "").strip()
        ]
        logger.info(f"Extracted {len(hinglish_bad_words)} Hindi/Hinglish toxic texts.")
    except Exception as e:
        logger.warning(f"Failed to load textdetox dataset: {e}. Falling back to empty set.")

    # ── Write to Redis ─────────────────────────────────────────────────────────
    await redis.delete("keywords:en")
    await redis.delete("keywords:hi")
    await redis.delete("keywords:hi-en")

    if english_bad_words:
        await redis.sadd("keywords:en", *english_bad_words)
        logger.info(f"Seeded {len(english_bad_words)} words into keywords:en")

    if hindi_bad_words:
        await redis.sadd("keywords:hi", *hindi_bad_words)
        logger.info(f"Seeded {len(hindi_bad_words)} words into keywords:hi")

    if hinglish_bad_words:
        # Hinglish toxic texts go into both hi and hi-en sets
        await redis.sadd("keywords:hi", *hinglish_bad_words)
        await redis.sadd("keywords:hi-en", *hinglish_bad_words)
        logger.info(f"Seeded {len(hinglish_bad_words)} Hinglish texts into keywords:hi and keywords:hi-en")

    logger.info("Keyword seeding into Redis complete.")


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 — FAISS banned topic embeddings
# ─────────────────────────────────────────────────────────────────────────────

async def seed_faiss_topics(db: AsyncSession):
    logger.info("Seeding FAISS Banned Topic Embeddings...")

    profile_id = "default_test_profile"

    # English labels — multilingual MiniLM bridges these to Hindi/Tamil/etc at inference
    banned_topics = [
        "cryptocurrency investment scam quick money high returns",
        "instructions on how to commit suicide or self harm",
        "extreme racism hate speech targeting minorities",
        "violent threats to murder assault or physically harm someone",
        "child sexual abuse material illegal sexual content minors",
        "phishing scams stealing personal banking credentials",
        "drug dealing illegal substance purchase and sale",
    ]

    # Must use the same model as inference (paraphrase-multilingual-MiniLM-L12-v2)
    # Downloads ~118 MB on first run, cached in ~/.cache/huggingface
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
  "confidence": 0.0 to 1.0,
  "violated_rule": "brief rule name or null",
  "reason": "one sentence in English explaining the decision",
  "feedback_message": "polite educational message in {{ detected_language }} or null if ALLOW"
}"""
    )
    db.add(template)
    await db.commit()
    logger.info("Default profile and prompt template seeded.")


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
            await seed_profile(db)
            await seed_faiss_topics(db)
            await seed_keywords_redis(redis)
            logger.info("=== Seeding Complete ===")
        except Exception as e:
            logger.error(f"Seeding failed: {e}", exc_info=True)
            raise
        finally:
            await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())

    