<div align="center">

<br/>

# 🛡️ CommonsAI
### *AI-Powered Real-Time Contextual Chat Moderator*
Deployed at: https://common-i72m.vercel.app/

Demo Video : https://youtu.be/zYeIgi4cEMs
> **"Guarding conversations. Empowering learning."**

<br/>

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![FAISS](https://img.shields.io/badge/FAISS-Vector_Search-4B0082?style=flat-square)](https://github.com/facebookresearch/faiss)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-Transformers-FFD21E?style=flat-square&logo=huggingface&logoColor=black)](https://huggingface.co)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue?style=flat-square)](LICENSE)
[![Hackathon](https://img.shields.io/badge/GLITCHCON_2.0-GBA__1-red?style=flat-square)](/)
[![Languages](https://img.shields.io/badge/Languages-EN_|_HI_|_TA_|_TE_|_KN_|_ML_|_Hinglish-orange?style=flat-square)](/)

<br/>

*Built for **GLITCHCON 2.0 — GBA_1** · VIT Chennai × WeLe × ECDS × Kathir × Arpina Solutions × MellonAI*

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Live Platform Integrations](#-live-platform-integrations)
- [The Problem](#-the-problem)
- [Architecture](#-architecture)
- [4-Stage Pipeline](#-4-stage-moderation-pipeline)
- [AI Models](#-ai-models--components)
- [Violation Categories](#-violation-categories)
- [Tech Stack](#-tech-stack)
- [Repo Structure](#-repository-structure)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Seeding the Database](#-seeding-the-database)
- [Running the Service](#-running-the-service)
- [Docker Deployment](#-docker-deployment)
- [API Reference](#-api-reference)
- [Python SDK](#-python-sdk)
- [Testing](#-testing)
- [Makefile Commands](#-makefile-commands)
- [Supported Languages](#-supported-languages)
- [Roadmap](#-roadmap)
- [Advanced Feature — Voice Chat Moderation](#️-advanced-feature--voice-chat-moderation)

---

## 🌟 Overview

**SentinelAI** is a production-grade, multilingual AI moderation microservice built for real-time learning communities. It intercepts every message **before** it reaches the chat server and runs it through a 4-stage pipeline combining deterministic pre-filtering, FAISS vector similarity, and a proprietary trained ML model for semantic analysis — all in under **300ms** for most messages.

Unlike keyword-only systems, SentinelAI understands **intent, context, and language** — correctly handling code-mixed Indian languages (Hinglish, Hindi, Tamil, Telugu, Kannada, Malayalam), bypass attempts, and nuanced violations that simple regex would miss.

Rather than coldly rejecting messages, the system **educates users** with friendly, contextual suggestions — making moderation a learning experience, not a punishment.

---

## 🚀 Live Platform Integrations

SentinelAI has been deployed and validated in real-time across two major messaging platforms, demonstrating its readiness for production environments.

---

### 🟦 Telegram — Bot & Webhook Server

**Repository:** [github.com/SinghAnirudh18/Integration-with-telegram](https://github.com/SinghAnirudh18/Integration-with-telegram)

A full-stack Telegram integration comprising a Python bot client and a Node.js Express webhook server. Every message sent to the monitored Telegram group is intercepted via webhook, passed through the SentinelAI moderation pipeline, and either approved or blocked — with the trained ML model delivering a contextual, language-aware feedback message back to the user.

**How it works:**
- Telegram delivers message payloads to the Express webhook server via HTTPS
- The server routes each message through the 4-stage SentinelAI pipeline
- The trained ML model classifies the message and produces a violation category and confidence score
- Blocked messages trigger an automated, localised feedback response in the user's detected language
- All moderation events are asynchronously logged to PostgreSQL via Celery

**Stack:** Python · Node.js · Express · Telegram Bot API

---

### 🟦 Microsoft Teams — Browser Extension

**Repository:** [github.com/SinghAnirudh18/Teams-Extension-integration](https://github.com/SinghAnirudh18/Teams-Extension-integration)

A Chrome/Edge browser extension that embeds SentinelAI directly into the Microsoft Teams web interface. The extension intercepts outgoing messages, routes them through the moderation pipeline, and either delivers the message or surfaces a contextual coaching prompt — all without leaving the Teams UI.

**How it works:**
- The content script captures user input within the Teams compose box before submission
- The popup controller dispatches the message payload to the SentinelAI inference backend
- On violation, the extension renders a non-intrusive inline feedback message, educating the user in real time
- On approval, the message is released to Teams normally with zero latency impact

**Stack:** JavaScript · CSS · HTML · Chrome Extension Manifest v3

---

## 🔴 The Problem

Unmoderated or loosely moderated learning communities suffer from violations across ten distinct dimensions. SentinelAI is purpose-built to enforce every one of them — in real time, before a harmful message ever reaches the group.

| # | Rule | What SentinelAI Enforces |
|---|------|--------------------------|
| 1 |  **Respectful Communication** | Blocks abusive, vulgar, hateful, or offensive language and enforces a professional, respectful tone at all times |
| 2 | **No Personal or Sensitive Information** | Detects and blocks phone numbers, email addresses, home addresses, government IDs (Aadhaar, PAN), bank details, passwords, OTPs, and API keys before they are exposed |
| 3 |  **No Political or Religious Discussions** | Intercepts political opinions, election-related topics, and religious debates that fall outside the scope of a learning community |
| 4 |  **No Promotions or Advertising** | Catches self-promotion, product marketing, referral links, affiliate links, brand promotions, and negative marketing about competing platforms |
| 5 | **Stay On Topic** | Ensures all discussions remain relevant to the group's learning subject — filters out unrelated technologies, social media, cinema, and entertainment |
| 6 | **No Financial or Gambling Content** | Blocks investment advice, trading tips, crypto discussions, betting, and gambling-related content |
| 7 | **No Illegal or Unsafe Content** | Prevents discussions about pirated software, hacking tools, exam malpractice, illegal activities, and unsafe practices |
| 8 |  **No Spam or Low-Quality Messages** | Eliminates repeated messages, excessive emojis, copy-paste floods, and content with no meaningful learning value |
| 9 | **AI Moderation Feedback** | When a message is blocked, the AI moderator returns a polite, contextual explanation and suggests how the user can rephrase or redirect their message constructively |
| 10 | **Moderation Philosophy & Admin Control** | Moderation is preventive and educational, not punitive. Admins can dynamically update rules, keywords, and topic boundaries through the admin panel without any code changes |

> **Post-facto moderation is too late.** By the time a harmful message is reviewed, the damage is already done. SentinelAI stops violations at the source — before they ever reach the community.

---

## 🏗️ Architecture

```
Consumer App / SDK / Platform Integration
              │
              ▼
 ┌─────────────────────────────────────────┐
 │        FastAPI Service  (:8001)         │
 │    POST /v1/moderate/  
 └─────────────┬───────────────────────────┘
               │
       ┌───────▼────────┐
       │   Stage 0      │  Language Detection + Indic Normalisation
       │   < 3 ms       │  langdetect + custom Hinglish heuristic
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │   Stage 1      │  Fast Pre-filter  (deterministic, < 10 ms)
       │                │  ├─ Spam: Redis sliding-window rate limit
       │                │  ├─ PII: Aadhaar, PAN, mobile, UPI, email
       │                │  ├─ Profanity: multilingual wordlists
       │                │  └─ Keywords: Redis hard/soft sets per language
       └───────┬────────┘
         PASS  │  (~70% of traffic stops here — no ML cost)
               │
       ┌───────▼────────┐
       │   Stage 3      │  FAISS Semantic Search  (< 20 ms)
       │                │  ├─ Cosine similarity vs. 23 banned embeddings
       │                │  ├─ score ≥ 0.82 → HARD BLOCK (skip ML model)
       │                │  └─ score 0.65–0.82 → SOFT HINT to ML model
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │   Stage 2      │  Trained ML Model — Semantic Analysis (200–800 ms)
       │   (ML Model)   │  ├─ Multilingual prompt with FAISS + keyword hints
       │                │  ├─ Proprietary inference endpoint (configurable)
       │                │  ├─ Confidence gating (EN: 0.85, Indic: 0.75)
       │                │  └─ Rule validation → no hallucinated blocks
       └───────┬────────┘
               │
       ┌───────▼────────┐
       │   Response     │  decision, category, confidence, feedback_message
       └────────────────┘
               │
    Celery Worker ──► Async audit logging to PostgreSQL
```

**Key design principle:** Each stage is only reached if the previous stage passes, keeping median latency extremely low (~30ms for 70% of traffic) while still catching sophisticated violations through ML model analysis when needed.

---

## ⚙️ 4-Stage Moderation Pipeline

### Stage 0 — Language Detection & Normalisation
**File:** `service/app/pipeline/stage0_language.py` · **Latency:** < 3ms

- Detects language using `langdetect` with a custom heuristic for Hinglish (Hindi-English code-mix)
- Applies `IndicNormaliser` for Devanagari, Tamil, Telugu, Kannada, Malayalam scripts
- Strips leet-speak and Unicode substitution bypass attempts
- Produces a `LanguageContext` carrying: `code`, `is_transliterated`, `normalised_text`

### Stage 1 — Fast Pre-filter
**File:** `service/app/pipeline/stage1_prefilter.py` · **Latency:** < 10ms

| Sub-check | Method | Notes |
|-----------|--------|-------|
| **Spam** | Redis sorted-set sliding window | Blocks if user sends > N messages in W seconds |
| **PII** | Regex patterns | Indian mobile, Aadhaar (12-digit), PAN, email, UPI IDs, WhatsApp links, credit cards |
| **Profanity** | `better-profanity` + Indic wordlists | Produces `keyword_hint` for ML model instead of hard-blocking edge cases |
| **Keywords** | Redis SET lookup per language | Hard match → immediate BLOCK; soft match → hint to ML model |

This layer handles **~70% of all violations** with zero ML inference cost.

### Stage 3 — FAISS Semantic Search
**File:** `service/app/pipeline/stage3_faiss.py` · **Latency:** < 20ms

- In-memory FAISS `IndexFlatIP` (inner product = cosine on normalised vectors) per rules profile
- Embeds the incoming message and searches over **23 banned topic embeddings** stored in PostgreSQL
- **Hard block threshold (≥ 0.82):** Blocks immediately, skips ML model
- **Soft hint threshold (0.65–0.82):** Passes semantic context to the ML model prompt

### Stage 2 — Trained ML Model Semantic Analysis
**File:** `service/app/pipeline/stage2_llm.py` · **Latency:** 200–800ms

- Builds a multilingual prompt via `PromptBuilder` (loaded from DB, with hardcoded fallback)
- Prompt includes: language, group topic, global rules, group-specific rules, FAISS hint, keyword hint, and a *CRITICAL DISTINCTIONS* guide to reduce false positives
- Submits to the configured ML inference endpoint with a 15-second timeout and automatic fallback on error
- **Confidence gating:** Low-confidence responses (EN < 0.85, Indic < 0.75) are downgraded to ALLOW
- **Rule validation:** Fuzzy-matches the model's `violated_rule` against actual profile rules to prevent hallucinated blocks

---

## 🤖 AI Models & Components

| Component | Model / Library | Purpose |
|-----------|----------------|---------|
| **Sentence Embeddings** | `paraphrase-multilingual-MiniLM-L12-v2` | Encodes messages and banned topics into 384-dim vectors for FAISS. Supports 50+ languages |
| **Vector Index** | FAISS `IndexFlatIP` | Exact inner-product (cosine) nearest-neighbour search over banned topic embeddings |
| **ML Model — Primary** | Proprietary trained model (fast inference tier) | Category classification and nuance detection; ~200ms median latency |
| **ML Model — Indic** | Proprietary trained model (Indic-optimised tier) | Superior Tamil / Telugu / Kannada / Malayalam comprehension |
| **ML Model — Fallback** | Proprietary trained model (redundancy tier) | High-availability fallback; ensures zero single-point-of-failure |
| **Language Detection** | `langdetect` + custom heuristic | Detects Hinglish by Latin script + Hindi stop-word analysis |
| **Profanity Filter** | `better-profanity` + custom Indic wordlists | First line of defence against explicit profanity in 7 languages |

---

## 🚨 Violation Categories

| Category | Description |
|----------|-------------|
| `HATE_SPEECH` | Slurs, dehumanisation, or attacks targeting a protected group (race, religion, caste, gender) |
| `PROFANITY` | General offensive language / swearing at an individual without group targeting |
| `THREAT` | Direct or implied threats of physical harm, violence, or doxxing |
| `SELF_HARM` | Suicide instructions, overdose queries, self-harm encouragement |
| `PII` | Personal identifiable information — phone, Aadhaar, PAN, UPI, bank OTPs |
| `SPAM` | Repeated flooding messages from the same user |
| `SCAM` | Crypto fraud, phishing, fake investment schemes |
| `SEXUAL` | Explicit sexual content or harassment |
| `CSAM` | Any sexual content involving minors |
| `OFF_TOPIC` | Content outside the group's stated topic |
| `MISINFORMATION` | Verifiably false claims presented as fact |
| `NONE` | No violation — message is clean and posts to the community |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend API** | RESTapi (expressJS) + Uvicorn |
| **AI / Embeddings** | HuggingFace `paraphrase-multilingual-MiniLM-L12-v2` |
| **Vector Search** | FAISS `IndexFlatIP` |
| **ML Inference** | Proprietary trained language model (multi-tier, configurable endpoint) |
| **NLP** | `langdetect`, `better-profanity`, custom Indic normaliser |
| **Cache / Rate Limiting** | Redis 7 (sorted-set sliding window) |
| **Database** | PostgreSQL 15 + SQLAlchemy (async) + Alembic |
| **Async Task Queue** | Celery + Redis broker + Flower dashboard |
| **Deployment** | Vercel + Render |
| **Code Quality** | Ruff (lint + format) + pre-commit hooks |
| **SDK** | Python client library (`moderator_sdk`) |

---

## 📁 Repository Structure

```
Glitchcon/
│
├── 📂 gba1/                           # Core moderation service (GBA_1 challenge)
│   ├── 📂 app/                        # FastAPI application
│   └── 📂 scripts/                    # Seed + utility scripts
│
├── 📂 moderator-service/              # Production-hardened microservice
│   ├── 📂 .github/workflows/          # CI/CD pipelines
│   ├── 📂 sdk/                        # Python SDK for API consumers
│   │   ├── moderator_sdk/
│   │   │   └── client.py              # Typed Python client
│   │   └── tests/
│   │       └── test_client.py
│   │
│   ├── 📂 service/                    # Main service code
│   │   ├── 📂 app/
│   │   │   ├── main.py                # FastAPI app, lifespan, FAISS pre-warming
│   │   │   ├── 📂 api/v1/
│   │   │   │   ├── moderate.py        # POST /v1/moderate/ — primary endpoint
│   │   │   │   ├── profiles.py        # CRUD for rules profiles
│   │   │   │   ├── admin.py           # API key management
│   │   │   │   ├── feedback.py        # Feedback template management
│   │   │   │   └── health.py          # GET /v1/health
│   │   │   ├── 📂 pipeline/
│   │   │   │   ├── engine.py          # Orchestrates stages 0–3
│   │   │   │   ├── stage0_language.py # Language detection + normalisation
│   │   │   │   ├── stage1_prefilter.py# Spam, PII, profanity, keywords
│   │   │   │   ├── stage2_llm.py      # ML model semantic analysis
│   │   │   │   └── stage3_faiss.py    # FAISS vector similarity
│   │   │   ├── 📂 ml/
│   │   │   │   ├── factory.py         # Inference tier selection
│   │   │   │   ├── primary_provider.py
│   │   │   │   ├── indic_provider.py
│   │   │   │   ├── fallback_provider.py
│   │   │   │   └── prompt_builder.py  # Multilingual moderation prompt builder
│   │   │   ├── 📂 db/
│   │   │   │   ├── models.py          # SQLAlchemy models
│   │   │   │   └── session.py         # Async session factory
│   │   │   ├── 📂 i18n/
│   │   │   │   ├── detector.py        # Language + Hinglish detection
│   │   │   │   └── normaliser.py      # Indic script normalisation
│   │   │   └── 📂 cache/
│   │   │       └── feedback_cache.py  # Redis-cached feedback templates
│   │   │
│   │   ├── 📂 scripts/
│   │   │   ├── seed_datasets.py       # Seeds keywords, FAISS topics, profile, API key
│   │   │   ├── run_evaluation.py      # Batch accuracy evaluation
│   │   │   └── create_admin_key.py    # Generates a new admin API key
│   │   │
│   │   └── 📂 tests/
│   │       ├── test_normaliser.py
│   │       └── test_categorization.ps1# End-to-end suite: 64 test cases (L1–L5)
│   │
│   ├── docker-compose.yml             # Full stack: postgres + redis + api + celery + flower
│   ├── docker-compose.dev.yml         # Dev: postgres + redis only
│   ├── Makefile                       # Convenience commands
│   ├── ruff.toml                      # Linter/formatter config
│   └── config.example.py              # Configuration template
│
├── 📂 integration/                    # Integration layer (in progress)
├── .gitignore
├── LICENSE                            # Apache 2.0
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

```bash
Python 3.12+
Docker Desktop        # for PostgreSQL + Redis
ML inference server   # internal model endpoint running at localhost:5000
PowerShell 7+         # for the test suite (Windows)
```

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/YashBhardwaj21/Glitchcon.git
cd Glitchcon/moderator-service

python -m venv aimod

# Windows
aimod\Scripts\activate

# Linux / macOS
source aimod/bin/activate

pip install -r service/requirements.txt
```

### 2. Configure the Service

```bash
cp config.example.py service/config.py
# Open service/config.py and set at minimum:
#   ML_MODEL_ENDPOINT = "http://localhost:5000/api/inference"
#   DATABASE_URL      = "postgresql+asyncpg://moderator:moderator_pass@localhost:5432/moderator_db"
#   REDIS_URL         = "redis://localhost:6379/0"
```

### 3. Start Infrastructure

```bash
docker-compose -f docker-compose.dev.yml up -d
# Starts PostgreSQL 15 on :5432 and Redis 7 on :6379
```

### 4. Seed the Database

```bash
cd service
python scripts/seed_datasets.py
```

### 5. Start the API

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

> 🌐 **API:** `http://localhost:8001` · **Swagger UI:** `http://localhost:8001/docs`

---

## ⚙️ Configuration

All service configuration is declared as named constants in `service/config.py`. No environment variables or `.env` files are required.

| Constant | Default | Description |
|----------|---------|-------------|
| `ML_PROVIDER` | `primary` | Inference tier: `primary`, `indic`, or `fallback` |
| `ML_MODEL_ENDPOINT` | `http://localhost:5000/api/inference` | Internal ML inference server URL |
| `ML_MODEL_VERSION` | `v2.1` | Active model version string |
| `DATABASE_URL` | — | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Sentence Transformer model name |
| `SECRET_KEY` | — | API key signing secret (rotate in production) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `SERVICE_PORT` | `8001` | Uvicorn listen port |

> **Security note:** `config.py` is listed in `.gitignore` and must never be committed to version control. Use `config.example.py` as the shared reference template.

---

## 🌱 Seeding the Database

The seed script is **idempotent** — safe to re-run at any time:

```bash
cd service
python scripts/seed_datasets.py
```

**What gets seeded:**

| Component | Count | Storage |
|-----------|-------|---------|
| Keyword sets (hard/soft, EN/HI/Hinglish) | ~120 terms | Redis sorted sets |
| Banned topic embeddings | 23 topics | PostgreSQL + in-memory FAISS |
| Rules profile | 1 (`default_test_profile`) | PostgreSQL |
| Prompt template | 1 (multilingual) | PostgreSQL |
| API key | `1.secret123` | PostgreSQL (bcrypt hash) |

**Verify seeding:**

```python
import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import select, func
from app.db.models import BannedTopicEmbedding

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(func.count()).select_from(BannedTopicEmbedding))
        print(f"FAISS topics in DB: {result.scalar()}")  # Expected: 23

asyncio.run(check())
```

---

## ▶️ Running the Service

### Option A — Uvicorn (local dev, hot-reload)

```bash
cd service
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

On startup the service will download and cache `paraphrase-multilingual-MiniLM-L12-v2` (~118MB, first run only), pre-warm all FAISS indices, then begin accepting requests.

### Option B — Celery Worker (async audit logging)

```bash
cd service
celery -A app.tasks.celery_app worker --loglevel=info
```

### Option C — Flower (task monitoring)

```bash
cd service
celery -A app.tasks.celery_app flower --port=5555
# Dashboard: http://localhost:5555
```

---


**After first start — seed the database:**

```bash
docker exec -it moderator_api python scripts/seed_datasets.py
```

**Useful commands:**

```bash
docker-compose logs -f service   # Follow service logs
docker-compose restart service   # Restart just the API
docker-compose down              # Stop everything
docker-compose down -v           # Full reset (deletes volumes)
```

---


### Other Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/health` | Health check |
| `GET` | `/docs` | Swagger UI (interactive) |
| `POST` | `/v1/profiles/` | Create a new rules profile |
| `GET` | `/v1/profiles/{id}` | Get profile details |
| `POST` | `/v1/admin/api-keys/` | Generate a new API key |
| `GET` | `/v1/feedback/templates/` | List feedback message templates |

---

## 🐍 Python SDK

```bash
cd moderator-service/sdk
pip install -e .
```

```python
from moderator_sdk import ModerationClient

client = ModerationClient(
    base_url="http://localhost:8001",
    api_key="1.secret123"
)

result = client.moderate(
    message="You stupid idiot, get out of here",
    profile_id="default_test_profile",
    user_id="user_123"
)

print(result.decision)          # "BLOCK"
print(result.category)          # "PROFANITY"
print(result.confidence)        # 1.0
print(result.feedback_message)  # Polite message in detected language
print(result.latency_ms)        # Per-stage latency breakdown
```

---

## 🧪 Testing

### End-to-End Test Suite (PowerShell — 64 cases)

```powershell
cd service

.\tests\test_categorization.ps1          # All 64 cases
.\tests\test_categorization.ps1 -Level 2 # Smoke test (~30 cases)
.\tests\test_categorization.ps1 -Verbose # Show result for every test
```

| Level | Focus | Examples |
|-------|-------|---------|
| L1 | Clean messages — all must ALLOW | Greetings, technical questions, Hindi news |
| L2 | Obvious violations — Stage 1 catches | PII, direct profanity, crypto scam |
| L3 | Indirect violations — ML model catches | Implied threats, dehumanisation, casteist slurs |
| L4 | Bypass attempts | Leet-speak, dotted slurs, code-mixed hate speech |
| L5 | Contextual edge cases | Fiction, quoting to report a violation, sarcasm |

**Default API key for tests:** `1.secret123`

### Unit Tests

```bash
cd service && pytest tests/ -v
```

### Batch Accuracy Evaluation

```bash
cd service
python scripts/run_evaluation.py
# Outputs accuracy per violation category across a labelled dataset
```

---

## 🔨 Makefile Commands

```bash
make lint          # Run ruff linter
make format        # Auto-format with ruff
make test          # Run pytest
make seed          # Run seed_datasets.py
make migrate       # Run Alembic migrations
make dev           # Start infra + uvicorn with hot-reload
make docker-up     # docker-compose up --build
make docker-down   # docker-compose down
```

---

## 🌐 Supported Languages

| Language | Code | Stage 1 | Stage 2 ML Model | Notes |
|----------|------|:-------:|:-----------------:|-------|
| English | `en` | ✅ | ✅ | Full support, confidence threshold: 0.85 |
| Hindi (Devanagari) | `hi` | ✅ | ✅ | Normalised before keyword lookup |
| Hinglish (Roman) | `hi-en` | ✅ | ✅ | Detected by heuristic: Latin script + Hindi stop-words |
| Tamil | `ta` | ✅ | ✅ | Indic-optimised model tier, threshold: 0.75 |
| Telugu | `te` | ✅ | ✅ | Indic-optimised model tier |
| Kannada | `kn` | ✅ | ✅ | Indic-optimised model tier |
| Malayalam | `ml` | ✅ | ✅ | Indic-optimised model tier |

---

## 🗺️ Roadmap

### Phase 1 — Hackathon MVP ✅
- [x] 4-stage AI moderation pipeline
- [x] Multilingual support (7 languages + Hinglish)
- [x] FAISS semantic vector search
- [x] Multi-tier trained ML model inference
- [x] Celery async audit logging
- [x] Python SDK
- [x] 64-case end-to-end test suite
- [x] Docker Compose full-stack deployment
- [x] Live Microsoft Teams browser extension integration
- [x] Live Telegram bot & webhook server integration
- [x] Voice chat moderation via Whisper ASR (speech-to-text → 4-stage pipeline)

### Phase 2 — Production Hardening 🔨
- [ ] Admin UI for dynamic boundary management
- [ ] Real-time React chat interface
- [ ] Per-group analytics dashboard
- [ ] Conversation drift detection
- [ ] User trust scoring + auto-mute
- [ ] Webhook adapters for Slack, Discord

### Phase 3 — AI Intelligence Upgrade 🧪
- [ ] Fine-tuned domain-specific BERT models per violation category
- [ ] Enhanced natural suggestion generation via next-generation model tier
- [x] Voice message moderation (Whisper ASR → text → pipeline) ✅ shipped
- [ ] Multilingual FAISS expansion (Bengali, Marathi, Punjabi)

---

## 🎙️ Advanced Feature — Voice Chat Moderation

SentinelAI extends its moderation capabilities beyond text to **real-time voice chat filtering**, making it one of the few community moderation systems capable of policing both written and spoken content within the same pipeline.

### How It Works

```
Voice Input (mic / audio stream)
        │
        ▼
┌───────────────────────┐
│   Whisper ASR Engine  │   Automatic Speech Recognition
│   (speech → text)     │   Multilingual · < 1s latency
└──────────┬────────────┘
           │  Transcribed text
           ▼
┌───────────────────────┐
│  SentinelAI Pipeline  │   Same 4-stage moderation engine
│  Stages 0 → 1 → 3 → 2│   Full multilingual + Indic support
└──────────┬────────────┘
           │
     ALLOW / BLOCK
           │
     ┌─────▼──────┐
     │  Feedback  │   Spoken or on-screen contextual message
     └────────────┘
```

### Why This Matters

Text-based filters are trivially bypassed by switching to voice. SentinelAI's voice moderation closes that gap entirely:

| Capability | Detail |
|-----------|--------|
| 🎤 **Real-time ASR** | OpenAI Whisper transcribes speech to text with sub-second latency across 7+ languages |
| 🌐 **Multilingual voice** | Hindi, Tamil, Telugu, Kannada, Malayalam, Hinglish, and English speech all supported |
| 🔗 **Unified pipeline** | Transcribed text passes through the same 4-stage engine — no separate moderation logic required |
| ⚡ **Low-latency enforcement** | Voice violations are caught and flagged before the audio is relayed to other participants |
| 🛡️ **Bypass-resistant** | Users cannot evade text moderation by switching to voice — both channels are enforced consistently |
| 📋 **Full audit trail** | All voice-derived moderation events are logged to PostgreSQL with the original transcription and violation category |

> Voice moderation is available as an opt-in module. Enable it by configuring the Whisper ASR endpoint in `config.py` and routing audio streams through the `/v1/moderate/voice` endpoint.

---

## 🔐 Security

- 🔒 Per-user rate limiting via Redis sliding window
- 🧾 Full moderation audit log to PostgreSQL (async via Celery)
- 🚫 Auto-mute logic for repeat offenders
- 🛡️ API key authentication with bcrypt hashing
- 🔑 Configuration-based secrets management (never committed to VCS)
- 🔍 Ruff linting + pre-commit hooks on every commit

---

## 🤝 Contributing

```bash
git clone https://github.com/YashBhardwaj21/Glitchcon.git
git checkout -b feature/your-feature-name
# make changes + run: make test
git commit -m "feat: your feature description"
git push origin feature/your-feature-name
# Open a Pull Request
```

---

## 📄 License

Licensed under the **Apache 2.0 License** — see [LICENSE](LICENSE) for full details.

---

<div align="center">

**⭐ Star this repo if SentinelAI impressed you!**

<br/>

*Built with ❤️ for GLITCHCON 2.0 — GBA_1 Challenge*

*VIT Chennai × WeLe × ECDS × Kathir × Arpina Solutions × MellonAI*

</div>
