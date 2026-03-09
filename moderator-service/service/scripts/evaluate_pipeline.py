import asyncio
import os
import sys
import time
from tqdm import tqdm
from typing import List, Tuple
from datasets import load_dataset
from sklearn.metrics import classification_report, f1_score
from redis.asyncio import Redis

# Setup path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.pipeline.engine import ModerationEngine
from app.schemas.moderate import ModerationRequest
from app.cache.profile_cache import ProfileCacheService
from app.cache.feedback_cache import FeedbackTemplateService
from app.core.config import settings
from app.core.logging import logger

async def run_evaluation():
    logger.info("=== Starting Pipeline Evaluation ===")
    
    # 1. Load Dataset (Subset of TextDetox English)
    # Using parquet-based source, sampling from middle where toxic examples exist
    logger.info("Loading textdetox dataset from HuggingFace...")
    # 1. Load Dataset — load full split, then filter for guaranteed balance
    logger.info("Loading textdetox dataset from HuggingFace...")
    en_ds = load_dataset("textdetox/multilingual_toxicity_dataset", split="en")
    all_rows = list(en_ds)
    
    # Build balanced test set — 50 toxic + 50 clean
    toxic_rows = [r for r in all_rows if r["toxic"] == 1][:50]
    clean_rows = [r for r in all_rows if r["toxic"] == 0][:50]
    test_rows  = toxic_rows + clean_rows
    
    logger.info(f"Test set: {len(toxic_rows)} toxic + {len(clean_rows)} clean = {len(test_rows)} total")
    
    # 2. Prepare connections
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    profile_id = "default_test_profile"
    
    async with AsyncSessionLocal() as db:
        # Load profile
        profile = await ProfileCacheService.get_profile(profile_id, db, redis)
        if not profile:
            logger.error("Profile 'default_test_profile' not found! Run seed_datasets.py first.")
            return

        y_true = []
        y_pred = []
        latencies = []
        
        logger.info("Running messages through pipeline (with 1s delay for rate limits)...")
        
        for idx, row in enumerate(tqdm(test_rows)):
            message = row['text']
            
            # Ground truth
            is_toxic = row['toxic'] == 1
            true_label = "BLOCK" if is_toxic else "ALLOW"
            
            # Form Request
            req = ModerationRequest(
                message=message,
                profile_id=profile_id,
                user_id=f"detox_{idx}"
            )
            
            # Run Engine
            try:
                start_time = time.perf_counter()
                response = await ModerationEngine.moderate(req, profile, db, redis)
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                
                latencies.append(latency_ms)
                y_true.append(true_label)
                y_pred.append(response.decision)
                
                # respect Groq free tier 30 RPM limit
                await asyncio.sleep(1.0)
                
                # Check for False Positives
                if response.decision != true_label and true_label == "ALLOW":
                    print(f"\nFALSE POSITIVE [{idx}]")
                    print(f"  Stage triggered : {response.stage_triggered}")
                    print(f"  Violated rule   : {response.violated_rule}")
                    print(f"  Confidence      : {response.confidence}")
                    print(f"  Message         : {message[:120]}")
                
                # Optional: print mismatches
                if response.decision != true_label:
                    logger.debug(f"Mismatch [{idx}]: True={true_label}, Pred={response.decision} (Stage: {response.stage_triggered}, Rule: {response.violated_rule}) -> Msg: {message[:100]}...")
            
            except Exception as e:
                logger.error(f"Error processing message {idx}: {e}")
                pass
                
        # 3. Calculate Metrics
        logger.info("=== Evaluation Results ===")
        print("\n--- Classification Report ---")
        print(classification_report(
            y_true, 
            y_pred, 
            labels=["ALLOW", "BLOCK"],
            target_names=["ALLOW", "BLOCK"],
            zero_division=0
        ))
        
        # Calculate F1 if we have BLOCK predictions
        if "BLOCK" in y_true and "BLOCK" in y_pred:
            f1 = f1_score(y_true, y_pred, pos_label="BLOCK")
            print(f"\nOverall F1 Score (BLOCK): {f1:.4f}")
        
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        print(f"Average Pipeline Latency: {avg_latency:.2f} ms")
        print(f"Total processed: {len(y_pred)}")
        
        logger.info("Evaluation Complete.")
        await redis.aclose()

if __name__ == "__main__":
    # Workaround for Windows asyncio crash on exit
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_evaluation())
