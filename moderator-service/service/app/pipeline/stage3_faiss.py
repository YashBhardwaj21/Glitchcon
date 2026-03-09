import faiss
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sentence_transformers import SentenceTransformer

from app.db.models import BannedTopicEmbedding
from app.core.logging import logger

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
    async def search(cls, text: str, profile_id: str, threshold: float, db: AsyncSession) -> tuple[bool, str | None, float]:
        """
        Searches the FAISS index for semantic similarity.
        Returns: (is_blocked, matched_topic_label, confidence_score)
        """
        index_data = await cls.get_or_create_index(profile_id, db)
        if not index_data:
            return False, None, 0.0
            
        index, labels = index_data
        query_vec = cls.encode(text)
        
        # Look for top 1 match
        scores, indices = index.search(query_vec, 1)
        
        best_score = float(scores[0][0])
        best_idx = int(indices[0][0])
        
        if best_idx >= 0 and best_score >= threshold:
            return True, labels[best_idx], best_score
            
        return False, None, best_score
