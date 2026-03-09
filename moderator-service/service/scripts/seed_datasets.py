import asyncio
import os
import sys
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from datasets import load_dataset
from sentence_transformers import SentenceTransformer

# Setup path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import async_session_maker
from app.db.models import RulesProfile, BannedTopicEmbedding, PromptTemplate
from app.core.config import settings
from app.core.logging import logger

async def seed_keywords_redis(redis: Redis):
    logger.info("Seeding Keyword Sets into Redis...")
    
    # English Profanity (Using LDNOOBW list from HuggingFace, but simplified here by using a direct subset 
    # to avoid a massive HF download if internet is slow. For real use, `load_dataset("LDNOOBW")`)
    # We will use the `better-profanity` built-in list + a few custom words for Phase 1.
    
    # To demonstrate multilingual caching, let's hardcode a small set of Hindi/ Hinglish words 
    # normally this would come from the IIT-B Hindi Abuse dataset via HuggingFace
    hindi_hinglish_bad_words = [
        "bc", "mc", "chu", "chutiya", "madarchod", "bhenchod", "harami",
        "कुतिया", "हरामी", "मादरचोद", "बहनचोद", "चूतिया"
    ]
    
    # English test set
    english_bad_words = [
        "cunt", "faggot", "nigger", "kill yourself", "kys", 
        "retard", "whore", "slut"
    ]
    
    # We will store these in sets named by language
    await redis.delete("keywords:hi")
    await redis.delete("keywords:hi-en")
    await redis.delete("keywords:en")
    
    if hindi_hinglish_bad_words:
        await redis.sadd("keywords:hi", *hindi_hinglish_bad_words)
        await redis.sadd("keywords:hi-en", *hindi_hinglish_bad_words)
        
    if english_bad_words:
        await redis.sadd("keywords:en", *english_bad_words)
        
    logger.info("Keyword Sets seeded directly into Redis.")

async def seed_faiss_topics(db: AsyncSession):
    logger.info("Seeding FAISS Banned Topics...")
    
    profile_id = "default_test_profile"
    
    # Core topics to ban globally across languages
    banned_topics = [
        "crypto cryptocurrency investment scam high returns quick money",
        "instructions on how to commit suicide or self harm",
        "extreme racism hate speech against minorities",
        "violent threats to murder assault or kill someone",
        "child pornography pedophilia illegal sexual content"
    ]
    
    # Check if they exist to avoid duplicates
    model = SentenceTransformer(settings.EMBEDDING_MODEL)
    
    for i, topic in enumerate(banned_topics):
        embedding_list = model.encode(topic).tolist()
        
        # Create DB record
        record = BannedTopicEmbedding(
            profile_id=profile_id,
            topic_label=f"topic_{i}",
            topic_text=topic,
            embedding=embedding_list
        )
        db.add(record)
        
    await db.commit()
    logger.info(f"Seeded {len(banned_topics)} FAISS Banned Topics.")

async def seed_profile(db: AsyncSession):
    logger.info("Seeding Default Profile...")
    profile_id = "default_test_profile"
    
    # Create the profile
    profile = RulesProfile(
        profile_id=profile_id,
        group_topic="General Educational Programming Community",
        global_rules=[
            "No hatespeech, racism, or severe profanity.",
            "No crypto or financial scams.",
            "Always be respectful."
        ],
        group_rules=[
            "Keep the discussion focused on Python, JavaScript, and programming.",
            "No self-promotion or links to external paid courses."
        ],
        keywords_by_language={}, # populated via Redis mostly, but could sync here
        spam_max_messages=5,
        spam_time_window_seconds=10,
        pii_regex=[
            r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b" # Email regex
        ]
    )
    db.add(profile)
    
    # Create the Default LLM Template
    template = PromptTemplate(
        profile_id=profile_id,
        version=1,
        template_text="""
You are a multilingual content moderation engine for a structured learning community.
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
   If detected_language is "English" or unknown, respond in English.
4. Be culturally sensitive.

Return ONLY a valid JSON object:
{
  "decision": "ALLOW" or "BLOCK",
  "confidence": 0.0 to 1.0,
  "violated_rule": "brief rule name or null",
  "reason": "one sentence in English explaining the decision",
  "feedback_message": "polite educational message in {{ detected_language }} explaining why it was blocked or null if allowed"
}
"""
    )
    db.add(template)
    await db.commit()
    logger.info("Seeded Default Profile and Prompt.")

async def main():
    logger.info("=== Starting Dataset Seeding ===")
    
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    
    async with async_session_maker() as db:
        # Clear out old stuff for idempotency 
        # (in production you would handle migrations/upserts properly)
        
        try:
            await seed_profile(db)
            await seed_faiss_topics(db)
            await seed_keywords_redis(redis)
            
            logger.info("=== Seeding Complete ===")
        except Exception as e:
            logger.error(f"Seeding failed: {e}")
        finally:
            await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
