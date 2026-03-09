"""
gba1/app/api/v1/health.py
--------------------------
Health endpoint for GBA1 service.
"""
from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/health", summary="GBA1 Health Check")
async def health():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "moderator_url": settings.MODERATOR_BASE_URL,
    }
