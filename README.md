# AI Moderation Microservice

> **A production-grade, multilingual content moderation API** built for real-time community moderation. It combines deterministic pre-filtering with LLM semantic analysis and FAISS vector similarity to accurately classify harmful content across **English, Hindi, Tamil, Telugu, Kannada, Malayalam, and Hinglish (code-mix)**.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Architecture Overview](#architecture-overview)
- [Pipeline Layers (Stages 0–3)](#pipeline-layers-stages-03)
- [Models & AI Components](#models--ai-components)
- [Violation Categories](#violation-categories)
- [Project Structure](#project-structure)
- [Quick Start (Local Dev)](#quick-start-local-dev)
- [Environment Variables](#environment-variables)
- [Seeding the Database](#seeding-the-database)
- [Running the Service](#running-the-service)
- [Docker Deployment](#docker-deployment)
- [Testing](#testing)
- [Python SDK](#python-sdk)
- [API Reference](#api-reference)
- [Makefile Commands](#makefile-commands)

---

## Problem Statement

Online communities — especially in India — are multilingual (English, Hindi, Hinglish, Tamil, etc.) and face moderation challenges that English-only rule-based systems cannot handle:

- Code-mixed messages ("bhai maar do isko") are invisible to English keyword filters
- Bypass attempts (leet speak, dotted slurs, Devanagari script) defeat regex-based detection
- LLM-only solutions are expensive, slow (200–800 ms), and inconsistent
- Contextual nuance (sarcasm, fiction, reporting a violation) causes false positives

This service solves these problems with a tiered pipeline that dispatches to increasingly expensive stages only when necessary, targeting **< 30 ms** for 70% of messages (no LLM call) and **< 900 ms** worst case.

---

## Architecture Overview

```
Consumer App / SDK
       │
       ▼
 ┌─────────────────────────────────────────┐
 │        FastAPI Service (:8001)          │
 │  POST /v1/moderate/  ◄──── X-API-Key   │
 └─────────────┬───────────────────────────┘
               │
       ┌───────▼────────┐
       │  Stage 0       │  Language Detection + Indic Normalisation
       │  < 3 ms        │  (langdetect + custom Hinglish heuristic)
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │  Stage 1       │  Fast Pre-filter  (deterministic, < 10 ms)
       │                │  ├─ Spam sliding-window (Redis sorted sets)
       │                │  ├─ PII regex (phone, Aadhaar, PAN, email, UPI)
       │                │  ├─ Profanity library (multilingual wordlists)
       │                │  └─ Keyword sets (Redis hard/soft, per-language)
       └───────┬────────┘
         PASS  │  (70% of traffic stops here)
               │
       ┌───────▼────────┐
       │  Stage 3       │  FAISS Semantic Search  (< 20 ms)
       │                │  ├─ Cosine similarity vs. banned topic embeddings
       │                │  ├─ HARD block (score ≥ 0.82) → immediate BLOCK
       │                │  └─ SOFT hint (0.65–0.82) → pass hint to LLM
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │  Stage 2 (LLM) │  Semantic Analysis  (200–800 ms)
       │                │  ├─ Builds multilingual prompt with hints
       │                │  ├─ Calls LLM (Groq / Gemini / OpenRouter)
       │                │  ├─ Confidence gating (language-aware threshold)
       │                │  └─ Rule validation (prevents hallucinated blocks)
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │  Response      │  decision, category, confidence, feedback_message
       └────────────────┘
               │
       Celery Worker  ──► async audit logging to PostgreSQL
```

---

## Pipeline Layers (Stages 0–3)

### Stage 0 — Language Detection & Normalisation
- **File:** `app/pipeline/stage0_language.py`
- Detects language using `langdetect` with a custom heuristic for Hinglish (Hindi-English code-mix)
- Applies `IndicNormaliser` for Devanagari, Tamil, Telugu, Kannada, Malayalam scripts
- Produces a `LanguageContext` carrying: `code`, `is_transliterated`, `normalised_text`
- **Latency:** < 3 ms

### Stage 1 — Fast Pre-filter
- **File:** `app/pipeline/stage1_prefilter.py`
- **Spam check** — Redis sorted-set sliding window: if user sends > N messages in W seconds → SPAM BLOCK
- **PII check** — Regex patterns for Indian mobile numbers, Aadhaar (12-digit), PAN, email addresses, UPI IDs (bank handle whitelist), WhatsApp links, credit card numbers. Email/UPI patterns run on normalised text to avoid leet-speak false positives (`m@d@rch0d` ≠ email)
- **Profanity check** — `better-profanity` library + custom multilingual wordlists (Hindi, Tamil, Telugu, Kannada, Malayalam); produces a `keyword_hint` for the LLM rather than a hard block
- **Keyword check** — Per-language Redis SETs (hard/soft); hard match = immediate BLOCK; soft match = LLM HINT
- **Latency:** < 10 ms; blocks ~70% of violations without any LLM call

### Stage 3 — FAISS Semantic Search
- **File:** `app/pipeline/stage3_faiss.py`
- In-memory FAISS `IndexFlatIP` (inner product = cosine on normalised vectors) per rules profile
- Embeds the incoming message and does a nearest-neighbour search over ~23 banned topic embeddings stored in PostgreSQL and loaded at startup
- **Hard block threshold:** cosine ≥ 0.82 → BLOCK immediately (skip LLM)
- **Soft hint threshold:** cosine 0.65–0.82 → append semantic hint to the LLM prompt
- **Latency:** < 20 ms (model loaded once at startup)

### Stage 2 — LLM Semantic Analysis
- **File:** `app/pipeline/stage2_llm.py`
- Builds a multilingual prompt via `PromptBuilder` (loaded from DB `PromptTemplate`, fallback to hardcoded)
- Prompt includes: language, group topic, global rules, group-specific rules, FAISS hint, keyword hint, CRITICAL DISTINCTIONS guide
- Calls the configured LLM provider with a 15-second timeout + automatic fallback on timeout/error
- **Confidence gating:** responses below the configured threshold (EN: 0.85, Indic: 0.75) are downgraded to ALLOW to prevent false positives
- **Rule validation:** fuzzy-matches the LLM's `violated_rule` against the actual profile rules to prevent hallucinated blocks
- **Latency:** 200–800 ms depending on provider

---

## Models & AI Components

| Component | Model / Library | Purpose |
|-----------|----------------|---------|
| **Sentence Embeddings** | `paraphrase-multilingual-MiniLM-L12-v2` (Sentence Transformers) | Encode messages and banned topics into 384-dim vectors for FAISS search. Supports 50+ languages including all Indian languages |
| **Vector Index** | FAISS `IndexFlatIP` | Exact inner-product (cosine) nearest-neighbour search over banned topic embeddings |
| **LLM — Default** | Groq `llama-3.1-8b-instant` | Fast inference (~200 ms), used for category classification and nuance detection |
| **LLM — Preferred Indic** | Google Gemini `gemini-1.5-flash` | Better Tamil/Telugu/Kannada/Malayalam comprehension |
| **LLM — Fallback** | OpenRouter `mistralai/mistral-7b-instruct:free` | Optional third provider for routing |
| **Language Detection** | `langdetect` + custom heuristic | Detects Hinglish by Latin script + common Hindi stop-words |
| **Profanity Filter** | `better-profanity` + custom Indic wordlists | First line of defence against explicit profanity |

---

## Violation Categories

| Category | Description |
|----------|-------------|
| `HATE_SPEECH` | Slurs, dehumanisation, or attacks targeting a protected group (race, religion, caste, gender) |
| `PROFANITY` | General offensive language / swearing at an individual without group targeting |
| `THREAT` | Direct or implied threats of physical harm, violence, or doxxing |
| `SELF_HARM` | Suicide instructions, overdose queries, self-harm encouragement |
| `PII` | Personal Identifiable Information — phone, Aadhaar, PAN, UPI, bank OTP |
| `SPAM` | Repeated flooding messages from the same user |
| `SCAM` | Crypto fraud, phishing, fake investment schemes |
| `SEXUAL` | Explicit sexual content or harassment |
| `CSAM` | Any sexual content involving minors |
| `OFF_TOPIC` | Content outside the group's stated topic |
| `MISINFORMATION` | Verifiably false claims presented as fact |
| `NONE` | No violation detected — message is clean |

---

## Project Structure

```
moderator-service/
├── docker-compose.yml          # Production: postgres + redis + api + celery + flower
├── docker-compose.dev.yml      # Dev: postgres + redis only (run uvicorn locally)
├── Makefile                    # Convenience commands (lint, test, seed, migrate)
├── .env.example                # Template for all environment variables
│
├── service/
│   ├── Dockerfile              # Multi-stage Python 3.12 image
│   ├── requirements.txt        # All Python dependencies
│   ├── alembic.ini             # Database migration config
│   ├── .env                    # Local secrets (not committed)
│   │
│   ├── app/
│   │   ├── main.py             # FastAPI app, lifespan, FAISS pre-warming
│   │   ├── api/v1/
│   │   │   ├── moderate.py     # POST /v1/moderate/ — primary endpoint
│   │   │   ├── profiles.py     # CRUD for rules profiles
│   │   │   ├── admin.py        # Admin: API key management
│   │   │   ├── feedback.py     # Feedback template management
│   │   │   └── health.py       # GET /v1/health
│   │   ├── pipeline/
│   │   │   ├── engine.py       # Orchestrates stages 0–3
│   │   │   ├── stage0_language.py   # Language detection + normalisation
│   │   │   ├── stage1_prefilter.py  # Spam, PII, profanity, keywords
│   │   │   ├── stage2_llm.py        # LLM semantic analysis
│   │   │   └── stage3_faiss.py      # FAISS vector similarity
│   │   ├── llm/
│   │   │   ├── factory.py      # Provider selection from .env
│   │   │   ├── groq_provider.py
│   │   │   ├── gemini_provider.py
│   │   │   ├── openrouter_provider.py
│   │   │   └── prompt_builder.py    # Builds multilingual moderation prompts
│   │   ├── db/
│   │   │   ├── models.py       # SQLAlchemy models (RulesProfile, BannedTopicEmbedding, etc.)
│   │   │   └── session.py      # Async session factory
│   │   ├── i18n/
│   │   │   ├── detector.py     # Language + Hinglish detection
│   │   │   └── normaliser.py   # Indic script normalisation + leet-speak stripping
│   │   └── cache/
│   │       └── feedback_cache.py    # Redis-cached feedback message templates
│   │
│   ├── scripts/
│   │   ├── seed_datasets.py    # Seeds: keywords, FAISS topics, profile, API key
│   │   ├── run_evaluation.py   # Batch evaluation against test dataset
│   │   └── create_admin_key.py # Generates a new admin API key
│   │
│   └── tests/
│       ├── test_normaliser.py
│       └── test_categorization.ps1  # End-to-end PowerShell test suite (64 cases)
│
└── sdk/
    ├── moderator_sdk/
    │   └── client.py           # Python SDK for consuming the API
    └── tests/
        └── test_client.py
```

---

## Quick Start (Local Dev)

### Prerequisites

- Python 3.12+
- Docker Desktop (for PostgreSQL + Redis)
- A Groq API key (free tier works) from [console.groq.com](https://console.groq.com)
- PowerShell 7+ (for running the test suite on Windows)

### 1. Clone & setup virtual environment

```bash
git clone <repo-url>
cd moderator-service

python -m venv aimod
# Windows:
aimod\Scripts\activate
# Linux/macOS:
source aimod/bin/activate

pip install -r service/requirements.txt
```

### 2. Configure environment

```bash
cp .env.example service/.env
# Edit service/.env — at minimum set:
#   GROQ_API_KEY=gsk_...
#   DATABASE_URL=postgresql+asyncpg://moderator:moderator_pass@localhost:5432/moderator_db
#   REDIS_URL=redis://localhost:6379/0
```

### 3. Start infrastructure (PostgreSQL + Redis)

```bash
docker-compose -f docker-compose.dev.yml up -d
```

This starts:
- **PostgreSQL 15** on `localhost:5432`
- **Redis 7** on `localhost:6379`

---

## Seeding the Database

The seed script creates the schema, loads all keywords into Redis, embeds banned topics into PostgreSQL, creates the default rules profile, and generates an API key.

```bash
cd service
python scripts/seed_datasets.py
```

**What it seeds:**

| Component | Count | Storage |
|-----------|-------|---------|
| Keyword sets (hard/soft, EN/HI/Hinglish) | ~120 terms | Redis sorted sets |
| Banned topic embeddings | 23 topics | PostgreSQL + in-memory FAISS |
| Rules profile | 1 (default_test_profile) | PostgreSQL |
| Prompt template | 1 (multilingual) | PostgreSQL |
| API key | `1.secret123` | PostgreSQL (bcrypt hash) |

> **Note:** The seed script is **idempotent** — it deletes existing FAISS embeddings and prompt templates before re-inserting, so re-running is safe and will not accumulate duplicates.

**Verify seeding:**

```python
# Quick check in Python
import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import select, func
from app.db.models import BannedTopicEmbedding

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(func.count()).select_from(BannedTopicEmbedding))
        print(f"FAISS topics in DB: {result.scalar()}")  # Should be 23

asyncio.run(check())
```

---

## Running the Service

### Option A: Uvicorn (local dev with hot-reload)

```bash
cd service

# Activate your virtual env first
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

The service will:
1. Load the `paraphrase-multilingual-MiniLM-L12-v2` model (~118 MB, cached after first run)
2. Pre-warm FAISS indices for all profiles in the database
3. Accept requests at `http://localhost:8001`

**API Docs:** `http://localhost:8001/docs` (Swagger UI)

### Option B: Celery worker (for async audit logging)

```bash
cd service
celery -A app.tasks.celery_app worker --loglevel=info
```

### Option C: Flower (Celery monitoring dashboard)

```bash
cd service
celery -A app.tasks.celery_app flower --port=5555
```

Open `http://localhost:5555` to monitor task queues.

---

## Docker Deployment

### Full stack (production-like)

```bash
# Build and start everything: postgres, redis, api, celery worker, flower
docker-compose up --build
```

Services started:
| Container | Port | Description |
|-----------|------|-------------|
| `moderator_postgres` | 5432 | PostgreSQL 15 database |
| `moderator_redis` | 6379 | Redis 7 cache + rate limiter |
| `moderator_api` | 8001 | FastAPI + Uvicorn |
| `moderator_celery` | — | Celery async worker |
| `moderator_flower` | 5555 | Celery monitoring dashboard |

> **Note:** When using Docker, database URLs automatically use Docker network hostnames (`db`, `redis`) instead of `localhost`. The `docker-compose.yml` handles this via environment overrides.

### After first start, run seed inside the container:

```bash
docker exec -it moderator_api python scripts/seed_datasets.py
```

### Useful Docker commands

```bash
# View service logs
docker-compose logs -f service

# Restart just the API
docker-compose restart service

# Stop everything
docker-compose down

# Stop and delete volumes (full reset)
docker-compose down -v
```

---

## Testing

### End-to-End Test Suite (PowerShell)

The primary test suite covers **64 test cases** across 5 levels:

```powershell
cd service

# Run all 64 tests
.\test_categorization.ps1

# Run only Level 1 + 2 (smoke test, ~30 tests)
.\test_categorization.ps1 -Level 2

# Run with verbose output (shows result for every test, not just failures)
.\test_categorization.ps1 -Verbose
```

**Test levels:**

| Level | Focus | Examples |
|-------|-------|---------|
| L1 | Clean messages — all should ALLOW | Greetings, technical questions, Hindi news |
| L2 | Obvious violations — Stage 1 should catch | PII, direct profanity, crypto scam |
| L3 | Indirect violations — LLM should catch | Implied threats, dehumanisation, casteist slurs |
| L4 | Bypass attempts — normaliser + LLM | Leet speak, dotted slurs, code-mixed hate |
| L5 | Edge cases — contextual nuance | Fiction, quoting to report, sarcasm |

**API key for tests:** `1.secret123`

### Unit Tests

```bash
cd service
pip install pytest
pytest tests/ -v
```

### Batch Evaluation Script

```bash
cd service
python scripts/run_evaluation.py
# Outputs accuracy per category across a labeled dataset
```

---

## Python SDK

The SDK provides a typed Python client for consuming the moderation API.

### Installation

```bash
cd sdk
pip install -e .
```

### Usage

```python
from moderator_sdk import ModerationClient

client = ModerationClient(
    base_url="http://localhost:8001",
    api_key="1.secret123"
)

result = client.moderate(
    message="You stupid idiot get out of here",
    profile_id="default_test_profile",
    user_id="user_123"
)

print(result.decision)          # "BLOCK"
print(result.category)          # "PROFANITY"
print(result.confidence)        # 1.0
print(result.feedback_message)  # Polite response in detected language
```

---

## API Reference

### `POST /v1/moderate/`

Moderate a single message.

**Headers:**
```
X-API-Key: <your_api_key>
Content-Type: application/json
```

**Request body:**
```json
{
  "message": "Your message text here",
  "profile_id": "default_test_profile",
  "user_id": "optional_user_id",
  "metadata": {}
}
```

**Response:**
```json
{
  "decision": "BLOCK",
  "category": "PROFANITY",
  "detected_language": "en",
  "stage_triggered": "llm+keyword_hint",
  "confidence": 0.95,
  "violated_rule": "No hate speech, racism, or severe profanity.",
  "reason": "Message contains explicit profanity directed at an individual.",
  "feedback_message": "Please refrain from using abusive language in the community.",
  "latency_ms": {
    "stage0_lang": 2,
    "stage1": 8,
    "stage2_llm": 312,
    "stage3_faiss": 14,
    "total": 340,
    "llm_provider": "groq"
  }
}
```

### Other Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/health` | Health check |
| `GET` | `/docs` | Swagger UI |
| `POST` | `/v1/profiles/` | Create a new rules profile |
| `GET` | `/v1/profiles/{id}` | Get profile details |
| `POST` | `/v1/admin/api-keys/` | Generate new API key |
| `GET` | `/v1/feedback/templates/` | List feedback templates |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `groq` | LLM backend: `groq`, `gemini`, or `openrouter` |
| `GROQ_API_KEY` | — | Groq API key (get free at console.groq.com) |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `DATABASE_URL` | — | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Sentence Transformer model name |
| `SECRET_KEY` | — | JWT/session secret (change in production) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `SERVICE_PORT` | `8001` | Uvicorn port |

---

## Makefile Commands

```bash
make lint          # Run ruff linter
make format        # Auto-format with ruff
make test          # Run pytest
make seed          # Run seed_datasets.py
make migrate       # Run alembic migrations
make dev           # Start infra + uvicorn with reload
make docker-up     # docker-compose up --build
make docker-down   # docker-compose down
```

---

## Supported Languages

| Language | Code | Stage 1 Profanity | Stage 2 LLM | Notes |
|----------|------|-------------------|-------------|-------|
| English | `en` | ✅ | ✅ | Full support |
| Hindi (Devanagari) | `hi` | ✅ | ✅ | Normalised before lookup |
| Hinglish (Roman) | `hi-en` | ✅ | ✅ | Detected by heuristic |
| Tamil | `ta` | ✅ | ✅ | LLM preferred |
| Telugu | `te` | ✅ | ✅ | LLM preferred |
| Kannada | `kn` | ✅ | ✅ | LLM preferred |
| Malayalam | `ml` | ✅ | ✅ | LLM preferred |

