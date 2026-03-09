import asyncio
import os
import sys
import time
from typing import List, Tuple
from datasets import load_dataset
from sklearn.metrics import classification_report, f1_score
from redis.asyncio import Redis

# Setup path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import async_session_maker
from app.pipeline.engine import ModerationEngine
from app.schemas.moderate import ModerationRequest
from app.cache.profile_cache import ProfileCacheService
from app.core.config import settings
from app.core.logging import logger

async def run_evaluation():
    logger.info("=== Starting Pipeline Evaluation ===")
    
    # 1. Load Dataset (Subset of Jigsaw Toxic Comment)
    # Using 'train' split but taking only 100 samples to keep it fast for testing
    logger.info("Loading Jigsaw dataset (100 samples) from HuggingFace...")
    dataset = load_dataset("jigsaw_toxicity_pred", split="train[:100]", trust_remote_code=True)
    
    # 2. Prepare connections
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    profile_id = "default_test_profile"
    
    async with async_session_maker() as db:
        
        # Load profile
        profile = await ProfileCacheService.get_profile(profile_id, db, redis)
        if not profile:
            logger.error("Profile 'default_test_profile' not found! Run seed_datasets.py first.")
            return

        y_true = []
        y_pred = []
        latencies = []
        
        logger.info("Running messages through pipeline...")
        
        for idx, row in enumerate(dataset):
            message = row['comment_text']
            
            # Ground truth: Jigsaw has several toxicity flags (toxic, severe_toxic, obscene, etc.)
            # If any are 1, it's toxic (BLOCK), else ALLOW.
            is_toxic = any([
                row['toxic'], row['severe_toxic'], row['obscene'], 
                row['threat'], row['insult'], row['identity_hate']
            ])
            true_label = "BLOCK" if is_toxic else "ALLOW"
            
            # Form Request
            req = ModerationRequest(
                message=message,
                profile_id=profile_id,
                user_id=f"jigsaw_{idx}"
            )
            
            # Run Engine
            try:
                start_time = time.perf_counter()
                response = await ModerationEngine.moderate(req, profile, db, redis)
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                
                latencies.append(latency_ms)
                y_true.append(true_label)
                y_pred.append(response.decision)
                
                # Optional: print mismatches
                if response.decision != true_label:
                    logger.debug(f"Mismatch [{idx}]: True={true_label}, Pred={response.decision} (Stage: {response.stage_triggered}, Rule: {response.violated_rule}) -> Msg: {message[:100]}...")
            
            except Exception as e:
                logger.error(f"Error processing message {idx}: {e}")
                # We won't count failed pipeline requests in the accuracy score for this simple test
                pass
                
        # 3. Calculate Metrics
        logger.info("=== Evaluation Results ===")
        print("\n--- Classification Report ---")
        print(classification_report(y_true, y_pred, labels=["ALLOW", "BLOCK"]))
        
        f1 = f1_score(y_true, y_pred, pos_label="BLOCK")
        
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        print(f"\nOverall F1 Score (BLOCK): {f1:.4f}")
        print(f"Average Pipeline Latency: {avg_latency:.2f} ms")
        print(f"Total processed: {len(y_pred)}")
        
        logger.info("Evaluation Complete.")
        await redis.aclose()

if __name__ == "__main__":
    # Workaround for Windows asyncio crash on exist
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_evaluation())
