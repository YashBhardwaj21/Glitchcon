"""
app/pipeline/stage2_classifier.py

Stage 2A -- Local LogisticRegression classifier on mpnet-base-v2 embeddings.

Decision logic:
    conf >= CONFIDENT_THRESHOLD and category != NONE  ->  BLOCK (skip FAISS + LLM)
    conf >= ESCALATE_THRESHOLD  and conf < CONFIDENT  ->  HINT  (escalate to LLM)
    conf <  ESCALATE_THRESHOLD                        ->  ALLOW (pass through)

The embedding model loaded here must match the model used during training.
Both this classifier and the FAISS index share the same SentenceTransformer
instance loaded at startup -- no duplicate model weights in memory.
"""

import logging
import pickle
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Must match EMBEDDING_MODEL in scripts/train_classifier.py
EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"

CLASSIFIER_PATH = "data/classifier.pkl"


class Stage2Classifier:
    _clf                = None
    _le                 = None
    _confident_threshold: float = 0.80
    _escalate_threshold:  float = 0.40
    _embedding_model:     str   = EMBEDDING_MODEL
    _loaded:              bool  = False

    @classmethod
    def load(cls) -> bool:
        """
        Load classifier.pkl from disk. Called once at startup via lifespan.
        Returns True if loaded, False if pkl missing (pipeline degrades gracefully).
        """
        if not os.path.exists(CLASSIFIER_PATH):
            logger.warning(
                "classifier.pkl not found at %s -- Stage 2A disabled. "
                "Run: python scripts/build_training_data.py && python scripts/train_classifier.py",
                CLASSIFIER_PATH,
            )
            return False

        try:
            with open(CLASSIFIER_PATH, "rb") as f:
                artifact = pickle.load(f)

            cls._clf                 = artifact["clf"]
            cls._le                  = artifact["le"]
            cls._confident_threshold = artifact.get("confident_threshold", 0.80)
            cls._escalate_threshold  = artifact.get("escalate_threshold",  0.40)
            cls._embedding_model     = artifact.get("embedding_model", EMBEDDING_MODEL)
            cls._loaded              = True

            cv_f1 = artifact.get("cv_f1_mean", 0.0)
            n     = artifact.get("num_examples", 0)
            cats  = artifact.get("categories", [])

            logger.info(
                "Stage2Classifier loaded: model=%s examples=%d cv_f1=%.3f "
                "categories=%s confident=%.2f escalate=%.2f",
                cls._embedding_model, n, cv_f1, cats,
                cls._confident_threshold, cls._escalate_threshold,
            )

            if cls._embedding_model != EMBEDDING_MODEL:
                logger.warning(
                    "Classifier pkl trained with '%s' but stage2_classifier.py "
                    "expects '%s'. Retrain the classifier.",
                    cls._embedding_model, EMBEDDING_MODEL,
                )

            return True

        except Exception as e:
            logger.error("Failed to load classifier.pkl: %s", e)
            cls._loaded = False
            return False

    @classmethod
    def predict(cls, embedding) -> Optional[dict]:
        """
        Run classifier on a pre-computed embedding vector.

        Args:
            embedding: numpy array of shape (768,) from mpnet-base-v2

        Returns:
            dict with keys: decision, category, confidence, hint
            or None if classifier is not loaded
        """
        if not cls._loaded or cls._clf is None:
            return None

        try:
            import numpy as np
            vec = np.array(embedding).reshape(1, -1)

            proba     = cls._clf.predict_proba(vec)[0]
            class_idx = int(proba.argmax())
            conf      = float(proba[class_idx])
            category  = cls._le.classes_[class_idx]

            if conf >= cls._confident_threshold and category != "NONE":
                decision = "BLOCK"
                hint     = None
            elif conf >= cls._escalate_threshold:
                decision = "HINT"
                hint     = f"classifier suspects {category} (conf:{conf:.2f})"
            else:
                decision = "ALLOW"
                hint     = None

            return {
                "decision":   decision,
                "category":   category,
                "confidence": conf,
                "hint":       hint,
            }

        except Exception as e:
            logger.error("Stage2Classifier.predict failed: %s", e)
            return None