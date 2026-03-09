from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, logger

from app.api.v1 import health
from app.api.v1 import admin

# Initialize structured logging
setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Starting AI Moderation Microservice")
    # Resources initialized here (Redis pool, LLM loading, FAISS loading) in subsequent phases
    yield
    # Shutdown actions
    logger.info("Shutting down Moderation Service")


app = FastAPI(
    title="AI Moderation Microservice",
    description="Multilingual LLM-Powered Moderation Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Routers
app.include_router(health.router, prefix="/v1", tags=["system"])
app.include_router(admin.router, prefix="/v1/admin", tags=["admin"])
