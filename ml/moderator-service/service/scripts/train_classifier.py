"""
scripts/train_classifier.py

Trains a LogisticRegression classifier on top of paraphrase-multilingual-MiniLM-L12-v2
embeddings. Uses the same model your FAISS index already loads — zero extra memory at
runtime since the model is shared.

Run AFTER build_training_data.py:
    python scripts/train_classifier.py

Output:
    data/classifier.pkl   — saved classifier + label encoder
    data/classifier_report.txt — per-category F1 scores
"""

import json
import pickle
import os
import numpy as np
from collections import Counter

from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report


TRAINING_DATA_PATH = "data/training_data.json"
CLASSIFIER_PATH    = "data/classifier.pkl"
REPORT_PATH        = "data/classifier_report.txt"
EMBEDDING_MODEL    = "paraphrase-multilingual-MiniLM-L12-v2"

# Confidence threshold: above this → classifier decision is final (no LLM)
# Below this → escalate to LLM for ambiguous cases
CONFIDENT_THRESHOLD = 0.80
ESCALATE_THRESHOLD  = 0.50


def load_data(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["texts"], data["labels"]


def train():
    print("=" * 60)
    print("  MODERATION CLASSIFIER TRAINING")
    print("=" * 60)

    # ── Load data ─────────────────────────────────────────────────
    if not os.path.exists(TRAINING_DATA_PATH):
        print(f"\nERROR: {TRAINING_DATA_PATH} not found.")
        print("Run: python scripts/build_training_data.py first\n")
        return

    texts, labels = load_data(TRAINING_DATA_PATH)
    counts = Counter(labels)
    print(f"\nLoaded {len(texts)} examples across {len(counts)} categories:")
    for cat, count in sorted(counts.items()):
        print(f"  {cat:<20} {count}")

    # ── Generate embeddings ───────────────────────────────────────
    print(f"\nLoading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("Generating embeddings (this takes ~10-30 seconds on CPU)...")
    X = model.encode(texts, show_progress_bar=True, batch_size=32)
    print(f"Embeddings shape: {X.shape}")

    # ── Encode labels ─────────────────────────────────────────────
    le = LabelEncoder()
    y = le.fit_transform(labels)
    print(f"\nLabel classes: {list(le.classes_)}")

    # ── Train classifier ──────────────────────────────────────────
    print("\nTraining LogisticRegression classifier...")
    clf = LogisticRegression(
        max_iter=1000,
        C=1.0,
        class_weight="balanced",   # handles unequal category sizes
        solver="lbfgs",            # lbfgs handles multiclass natively in sklearn 1.5+
        random_state=42,
    )
    clf.fit(X, y)
    print("Training complete.")

    # ── Cross-validation ──────────────────────────────────────────
    print("\nRunning 5-fold cross-validation...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(clf, X, y, cv=cv, scoring="f1_weighted")
    print(f"CV F1 (weighted): {scores.mean():.3f} ± {scores.std():.3f}")

    if scores.mean() < 0.75:
        print("\nWARNING: CV F1 below 0.75 — consider adding more training examples")
        print("         Especially for categories with low counts.")
    elif scores.mean() < 0.85:
        print("\nGOOD: Classifier is usable. More examples will improve further.")
    else:
        print("\nEXCELLENT: Classifier is production-ready.")

    # ── Per-category report ───────────────────────────────────────
    y_pred = clf.predict(X)
    report = classification_report(y, y_pred, target_names=le.classes_)
    print("\nPer-category performance (on training set — use CV score for real estimate):")
    print(report)

    # ── Save ─────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(CLASSIFIER_PATH), exist_ok=True)

    with open(CLASSIFIER_PATH, "wb") as f:
        pickle.dump({
            "clf": clf,
            "le": le,
            "confident_threshold": CONFIDENT_THRESHOLD,
            "escalate_threshold": ESCALATE_THRESHOLD,
            "embedding_model": EMBEDDING_MODEL,
            "num_examples": len(texts),
            "categories": list(le.classes_),
        }, f)

    with open(REPORT_PATH, "w") as f:
        f.write(f"CV F1: {scores.mean():.3f} ± {scores.std():.3f}\n\n")
        f.write(report)

    print(f"\nClassifier saved to: {CLASSIFIER_PATH}")
    print(f"Report saved to:     {REPORT_PATH}")
    print("\nNext step: uvicorn will load the classifier automatically on startup.")
    print("The pipeline will use it as Stage 2A before calling the LLM.\n")


if __name__ == "__main__":
    train()