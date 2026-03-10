"""
scripts/train_classifier.py

Trains a calibrated LogisticRegression classifier on top of
paraphrase-multilingual-mpnet-base-v2 embeddings (768-dim, more accurate
than MiniLM-L12-v2 at the cost of slightly more memory).

Run AFTER build_training_data.py:
    python scripts/train_classifier.py

Output:
    data/classifier.pkl         -- saved classifier + label encoder + metadata
    data/classifier_report.txt  -- per-category F1 and CV scores
"""

import json
import pickle
import os
import numpy as np
from collections import Counter

from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report


TRAINING_DATA_PATH = "data/training_data.json"
CLASSIFIER_PATH    = "data/classifier.pkl"
REPORT_PATH        = "data/classifier_report.txt"

# Upgrade from MiniLM-L12-v2 (384-dim) to mpnet-base-v2 (768-dim)
# Better semantic understanding especially for indirect phrasing
# Model size: ~420MB vs 118MB | Inference: ~10ms vs ~3ms on CPU
EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"

# Above CONFIDENT_THRESHOLD and category != NONE -> BLOCK immediately (skip LLM)
# Between ESCALATE_THRESHOLD and CONFIDENT_THRESHOLD -> HINT (send to LLM)
# Below ESCALATE_THRESHOLD -> ALLOW
CONFIDENT_THRESHOLD = 0.80
ESCALATE_THRESHOLD  = 0.40   # lowered from 0.50 -- reduces wasted LLM calls


def load_data(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["texts"], data["labels"]


def train():
    print("=" * 60)
    print("  MODERATION CLASSIFIER TRAINING")
    print("  Model: paraphrase-multilingual-mpnet-base-v2")
    print("=" * 60)

    # ── Load data ─────────────────────────────────────────────────────────────
    if not os.path.exists(TRAINING_DATA_PATH):
        print(f"\nERROR: {TRAINING_DATA_PATH} not found.")
        print("Run: python scripts/build_training_data.py first\n")
        return

    texts, labels = load_data(TRAINING_DATA_PATH)
    counts = Counter(labels)
    print(f"\nLoaded {len(texts)} examples across {len(counts)} categories:")
    for cat, count in sorted(counts.items()):
        bar = "#" * (count // 5)
        print(f"  {cat:<20} {count:>4}  {bar}")

    if min(counts.values()) < 30:
        print("\nWARNING: At least one category has fewer than 30 examples.")
        print("         CV scores will be unreliable. Add more data first.")

    # ── Generate embeddings ───────────────────────────────────────────────────
    print(f"\nLoading embedding model: {EMBEDDING_MODEL}")
    print("(First run downloads ~420MB -- subsequent runs use cache)")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("\nGenerating embeddings...")
    X = model.encode(texts, show_progress_bar=True, batch_size=32, normalize_embeddings=True)
    print(f"Embeddings shape: {X.shape}  (expecting N x 768)")

    # ── Encode labels ─────────────────────────────────────────────────────────
    le = LabelEncoder()
    y  = le.fit_transform(labels)
    print(f"\nLabel classes: {list(le.classes_)}")

    # ── Base classifier ───────────────────────────────────────────────────────
    print("\nTraining LogisticRegression base classifier...")
    base_clf = LogisticRegression(
        max_iter=1000,
        C=1.0,
        class_weight="balanced",
        solver="lbfgs",
        random_state=42,
    )

    # ── Calibration wrapper ───────────────────────────────────────────────────
    # Isotonic calibration maps raw probabilities to well-calibrated ones.
    # A 0.80 confidence will actually correspond to ~80% precision after this.
    print("Wrapping with isotonic calibration (cv=3)...")
    clf = CalibratedClassifierCV(base_clf, method="isotonic", cv=3)
    clf.fit(X, y)
    print("Training complete.")

    # ── Cross-validation on base classifier ──────────────────────────────────
    print("\nRunning 5-fold cross-validation on base classifier...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(base_clf, X, y, cv=cv, scoring="f1_weighted")
    print(f"CV F1 (weighted): {scores.mean():.3f} +/- {scores.std():.3f}")
    print(f"Individual folds: {[round(s, 3) for s in scores]}")

    if scores.mean() < 0.75:
        print("\nWARNING: CV F1 below 0.75 -- add more training examples.")
        print("         Aim for 100+ per violation category.")
    elif scores.mean() < 0.85:
        print("\nGOOD: Classifier is usable. More data will push it further.")
    else:
        print("\nEXCELLENT: Classifier is production-ready (CV F1 >= 0.85).")

    # ── Per-category report on training set ──────────────────────────────────
    y_pred = clf.predict(X)
    report = classification_report(y, y_pred, target_names=le.classes_)
    print("\nPer-category (training set -- use CV F1 for real estimate):")
    print(report)

    # ── Threshold sensitivity check ───────────────────────────────────────────
    print(f"Threshold sensitivity at CONFIDENT={CONFIDENT_THRESHOLD} ESCALATE={ESCALATE_THRESHOLD}:")
    proba = clf.predict_proba(X)
    above_confident = (proba.max(axis=1) >= CONFIDENT_THRESHOLD).sum()
    in_hint_zone    = ((proba.max(axis=1) >= ESCALATE_THRESHOLD) &
                       (proba.max(axis=1) <  CONFIDENT_THRESHOLD)).sum()
    below_escalate  = (proba.max(axis=1) <  ESCALATE_THRESHOLD).sum()
    n = len(X)
    print(f"  >= {CONFIDENT_THRESHOLD} (BLOCK immediately) : {above_confident:>4} / {n}  "
          f"({100*above_confident/n:.0f}%)")
    print(f"  {ESCALATE_THRESHOLD}-{CONFIDENT_THRESHOLD} (HINT to LLM)     : {in_hint_zone:>4} / {n}  "
          f"({100*in_hint_zone/n:.0f}%)")
    print(f"  < {ESCALATE_THRESHOLD} (ALLOW pass-through)  : {below_escalate:>4} / {n}  "
          f"({100*below_escalate/n:.0f}%)")

    # ── Save ──────────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(CLASSIFIER_PATH), exist_ok=True)

    artifact = {
        "clf":                 clf,
        "le":                  le,
        "confident_threshold": CONFIDENT_THRESHOLD,
        "escalate_threshold":  ESCALATE_THRESHOLD,
        "embedding_model":     EMBEDDING_MODEL,
        "num_examples":        len(texts),
        "categories":          list(le.classes_),
        "cv_f1_mean":          float(scores.mean()),
        "cv_f1_std":           float(scores.std()),
    }

    with open(CLASSIFIER_PATH, "wb") as f:
        pickle.dump(artifact, f)

    report_text = (
        f"Model         : {EMBEDDING_MODEL}\n"
        f"Examples      : {len(texts)}\n"
        f"CV F1 (mean)  : {scores.mean():.3f}\n"
        f"CV F1 (std)   : {scores.std():.3f}\n"
        f"Folds         : {[round(s, 3) for s in scores]}\n\n"
        f"Thresholds:\n"
        f"  confident   : {CONFIDENT_THRESHOLD}  (BLOCK immediately)\n"
        f"  escalate    : {ESCALATE_THRESHOLD}   (HINT to LLM)\n\n"
        + report
    )

    with open(REPORT_PATH, "w") as f:
        f.write(report_text)

    print(f"\nClassifier saved : {CLASSIFIER_PATH}")
    print(f"Report saved     : {REPORT_PATH}")
    print("\nIMPORTANT: Update stage2_classifier.py -- change EMBEDDING_MODEL")
    print("           to 'paraphrase-multilingual-mpnet-base-v2'")
    print("           and update main.py FaissService.load_model() call")
    print("           to use the same model name.\n")
    print("Next step: restart uvicorn -- it loads classifier.pkl at startup.\n")


if __name__ == "__main__":
    train()