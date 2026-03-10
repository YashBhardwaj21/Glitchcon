import faiss
import numpy as np
from typing import NamedTuple, Literal, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sentence_transformers import SentenceTransformer

from app.db.models import BannedTopicEmbedding
from app.core.logging import logger

# ─── Soft-block thresholds ────────────────────────────────────────────────────
# HARD: certain violation — block immediately without LLM
# SOFT: uncertain — pass to LLM with a semantic hint
# Below SOFT: clean — LLM runs without any hint
FAISS_HARD_BLOCK_THRESHOLD = 0.82
FAISS_SOFT_BLOCK_THRESHOLD = 0.65


class FAISSResult(NamedTuple):
    """
    Three-state result from Stage 3 semantic search.

    decision:
        "BLOCK" — score >= HARD threshold.  Block immediately.
        "HINT"  — score in [SOFT, HARD).   Pass to LLM with a semantic hint.
        "ALLOW" — score < SOFT threshold.  LLM runs without any hint.
    topic:    matched banned topic label (or None when decision is ALLOW)
    category: violation category (e.g. SCAM, HATE_SPEECH)
    score:    cosine similarity (0.0–1.0)
    """
    decision: Literal["BLOCK", "HINT", "ALLOW"]
    topic: str | None
    category: str
    score: float


TOPIC_CATEGORY_MAP = {
    # ── Crypto / investment scams ─────────────────────────────────────────────
    "cryptocurrency investment scam"                          : "SCAM",
    "bitcoin ethereum pump and dump"                          : "SCAM",
    "send money get rich quick"                               : "SCAM",
    "crypto wallet private key seed phrase"                   : "SCAM",
    "I can double your money in 30 days guaranteed DM me"     : "SCAM",
    "crypto coin will 10x buy now I have insider information" : "SCAM",
    "work from home earn 50000 no experience required"        : "SCAM",
    "you have won 25 lakh in the lucky draw claim prize now"  : "SCAM",

    # ── India-specific scams (NEW) ────────────────────────────────────────────
    "PM Kisan yojana mein extra payment claim karo abhi"      : "SCAM",
    "government job guaranteed pay registration fee online"   : "SCAM",
    "your SIM will be blocked share details to prevent it"    : "SCAM",
    "UPI payment screenshot sent release the product now"     : "SCAM",
    "full scholarship available apply fee is only 2000 rupees": "SCAM",
    "flat available very cheap rent contact owner directly"   : "SCAM",
    "I have your private video pay or I send it to contacts"  : "SCAM",
    "like this YouTube video and earn 100 rupees per task"    : "SCAM",
    "send OTP for KYC verification or account will be blocked": "SCAM",
    "I am US army officer need help transferring money India" : "SCAM",

    # ── Self harm ─────────────────────────────────────────────────────────────
    "instructions on how to commit suicide"                   : "SELF_HARM",
    "how many pills to take to overdose"                      : "SELF_HARM",
    "methods to end your life"                                : "SELF_HARM",
    "want to die need help ending it"                         : "SELF_HARM",
    # Self-harm subtypes (NEW)
    "I have been collecting pills for weeks almost have enough now" : "SELF_HARM",
    "said goodbye to all my close friends today just in case"      : "SELF_HARM",
    "I wrote letters to everyone I love this morning just in case" : "SELF_HARM",
    "which bridge near my city is the highest and most isolated"   : "SELF_HARM",
    "I want to fall asleep gently and never wake up again"         : "SELF_HARM",
    "I have been cutting myself every day it is the only relief"   : "SELF_HARM",
    "how many pills does it take to not wake up again"             : "SELF_HARM",
    "I am not afraid to die anymore that means I am ready"         : "SELF_HARM",
    "I cancelled all my future plans because I will not need them" : "SELF_HARM",
    "I gave away all my belongings this week it felt freeing"      : "SELF_HARM",
    "I want to end my life tonight I have made up my mind"         : "SELF_HARM",
    "I have been stockpiling my medication for a specific purpose" : "SELF_HARM",
    "I am done fighting I just want it to stop permanently"        : "SELF_HARM",
    "I have been saving every prescription given to me for months" : "SELF_HARM",

    # ── Hate speech ───────────────────────────────────────────────────────────
    "extreme racism hate speech"                              : "HATE_SPEECH",
    "racist slurs targeting black"                            : "HATE_SPEECH",
    "casteist slurs against dalit"                            : "HATE_SPEECH",
    "communal hatred between hindus muslims"                  : "HATE_SPEECH",
    "antisemitic content targeting jewish"                    : "HATE_SPEECH",
    # India-specific hate (NEW)
    "love jihad is a real organised conspiracy against our daughters"     : "HATE_SPEECH",
    "they are targeting Hindu girls to convert them through marriage"     : "HATE_SPEECH",
    "halal meat is funding terrorism it should be banned"                 : "HATE_SPEECH",
    "beef eaters have no place in this Hindu nation"                      : "HATE_SPEECH",
    "that mosque was built on a demolished temple tear it down"           : "HATE_SPEECH",
    "inter-caste marriage is polluting our community bloodline"           : "HATE_SPEECH",
    "Dalit should not be allowed in upper caste homes or temples"         : "HATE_SPEECH",
    "our daughter brought shame marrying into that religion"              : "HATE_SPEECH",
    "the great replacement is happening in our own country"               : "HATE_SPEECH",
    "they breed like cockroaches to outnumber real citizens"              : "HATE_SPEECH",
    "we need to cleanse this country of these outsiders now"              : "HATE_SPEECH",
    "gay agenda is corrupting our children in schools"                    : "HATE_SPEECH",
    "women belong in the kitchen not in tech or leadership"               : "HATE_SPEECH",

    # ── Threats ───────────────────────────────────────────────────────────────
    "violent threats to murder assault"                       : "THREAT",
    "i will find you and kill you"                            : "THREAT",
    "bomb explosion attack planning"                          : "THREAT",
    # Doxxing subtypes (NEW)
    "I know where you live and I am coming for you tonight"   : "THREAT",
    "enjoy your evening walk I know your usual route very well": "THREAT",
    "I have your home address and I will share it everywhere" : "THREAT",
    "your address is going viral in this group tonight"       : "THREAT",
    "I know your parents names and where they both work"      : "THREAT",
    "I found your employer and I will contact HR immediately" : "THREAT",
    "I will get you fired by the end of this week"            : "THREAT",
    "your neighbourhood is known to me be very careful"       : "THREAT",
    "if you marry outside your community there will be consequences" : "THREAT",
    "I will tag your family and employer in my post"          : "THREAT",
    "I will DDoS your server until it is offline permanently" : "THREAT",
    "pay me or I release your private photos to everyone"     : "THREAT",
    "delete the post or your family will find out everything" : "THREAT",

    # ── CSAM ─────────────────────────────────────────────────────────────────
    "child sexual abuse material"                             : "CSAM",
    "sexual content involving underage"                       : "CSAM",

    # ── PII / Phishing ────────────────────────────────────────────────────────
    "phishing scams stealing credentials"                     : "PII",
    "otp bank account password steal"                         : "PII",
    "fake kyc aadhaar pan verification"                       : "PII",

    # ── Drugs ─────────────────────────────────────────────────────────────────
    "drug dealing illegal substance"                          : "SCAM",
    "buy weed cocaine heroin online"                          : "SCAM",
}


def get_category_for_topic(topic_label: str) -> str:
    if not topic_label:
        return "NONE"
    for key, category in TOPIC_CATEGORY_MAP.items():
        if key.lower() in topic_label.lower():
            return category
    return "HATE_SPEECH"  # default for unknown FAISS matches


class FaissService:
    _model = None
    # Dict mapping profile_id -> (faiss_index, list_of_topic_labels)
    _indices: dict[str, tuple[faiss.IndexFlatIP, list[str]]] = {}

    @classmethod
    def load_model(cls):
        if cls._model is None:
            from app.core.config import settings
            logger.info(f"Loading sentence-transformers model: {settings.EMBEDDING_MODEL}...")
            cls._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info(f"Model {settings.EMBEDDING_MODEL} loaded.")

    @classmethod
    async def reload_index(cls, profile_id: str, db: AsyncSession):
        """Builds or rebuilds the FAISS index for a specific profile_id from the DB."""
        stmt = select(BannedTopicEmbedding).where(
            BannedTopicEmbedding.profile_id == profile_id
        )
        result = await db.execute(stmt)
        embeddings = result.scalars().all()

        if not embeddings:
            cls._indices.pop(profile_id, None)
            return

        dim = len(embeddings[0].embedding)
        index = faiss.IndexFlatIP(dim)

        vectors = []
        labels  = []

        for emb in embeddings:
            vec = np.array(emb.embedding, dtype=np.float32)
            vec_2d = vec.reshape(1, -1)
            faiss.normalize_L2(vec_2d)
            vectors.append(vec_2d[0])
            labels.append(emb.topic_label)

        vector_matrix = np.vstack(vectors)
        index.add(vector_matrix)

        cls._indices[profile_id] = (index, labels)
        logger.info(f"Loaded {len(vectors)} FAISS embeddings for profile {profile_id}")

    @classmethod
    async def get_or_create_index(
        cls, profile_id: str, db: AsyncSession
    ) -> tuple[faiss.IndexFlatIP, list[str]] | None:
        if profile_id not in cls._indices:
            await cls.reload_index(profile_id, db)
        return cls._indices.get(profile_id)

    @classmethod
    def encode(cls, text: str) -> np.ndarray:
        """
        Encode text to a normalised 768-dim embedding vector.
        Returns shape (1, 768) float32 numpy array.
        Normalisation is required for cosine similarity via IndexFlatIP.
        """
        if cls._model is None:
            cls.load_model()
        vec = cls._model.encode([text], normalize_embeddings=True)[0]
        return np.array(vec, dtype=np.float32).reshape(1, -1)

    @classmethod
    async def search(
        cls,
        text: str,
        profile_id: str,
        threshold: float,
        db: AsyncSession,
        precomputed_embedding: Optional[np.ndarray] = None
    ) -> FAISSResult:
        """
        Search the FAISS index for semantic similarity.

        Args:
            text:                  Raw text (used only if precomputed_embedding is None)
            profile_id:            Profile to search against
            threshold:             Profile-level threshold (kept for API compat)
            db:                    DB session
            precomputed_embedding: Optional pre-computed (1, 768) embedding from
                                   upstream. When provided, skips encode() call
                                   and saves ~10ms per request.

        Returns FAISSResult with three-state decision:
            score >= 0.82 → BLOCK
            score >= 0.65 → HINT
            score <  0.65 → ALLOW
        """
        index_data = await cls.get_or_create_index(profile_id, db)
        if not index_data:
            return FAISSResult(decision="ALLOW", topic=None, category="NONE", score=0.0)

        index, labels = index_data

        # Reuse upstream embedding if provided — avoids duplicate encode()
        query_vec = (
            precomputed_embedding
            if precomputed_embedding is not None
            else cls.encode(text)
        )

        scores, indices = index.search(query_vec, 1)

        best_score = float(scores[0][0])
        best_idx   = int(indices[0][0])

        if best_idx < 0:
            return FAISSResult(
                decision="ALLOW", topic=None, category="NONE", score=best_score
            )

        best_topic = labels[best_idx]
        category   = get_category_for_topic(best_topic)

        if best_score >= FAISS_HARD_BLOCK_THRESHOLD:
            logger.debug(
                f"FAISS HARD BLOCK: score={best_score:.3f}, topic={best_topic[:60]}"
            )
            return FAISSResult(
                decision="BLOCK", topic=best_topic, category=category, score=best_score
            )
        elif best_score >= FAISS_SOFT_BLOCK_THRESHOLD:
            logger.debug(
                f"FAISS SOFT HINT: score={best_score:.3f}, topic={best_topic[:60]}"
            )
            return FAISSResult(
                decision="HINT", topic=best_topic, category=category, score=best_score
            )
        else:
            return FAISSResult(
                decision="ALLOW", topic=None, category="NONE", score=best_score
            )