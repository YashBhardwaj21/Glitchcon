from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import secrets
import bcrypt

from app.db.session import get_db
from app.db.models import APIKey

router = APIRouter()

class APIKeyCreate(BaseModel):
    app_name: str
    profile_id_whitelist: list[str] = []
    rate_limit_per_min: int = 60

class APIKeyResponse(BaseModel):
    id: int
    app_name: str
    api_key: str  # Plaintext key - shown only once!

@router.post("/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: APIKeyCreate,
    db: AsyncSession = Depends(get_db)
    # Note: In a real system, this endpoint would be protected by a super-admin token.
):
    # Generate a strong 32-byte secret
    raw_secret = secrets.token_hex(32)
    
    # We will format the physical key as <id>.<raw_secret> so we can look it up by ID
    # But we need the ID first. So we create the DB row with a dummy hash, 
    # then get the ID, then update the hash.
    
    salt = bcrypt.gensalt()
    key_hash = bcrypt.hashpw(raw_secret.encode('utf-8'), salt).decode('utf-8')
    
    new_key = APIKey(
        app_name=data.app_name,
        key_hash=key_hash, # Temporary
        profile_id_whitelist=data.profile_id_whitelist,
        rate_limit_per_min=data.rate_limit_per_min
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)
    
    # Physical key to return to user
    full_api_key = f"{new_key.id}.{raw_secret}"
    
    # Store the bcrypt hash of the full_api_key
    final_hash = bcrypt.hashpw(full_api_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    new_key.key_hash = final_hash
    await db.commit()
    
    return APIKeyResponse(
        id=new_key.id,
        app_name=new_key.app_name,
        api_key=full_api_key
    )
