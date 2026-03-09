from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from redis.asyncio import Redis

from app.db.session import get_db
from app.db.models import FeedbackTemplate, APIKey
from app.api.deps import verify_api_key
from app.api.v1.health import get_redis
from app.cache.feedback_cache import FeedbackTemplateService
from app.schemas.feedback import FeedbackTemplateCreate, FeedbackTemplateUpdate, FeedbackTemplateResponse

router = APIRouter()

@router.post("/", response_model=FeedbackTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_feedback_template(
    template_in: FeedbackTemplateCreate,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key),
    redis: Redis = Depends(get_redis)
):
    """
    Creates a new feedback message template for a specific language and violation type (rule_type).
    """
    stmt = select(FeedbackTemplate).where(
        FeedbackTemplate.rule_type == template_in.rule_type,
        FeedbackTemplate.language_code == template_in.language_code
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Template for rule '{template_in.rule_type}' and language '{template_in.language_code}' already exists",
        )
        
    db_template = FeedbackTemplate(**template_in.model_dump())
    db.add(db_template)
    await db.commit()
    await db.refresh(db_template)
    
    return FeedbackTemplateResponse.model_validate(db_template)

@router.get("/{rule_type}/{language_code}", response_model=FeedbackTemplateResponse)
async def get_feedback_template(
    rule_type: str,
    language_code: str,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key),
    redis: Redis = Depends(get_redis)
):
    """
    Returns the feedback template for a specific rule_type and language.
    """
    template = await FeedbackTemplateService.get_template(rule_type, language_code, db, redis)
    if not template:
        raise HTTPException(status_code=404, detail="Feedback template not found")
        
    return template

@router.patch("/{rule_type}/{language_code}", response_model=FeedbackTemplateResponse)
async def update_feedback_template(
    rule_type: str,
    language_code: str,
    template_in: FeedbackTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key),
    redis: Redis = Depends(get_redis)
):
    """
    Updates an existing feedback template and invalidates its cache.
    """
    stmt = select(FeedbackTemplate).where(
        FeedbackTemplate.rule_type == rule_type,
        FeedbackTemplate.language_code == language_code
    )
    result = await db.execute(stmt)
    db_template = result.scalar_one_or_none()
    
    if not db_template:
        raise HTTPException(status_code=404, detail="Feedback template not found")
        
    db_template.message_template = template_in.message_template
        
    await db.commit()
    await db.refresh(db_template)
    
    # Invalidate cache
    await FeedbackTemplateService.invalidate(rule_type, language_code, redis)
    
    return FeedbackTemplateResponse.model_validate(db_template)

@router.delete("/{rule_type}/{language_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feedback_template(
    rule_type: str,
    language_code: str,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(verify_api_key),
    redis: Redis = Depends(get_redis)
):
    """
    Deletes an existing feedback template.
    """
    stmt = select(FeedbackTemplate).where(
        FeedbackTemplate.rule_type == rule_type,
        FeedbackTemplate.language_code == language_code
    )
    result = await db.execute(stmt)
    db_template = result.scalar_one_or_none()
    
    if not db_template:
        raise HTTPException(status_code=404, detail="Feedback template not found")
        
    await db.delete(db_template)
    await db.commit()
    
    # Invalidate cache
    await FeedbackTemplateService.invalidate(rule_type, language_code, redis)
