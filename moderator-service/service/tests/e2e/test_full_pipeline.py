"""
tests/e2e/test_full_pipeline.py
-------------------------------
End-to-End integration tests for the full moderation pipeline.
Requires a live, running instance of the moderator-service and a valid API key.

Usage:
    export MODERATOR_BASE_URL="http://localhost:8001"
    export MODERATOR_API_KEY="1.your_test_key"
    pytest tests/e2e -v -m e2e
"""
import os
import pytest
from httpx import AsyncClient

from moderator_sdk import ModerationClient
from moderator_sdk.models import ModerationRequest
from moderator_sdk.exceptions import ModerationClientError

# ─── Configuration ─────────────────────────────────────────────────────────────

BASE_URL = os.getenv("MODERATOR_BASE_URL", "http://localhost:8001")
API_KEY  = os.getenv("MODERATOR_API_KEY")

# Skip all tests in this file if no API key is provided
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not API_KEY,
        reason="E2E tests require MODERATOR_API_KEY to be set in the environment"
    )
]

# We need a test profile to exist for these tests.
# The seed_profiles.py script creates 'wele_general', 'wele_sports', etc.
PROFILE_ID = "wele_general"


@pytest.fixture
async def sdk_client():
    """Provides a configured async SDK client."""
    async with ModerationClient(base_url=BASE_URL, api_key=API_KEY, timeout=15.0) as client:
        # Verify the service is up first
        await client.health_check()
        yield client


# ─── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_english_allow(sdk_client: ModerationClient):
    """Clean English message should pass (ALLOW)."""
    req = ModerationRequest(
        message="Hey everyone, what time does the match start tomorrow?",
        profile_id=PROFILE_ID,
        user_id="test_user_en1",
    )
    resp = await sdk_client.moderate(req)

    assert resp.decision == "ALLOW"
    assert resp.detected_language == "en"


@pytest.mark.asyncio
async def test_e2e_hindi_allow(sdk_client: ModerationClient):
    """Clean Hindi message should pass (ALLOW) and correctly detect 'hi'."""
    req = ModerationRequest(
        message="कल मैच कितने बजे शुरू होगा?",
        profile_id=PROFILE_ID,
        user_id="test_user_hi1",
    )
    resp = await sdk_client.moderate(req)

    assert resp.decision == "ALLOW"
    assert resp.detected_language == "hi"


@pytest.mark.asyncio
async def test_e2e_pii_block_stage1(sdk_client: ModerationClient):
    """Message with obvious PII should be blocked immediately by Stage 1."""
    req = ModerationRequest(
        message="You can reach me at 9876543210 or email me at user@gmail.com",
        profile_id=PROFILE_ID,
        user_id="test_user_pii",
    )
    resp = await sdk_client.moderate(req)

    assert resp.decision == "BLOCK"
    assert resp.stage_triggered == "stage1"
    assert resp.violated_rule == "pii_leak"


@pytest.mark.asyncio
async def test_e2e_profanity_block_stage1(sdk_client: ModerationClient):
    """Message with obvious profanity should be blocked by Stage 1 (wordlist)."""
    # Assuming 'asshole' is in the default en profanity list
    req = ModerationRequest(
        message="Why are you acting like such an asshole today?",
        profile_id=PROFILE_ID,
        user_id="test_user_profanity",
    )
    resp = await sdk_client.moderate(req)

    assert resp.decision == "BLOCK"
    assert resp.stage_triggered == "stage1"
    assert "profanity" in (resp.violated_rule or "").lower()


@pytest.mark.asyncio
async def test_e2e_leet_bypass_block(sdk_client: ModerationClient):
    """Message attempting leet-speak bypass should still be caught by the normaliser."""
    req = ModerationRequest(
        message="you are such a b1tch",
        profile_id=PROFILE_ID,
        user_id="test_user_leet",
    )
    resp = await sdk_client.moderate(req)

    assert resp.decision == "BLOCK"
    assert resp.stage_triggered == "stage1"


@pytest.mark.asyncio
async def test_e2e_llm_moderation(sdk_client: ModerationClient):
    """
    Subtle hate speech or threat should bypass Stage 1 and be blocked by Stage 2 (LLM).
    "I will destroy you and your family" usually triggers a threat rule.
    """
    req = ModerationRequest(
        message="I know where you live and I am coming to destroy you and your family.",
        profile_id=PROFILE_ID,
        user_id="test_user_threat",
    )
    resp = await sdk_client.moderate(req)

    assert resp.decision == "BLOCK"
    # Depending on FAISS overlap, it might be stage2_llm or stage3_faiss, but definitely not stage1
    assert resp.stage_triggered != "stage1"
    assert resp.confidence is not None


@pytest.mark.asyncio
async def test_e2e_spam_flood_rate_limit(sdk_client: ModerationClient):
    """
    Sending identical/rapid messages from the same user should trigger the
    sliding window spam filter in Redis (Stage 1).
    """
    user_id = "test_user_spammer_99"
    msg     = "Buy cheap crypto here!"

    # The wele_general profile has a spam_limit of 5 per 60s.
    # We send 6 messages; the 6th should be blocked for spam.
    results = []
    for _ in range(6):
        req = ModerationRequest(message=msg, profile_id=PROFILE_ID, user_id=user_id)
        resp = await sdk_client.moderate(req)
        results.append(resp)

    # First 5 might be ALLOW or BLOCK (depending on if crypto triggers a rule),
    # but the 6th MUST be blocked specifically for 'spam'.
    last_resp = results[-1]
    assert last_resp.decision == "BLOCK"
    assert last_resp.stage_triggered == "stage1"
    assert last_resp.violated_rule == "spam_flood"


@pytest.mark.asyncio
async def test_e2e_batch_moderation(sdk_client: ModerationClient):
    """Test concurrent batch execution using the SDK batch_moderate method."""
    reqs = [
        ModerationRequest(message="Hello friend", profile_id=PROFILE_ID, user_id="b1"),
        ModerationRequest(message="Call 9876543210 right now", profile_id=PROFILE_ID, user_id="b2"),
        ModerationRequest(message="What is the homework for today", profile_id=PROFILE_ID, user_id="b3"),
    ]

    batch = await sdk_client.batch_moderate(reqs)

    assert batch.total == 3
    assert batch.success_count == 3
    assert batch.error_count == 0

    assert batch.results[0].decision == "ALLOW"
    assert batch.results[1].decision == "BLOCK"  # PII
    assert batch.results[2].decision == "ALLOW"
