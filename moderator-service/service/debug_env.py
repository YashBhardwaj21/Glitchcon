import sys
import os
import asyncio
from redis.asyncio import Redis

# Add service directory to path
sys.path.append(os.getcwd())

async def debug():
    print("--- Environment Debug ---")
    print(f"Python: {sys.version}")
    print(f"CWD: {os.getcwd()}")
    
    try:
        from app.core.config import settings
        print(f"Settings loaded. Provider: {settings.LLM_PROVIDER}")
        print(f"Redis URL: {settings.REDIS_URL}")
        
        from app.pipeline.engine import ModerationEngine
        print("ModerationEngine imported successfully.")
        
        from app.llm.providers.groq_provider import GroqProvider
        provider = GroqProvider()
        print("GroqProvider initialized.")
        
        print("Testing Redis...")
        redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis.ping()
        print("Redis PING success.")
        await redis.aclose()
        
    except Exception as e:
        print(f"DEBUG ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug())
