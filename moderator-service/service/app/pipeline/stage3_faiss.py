import faiss
import numpy as np
from typing import NamedTuple, Literal
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
    topic:  matched banned topic label (or None when decision is ALLOW)
    category: violation category (e.g. SCAM, HATE_SPEECH)
    score:  cosine similarity (0.0–1.0)
    """
    decision: Literal["BLOCK", "HINT", "ALLOW"]
    topic: str | None
    category: str
    score: float


TOPIC_CATEGORY_MAP = {
    # Crypto/scam
    "cryptocurrency investment scam"          : "SCAM",
    "bitcoin ethereum pump and dump"          : "SCAM",
    "send money get rich quick"               : "SCAM",
    "crypto wallet private key seed phrase"   : "SCAM",

    # Self harm
    "instructions on how to commit suicide"   : "SELF_HARM",
    "how many pills to take to overdose"      : "SELF_HARM",
    "methods to end your life"                : "SELF_HARM",
    "want to die need help ending it"         : "SELF_HARM",

    # Hate speech
    "extreme racism hate speech"              : "HATE_SPEECH",
    "racist slurs targeting black"            : "HATE_SPEECH",
    "casteist slurs against dalit"            : "HATE_SPEECH",
    "communal hatred between hindus muslims"  : "HATE_SPEECH",
    "antisemitic content targeting jewish"    : "HATE_SPEECH",

    # Threats
    "violent threats to murder assault"       : "THREAT",
    "i will find you and kill you"            : "THREAT",
    "bomb explosion attack planning"          : "THREAT",

    # CSAM
    "child sexual abuse material"             : "CSAM",
    "sexual content involving underage"       : "CSAM",

    # PII/Phishing
    "phishing scams stealing credentials"     : "PII",
    "otp bank account password steal"         : "PII",
    "fake kyc aadhaar pan verification"       : "PII",

    # Drugs
    "drug dealing illegal substance"          : "SCAM",
    "buy weed cocaine heroin online"          : "SCAM",
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
            logger.info("Loading sentence-transformers model...")
            # Use paraphrase-multilingual-MiniLM-L12-v2 (384 dims, supports 50+ languages)
            cls._model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            logger.info("sentence-transformers model loaded.")

    @classmethod
    async def reload_index(cls, profile_id: str, db: AsyncSession):
        """Builds or rebuilds the FAISS index for a specific profile_id from the DB."""
        stmt = select(BannedTopicEmbedding).where(BannedTopicEmbedding.profile_id == profile_id)
        result = await db.execute(stmt)
        embeddings = result.scalars().all()

        if not embeddings:
            cls._indices.pop(profile_id, None)
            return

        dim = len(embeddings[0].embedding)
        # Inner Product for Cosine Similarity (vectors must be normalized)
        index = faiss.IndexFlatIP(dim)

        vectors = []
        labels = []

        for emb in embeddings:
            vec = np.array(emb.embedding, dtype=np.float32)
            # Normalize vector in-place
            vec_2d = vec.reshape(1, -1)
            faiss.normalize_L2(vec_2d)
            vectors.append(vec_2d[0])
            labels.append(emb.topic_label)

        vector_matrix = np.vstack(vectors)
        index.add(vector_matrix)

        cls._indices[profile_id] = (index, labels)
        logger.info(f"Loaded {len(vectors)} FAISS embeddings for profile {profile_id}")

    @classmethod
    async def get_or_create_index(cls, profile_id: str, db: AsyncSession) -> tuple[faiss.IndexFlatIP, list[str]] | None:
        if profile_id not in cls._indices:
            await cls.reload_index(profile_id, db)
        return cls._indices.get(profile_id)

    @classmethod
    def encode(cls, text: str) -> np.ndarray:
        if cls._model is None:
            cls.load_model()
        vec = cls._model.encode([text])[0]
        vec_np = np.array(vec, dtype=np.float32).reshape(1, -1)
        faiss.normalize_L2(vec_np)
        return vec_np

    @classmethod
    async def search(cls, text: str, profile_id: str, threshold: float, db: AsyncSession) -> FAISSResult:
        """
        Searches the FAISS index for semantic similarity.

        Uses a two-threshold approach:
          - score >= FAISS_HARD_BLOCK_THRESHOLD (0.82) → BLOCK immediately
          - score in [FAISS_SOFT_BLOCK_THRESHOLD (0.65), 0.82) → HINT to LLM
          - score < 0.65 → ALLOW (topic not detected)

        Note: the `threshold` parameter from the profile config is retained for
        API compatibility but the module-level constants take precedence now.
        """
        index_data = await cls.get_or_create_index(profile_id, db)
        if not index_data:
            return FAISSResult(decision="ALLOW", topic=None, category="NONE", score=0.0)

        index, labels = index_data
        query_vec = cls.encode(text)

        # Look for top 1 match
        scores, indices = index.search(query_vec, 1)

        best_score = float(scores[0][0])
        best_idx = int(indices[0][0])

        if best_idx < 0:
            return FAISSResult(decision="ALLOW", topic=None, category="NONE", score=best_score)

        best_topic = labels[best_idx]
        category = get_category_for_topic(best_topic)

        if best_score >= FAISS_HARD_BLOCK_THRESHOLD:
            logger.debug(f"FAISS HARD BLOCK: score={best_score:.3f}, topic={best_topic[:60]}")
            return FAISSResult(decision="BLOCK", topic=best_topic, category=category, score=best_score)
        elif best_score >= FAISS_SOFT_BLOCK_THRESHOLD:
            logger.debug(f"FAISS SOFT HINT: score={best_score:.3f}, topic={best_topic[:60]}")
            return FAISSResult(decision="HINT", topic=best_topic, category=category, score=best_score)
        else:
            return FAISSResult(decision="ALLOW", topic=None, category="NONE", score=best_score)
