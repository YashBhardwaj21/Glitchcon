from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, logger

from app.api.v1 import health
from app.api.v1 import admin
from app.api.v1 import profiles
from app.api.v1 import moderate
from app.api.v1 import feedback
from app.db.session import AsyncSessionLocal
from app.db.models import RulesProfile
from sqlalchemy.future import select
from app.pipeline.stage3_faiss import FaissService
from app.pipeline.stage2_classifier import Stage2Classifier

# Initialize structured logging
setup_logging()


async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("Starting AI Moderation Microservice")

    # 1. Load sentence-transformer model (shared by FAISS and classifier)
    FaissService.load_model()

    # 2. Load local classifier (classifier.pkl + label encoder)
    #    Loads into memory once — predict() calls are then ~2ms
    classifier_ok = Stage2Classifier.load()
    if classifier_ok:
        logger.info("Stage2Classifier loaded successfully.")
    else:
        # Non-fatal — pipeline falls back to FAISS + LLM if pkl is missing
        logger.warning(
            "Stage2Classifier not loaded — data/classifier.pkl not found. "
            "Run: python scripts/train_classifier.py"
        )

    # 3. Pre-warm FAISS indices for all profiles
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(RulesProfile.profile_id))
            profile_ids = result.scalars().all()
            for pid in profile_ids:
                await FaissService.reload_index(pid, db)
        logger.info(f"FAISS pre-warming complete for {len(profile_ids)} profiles.")
    except Exception as e:
        logger.error(f"Failed to pre-warm FAISS indices: {e}")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Shutting down Moderation Service")


app = FastAPI(
    title="AI Moderation Microservice",
    description="Multilingual LLM-Powered Moderation Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
origins = settings.CORS_ORIGINS
if isinstance(origins, str):
    origins = [origins]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True if origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Routers
app.include_router(health.router,    prefix="/v1",          tags=["system"])
app.include_router(admin.router,     prefix="/v1/admin",    tags=["admin"])
app.include_router(profiles.router,  prefix="/v1/profiles", tags=["profiles"])
app.include_router(feedback.router,  prefix="/v1/feedback", tags=["feedback"])
app.include_router(moderate.router,  prefix="/v1/moderate", tags=["moderate"])