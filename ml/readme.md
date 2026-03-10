# GBA_1 — AI Chat Moderation Service

Multilingual content moderation microservice with a 4-stage deterministic and semantic pipeline. Designed for real-time community chat moderation across English, Hindi, and Hinglish content.

**Version:** 0.3.0 | **Classifier CV F1:** 0.867 ± 0.034 | **Test Suite Score:** 93.8% (64 tests)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Pipeline](#pipeline)
4. [Models](#models)
5. [Data and Training](#data-and-training)
6. [Repository Structure](#repository-structure)
7. [Setup and Installation](#setup-and-installation)
8. [Configuration](#configuration)
9. [API Reference](#api-reference)
10. [Running Tests](#running-tests)
11. [Performance](#performance)
12. [Known Issues](#known-issues)

---

## Overview

GBA_1 inspects incoming chat messages and returns a structured moderation decision — `BLOCK` or `ALLOW` — along with a violation category, confidence score, stage attribution, and a localised user-facing feedback message.

The primary design constraint is minimising external semantic cycles. The architecture achieves high efficiency and low latency by placing a deterministic pre-filter and a locally trained classifier ahead of the semantic stages, reducing deep inference traffic by approximately 85%.

### Supported Violation Categories

| Category | Description |
|---|---|
| `HATE_SPEECH` | Racial slurs, casteism, communal incitement, gender discrimination, dehumanisation, coded hate language |
| `PROFANITY` | Severe English profanity, Hindi/Hinglish slurs, leet-speak and separator bypasses |
| `THREAT` | Direct and indirect personal threats, doxxing, conditional threats, Hindi location threats |
| `SCAM` | Investment fraud, crypto pump schemes, phishing, OTP theft, lottery fraud, job scams |
| `SELF_HARM` | Direct method seeking, passive ideation, planning signals, stockpiling language |
| `PII` | Indian mobile numbers, Aadhaar, PAN, email, UPI handles, card numbers, API keys |
| `SPAM` | Rate-limit violations via Redis sliding window per user per profile |
| `NONE` | Clean message — no violation detected |

---

## Architecture

### Technology Stack

| Component | Technology |
|---|---|
| API Framework | FastAPI (Python 3.11+) with async request handling |
| Database | PostgreSQL via SQLAlchemy AsyncSession |
| Cache | Redis (asyncio) — keyword sets, spam counters, feedback cache |
| Vector Store | FAISS — in-memory cosine similarity index per profile |
| Embedding Model | `paraphrase-multilingual-MiniLM-L12-v2` (384-dim vectors) |
| Local Classifier | LogisticRegression (scikit-learn 1.5+) on MiniLM embeddings |
| LLM Provider | Groq (default) — configurable via `LLM_PROVIDER` env var |
| Language Detection | langdetect with custom Devanagari and emoji pre-checks |

---

## Pipeline

Every request passes through the pipeline sequentially. Each stage can short-circuit by returning a `BLOCK`, skipping all subsequent stages. This is what keeps median latency under 15ms for the majority of traffic.

```
Incoming Request
      |
      v
  Stage 0   Language Detection                     ~2ms
      |      langdetect + Unicode/emoji guards
      |      Output: LanguageContext (code, normalised_text, is_transliterated)
      |
      v
  Stage 1   Deterministic Pre-filter               ~5ms
      |      1. Spam flood     — Redis ZSET sliding window per user
      |      2. PII regex      — phone, Aadhaar, PAN, UPI, email, card, API key
      |      3. Profanity/Hate — hardcoded sets + leet normalisation
      |      4. Keyword check  — Redis TF-IDF SETs (hard BLOCK / soft HINT)
      |
      |----  BLOCK (conf=1.0) → return immediately
      |
      v
  Stage 2A  Local Classifier                       ~3ms
      |      LogisticRegression on MiniLM embeddings
      |      conf ≥ 0.80 and category != NONE  →  BLOCK
      |      conf   0.50 – 0.80               →  HINT (escalate to LLM)
      |      conf < 0.50                      →  ALLOW (pass through)
      |
      |----  BLOCK (conf ≥ 0.80) → return immediately
      |
      v
  Stage 3   FAISS Semantic Search                  ~10ms
      |      Cosine similarity vs per-profile topic index
      |      score > hard_threshold  →  BLOCK
      |      score > soft_threshold  →  HINT
      |      Reporting context guard: academic phrasing downgrades BLOCK → HINT
      |
      |----  BLOCK (no reporting context) → return immediately
      |
      v
  Stage 2B  LLM Inference                          ~600–900ms
            Called only when classifier is uncertain AND FAISS did not hard block
            Receives: message + faiss_hint + classifier_hint + keyword_hint
            ~10–15% of total traffic reaches this stage
```

### Stage 0 — Language Detection

Uses `langdetect` with two pre-checks to prevent crashes on edge-case inputs: pure emoji/symbol strings default to `en`, and ASCII strings under 4 characters bypass langdetect. Romanised Hindi (Hinglish) is detected heuristically — if langdetect returns `en` but common Hinglish tokens are present, the context is marked `hi-en` (transliterated).

### Stage 1 — Deterministic Pre-filter

**Spam:** Redis sorted set per `profile_id:user_id`. Atomically removes entries outside the window, adds the current timestamp, and counts. If count exceeds `spam_limit` the request is blocked.

**PII:** Nine compiled regex patterns covering Indian-specific identifiers. Runs on the original (un-normalised) text.

**Profanity/Hate/Threat:** Text is normalised before matching using four transformations:
- Leet-speak substitution: `@→a`, `3→e`, `9→g`, `4→a`, `0→o`, `$→s` etc.
- Collapse 3+ repeated characters: `fuuuuck → fuck`
- Remove spaces between single letters: `f u c k → fuck`
- Strip separator characters between letter clusters: `b*tch → bitch`, `f.u.c.k.i.n.g → fucking`

Four hardcoded sets are checked in priority order: `HARD_HI_THREAT`, `HARD_EN_HATE_SPEECH`, `HARD_EN_PROFANITY`, `HARD_HI_PROFANITY`.

### Stage 2A — Local Classifier

LogisticRegression trained on MiniLM sentence embeddings. Loaded once at startup from `data/classifier.pkl`. Predicts across 5 categories with calibrated probability outputs.

| Confidence | Action |
|---|---|
| ≥ 0.80 and category != NONE | BLOCK immediately — skip FAISS and LLM |
| 0.50 – 0.80 | HINT — classifier suspicion passed as context to LLM |
| < 0.50 | ALLOW — classifier confident the message is clean |

If `classifier.pkl` is not present, Stage 2A returns ALLOW and the pipeline continues gracefully to FAISS and LLM.

### Stage 3 — FAISS Semantic Search

Per-profile in-memory FAISS FlatIP index of violation topic embeddings. Topics are short descriptive phrases (e.g. `"crypto investment guaranteed returns scam"`) embedded with MiniLM and stored in the database. Two thresholds are configured per profile: hard (BLOCK) and soft (HINT).

The **reporting context guard** prevents false positives on analytical messages. If FAISS wants to hard block but the message contains phrases like `"is a serious issue"`, `"research shows"`, `"should I report"` — the BLOCK is downgraded to HINT and passed to the LLM instead.

### Stage 2B — Deep Semantic Inference

Only invoked when the classifier is in the uncertain range (0.50–0.80) and FAISS did not hard block. Prompt includes all available hints from previous stages. Returns structured JSON: `decision`, `category`, `confidence`, `violated_rule`, `feedback_message`.

---

## Models

### paraphrase-multilingual-MiniLM-L12-v2

| Property | Value |
|---|---|
| Architecture | 12-layer MiniLM transformer encoder |
| Output | 384-dimensional float32 embedding |
| Languages | 50+ including English, Hindi, romanised Hindi |
| Max input length | 128 tokens |
| Inference time (CPU) | ~2–5ms after warm-up |
| Model size | 118MB |
| Usage | Shared between FAISS index construction, FAISS queries, and classifier training |

Chosen because it is the smallest multilingual sentence-transformer that produces cross-lingual embeddings. English text and its Hindi equivalent map to nearby vectors — meaning a FAISS index built on English phrases returns relevant results for Hindi queries on the same topic.

### LogisticRegression Classifier

| Property | Value |
|---|---|
| Algorithm | LogisticRegression, lbfgs solver, multinomial |
| Input | 384-dim MiniLM embedding |
| Classes | HATE_SPEECH, NONE, SCAM, SELF_HARM, THREAT |
| Class weighting | balanced |
| Regularisation | L2, C=1.0 |
| Training examples | 446 |
| CV F1 (weighted, 5-fold) | 0.867 ± 0.034 |
| Inference time | < 3ms |

Linear regression on top of MiniLM embeddings is intentional. The embedding model handles non-linear feature extraction — a linear boundary in 384-dimensional space is sufficient and gives well-calibrated probability outputs needed for the confidence thresholds.

The 0.99 training accuracy vs 0.867 CV F1 discrepancy is expected. Training accuracy measures memorisation of seen data. CV F1 on unseen folds is the real performance estimate.

---

## Data and Training

Training data is constructed manually in `scripts/build_training_data.py`. Manual construction is used over scraped datasets to avoid label noise and Western-language bias that degrades performance on Indian-language content.

### Dataset Breakdown

| Category | Examples | Coverage |
|---|---|---|
| THREAT | 82 | Direct threats, veiled threats, doxxing, conditional threats, cyber threats, Hindi/Hinglish location threats |
| HATE_SPEECH | 89 | Racial dehumanisation, India communal hate, casteism, gender discrimination, LGBTQ hate, incitement, coded hate |
| SCAM | 75 | Investment/trading fraud, crypto pump, job scams, phishing/OTP theft, lottery fraud, romance scams, Hinglish variants |
| SELF_HARM | 74 | Direct method seeking, passive ideation, planning signals, curiosity-framed requests, Hindi variants |
| NONE | 130 | Greetings, technical questions, sports/entertainment, academic/reporting context traps, medical context, fiction |
| **TOTAL** | **446** | After deduplication |

The `NONE` class is the largest and most deliberately diverse. It includes examples with dangerous-sounding vocabulary in safe contexts — research papers discussing suicide rates, news reports on hate crimes, medical queries, fiction containing threats. This teaches the model the difference between discussing a topic and perpetuating it, which is the primary source of false positives in naive classifiers.

### Training Steps

```bash
# 1. Generate labelled training data
python scripts/build_training_data.py
# writes: data/training_data.json

# 2. Train and evaluate classifier
python scripts/train_classifier.py
# writes: data/classifier.pkl
#         data/classifier_report.txt
# CV F1 >= 0.85 is considered production-ready
```

---

## Repository Structure

```
service/
  app/
    main.py                      FastAPI app, lifespan startup (model warm-up)
    api/v1/                      Route handlers: moderate, profiles, admin, feedback, health
    pipeline/
      stage0_language.py         Language detection and normalisation
      stage1_prefilter.py        Deterministic keyword, PII, profanity, spam checks
      stage2_classifier.py       Local LogisticRegression classifier (Stage 2A)
      stage2_llm.py              Deep inference wrapper (Stage 2B)
      stage3_faiss.py            FAISS semantic similarity search
    inference/
      factory.py                 Inference provider factory
    i18n/
      detector.py                Language detection with Unicode and emoji guards
      profanity_lists/           Per-language word lists (hi, ta, te, kn, ml)
    schemas/                     Pydantic models: ModerationRequest, ModerationResponse
    cache/                       Redis-backed feedback template service
    db/                          SQLAlchemy models and session management
    core/                        Config (settings), structured logging
  scripts/
    build_training_data.py       Generates data/training_data.json (~700 raw examples)
    train_classifier.py          Trains and saves data/classifier.pkl
    seed_datasets.py             Seeds Redis keyword sets and FAISS topics
  data/
    classifier.pkl               Trained classifier artifact
    training_data.json           Full labelled dataset for retraining
    classifier_report.txt        Per-category F1 from last training run
  test_categorization.ps1        Test suite (64 tests)
```

---

## Setup and Installation

### Prerequisites

- Python 3.11+
- PostgreSQL (schema migrated)
- Redis on default port 6379
- `.env` file in `service/` with required variables

### Install and Run

```powershell
# Activate virtual environment
& "C:\Users\Yash Bhardwaj\Desktop\Glitchcon\aimod\Scripts\Activate.ps1"

# Navigate to service directory
cd "C:\Users\Yash Bhardwaj\Desktop\Glitchcon\ml\moderator-service\service"

# Install dependencies
pip install -r requirements.txt

# Generate training data and train classifier
python scripts/build_training_data.py
python scripts/train_classifier.py

# Seed Redis keyword sets and FAISS topics
python scripts/seed_datasets.py

# Start the service
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### Expected Startup Output

```
Starting AI Moderation Microservice
Stage2Classifier loaded successfully.
FAISS pre-warming complete for N profiles.
```

---

## Configuration

### Environment Variables

| Variable | Description |
|---|---|
| `PRIMARY_PROVIDER` | `system_default` |
| `API_SECRET_KEY` | System API key |
| `DATABASE_URL` | PostgreSQL async connection string |
| `REDIS_URL` | Redis connection string (default: `redis://localhost:6379`) |
| `CORS_ORIGINS` | Comma-separated allowed origins or `*` |

### Profile Configuration

Each profile configures pipeline behaviour per community. Key fields:

| Field | Description |
|---|---|
| `spam_limit` | Max messages per user within `spam_window_s` (set to `5` for tests) |
| `spam_window_s` | Sliding window duration in seconds (set to `60` for tests) |
| `faiss_threshold` | Hard cosine similarity threshold for FAISS BLOCK |
| `supported_languages` | Language codes enabled for this profile |

---

## API Reference

### POST /v1/moderate/

```
Header: X-API-Key: <key>
Content-Type: application/json
```

**Request**

```json
{
  "message":    "Text to moderate",
  "profile_id": "default_test_profile",
  "user_id":    "user_123",
  "metadata":   {}
}
```

**Response**

```json
{
  "decision":          "BLOCK",
  "category":          "THREAT",
  "detected_language": "en",
  "stage_triggered":   "stage2_classifier",
  "confidence":        0.993,
  "violated_rule":     "threat",
  "reason":            "Blocked by local classifier: THREAT",
  "feedback_message":  "Please refrain from making threats...",
  "latency_ms": {
    "stage0_lang":  2,
    "stage1":       4,
    "inference_source": "local_classifier"
  }
}
```

### Other Endpoints

| Endpoint | Description |
|---|---|
| `GET /v1/health` | Service health check |
| `GET /v1/profiles/{profile_id}` | Retrieve profile configuration |
| `POST /v1/profiles/` | Create a new moderation profile |
| `GET /v1/admin/reload-faiss/{profile_id}` | Hot-reload FAISS index without restart |
| `POST /v1/feedback/` | Submit or update feedback templates |
| `GET /docs` | Swagger UI |

---

## Running Tests

```powershell
# Standard suite — 64 tests, established messages
.\test_categorization.ps1

# Verbose output
.\test_categorization.ps1 -Verbose
```

### Test Level Structure

| Level | Description |
|---|---|
| L1 | Clean messages — all must ALLOW. Includes dangerous-sounding vocabulary in safe context |
| L2 | Obvious violations — Stage 1 should catch deterministically |
| L3 | Indirect violations — classifier and FAISS must detect |
| L4 | Adversarial bypasses — leet speak, code-switching, framing tricks |
| L5 | Edge cases — false positive traps, spam flood, quoting violations to report them |

---

## Performance

### Test Suite Results

| Test Suite | 93.8% | Verified on 64 standardized test cases |

### Latency by Path

| Path | Typical Latency |
|---|---|
| Stage 1 BLOCK (deterministic) | 5–10ms |
| Stage 2A BLOCK (classifier confident) | 8–15ms |
| Stage 3 BLOCK (FAISS hard block) | 18–30ms |
| Stage 2B (LLM required) | 600–950ms |
| ALLOW — clean message, no hints | 5–12ms |

The selective use of deep semantic inference ensures low latency and cost efficiency:

- ~70% of semantic violations blocked by classifier at ≥ 0.80 confidence
- ~15% of messages allowed by classifier at < 0.50 confidence without LLM
- ~10–15% of traffic reaches the LLM (uncertain classifier + no FAISS hard block)

---

