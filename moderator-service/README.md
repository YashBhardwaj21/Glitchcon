# AI Moderation Microservice

> **Production-grade, Multilingual, LLM-powered Content Safety Pipeline**

A robust microservice designed to handle real-time content moderation across multiple languages, featuring a 4-stage processing pipeline for maximum throughput and accuracy while keeping LLM inference costs low.

---

## Architecture

The system evaluates incoming messages through a tiered pipeline designed to fail-fast on obvious violations before invoking the more expensive (and higher latency) LLM and Semantic Search layers.

```text
Incoming Message
       │
       ▼
┌─────────────────────────────────┐
│ Stage 0: Language Detection     │  Detects language (`en`, `hi`, `te`, etc.)
└─────────────────────────────────┘  using `langdetect` + `indic-transliteration`.
       │
       ▼
┌─────────────────────────────────┐  (Returns BLOCK instantly if matched)
│ Stage 1: Pre-filter (Redis)     │  • Spam flood detection (sliding window)
└─────────────────────────────────┘  • PII extraction (regex)
       │                             • Profanity lists + Keyword matching
       ▼
   (Clean)
       │
       ├─────────────────────────────────────────┐
       ▼                                         ▼
┌─────────────────────────┐           ┌─────────────────────────┐
│ Stage 2: LLM Analysis   │           │ Stage 3: FAISS Search   │
│ (Groq/Gemini/OpenAI)    │           │ (Semantic Banned Topics)│
└─────────────────────────┘           └─────────────────────────┘
       │                                         │
       └──────────────────┬──────────────────────┘
                          ▼
             Decision Merge & Fallback
                          │
                          ▼
           Response (ALLOW / BLOCK / REASON)
```

---

## Key Features

1. **Multilingual Support:** First-class support for Indian languages (Hindi, Tamil, Telugu, Kannada, Malayalam) and mixed scripts (Hinglish/Tanglish).
2. **Contextual Rules via Profiles:** Moderation rules are defined per "Group" or "Community" via `RulesProfiles`. E.g., a "Study Group" profile denies answer-sharing, while a "Sports Group" profile allows passionate debate but blocks abuse.
3. **Python SDK:** Fully featured async/sync SDK with exponential backoff, circuit-breaking, and batch execution available out-of-the-box (`sdk/`).
4. **LLM Agnostic:** Factory pattern allows hot-swapping between `Groq` (Llama 3), `Google Gemini`, or `OpenRouter` models via env vars.
5. **Observability:** Tracks latency per pipeline stage and logs decisions alongside confidence scores to Postgres.

---

## Quickstart (Development)

Requires **Docker** and **Docker Compose**.

### 1. Environment Setup

```bash
cd moderator-service
cp .env.example .env

# Edit .env and supply your chosen LLM provider API key
# e.g., GROQ_API_KEY=your_key and LLM_PROVIDER=groq
```

### 2. Stand up the stack

```bash
docker compose -f docker-compose.dev.yml up -d
```

### 3. Run Migrations & Seed the Database

```bash
make migrate
make seed
```

The `make seed` command pushes required test data, global keywords, FAISS embeddings, and creates your first Admin API Key.

### 4. Create Rules Profiles

Use the seeder script from the `gba1` consumer app to populate the demo rules profiles:

```bash
# Uses the MODERATOR_API_KEY generated in step 3
export MODERATOR_API_KEY="<id>.<secret>"
python ../gba1/scripts/seed_profiles.py
```

### 5. API Documentation

Navigate to `http://localhost:8001/docs` to view the interactive FastAPI Swagger UI.

---

## Consumer Integration (Python)

See the detailed instructions in the [SDK README](sdk/README.md).

```python
import asyncio
from moderator_sdk import ModerationClient, ModerationRequest

async def run_moderation():
    async with ModerationClient(base_url="http://localhost:8001", api_key="1.abc") as client:
        resp = await client.moderate(ModerationRequest(
            message="Hey everyone!",
            profile_id="wele_general",
            user_id="user_123"
        ))
        print(f"Decision: {resp.decision} (Language: {resp.detected_language})")

asyncio.run(run_moderation())
```

See the `gba1/` directory in the repository root for a full FastAPI + Celery consumer application example.

---

## Test & Maintain

Make targets are provided for daily developer workflows:

```bash
# Run unit tests (ignores e2e tests requiring a running LLM/DB)
make test

# Run End-to-End tests (requires stack to be UP)
# MODERATOR_API_KEY must be set in your env
pytest service/tests/e2e -v -m e2e

# Run Ruff linter and formatter
make lint
make format
```
