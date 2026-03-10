"""
tests/test_faiss_result.py
--------------------------
Unit tests for the FAISSResult named tuple from stage3_faiss.py.
No DB, network, or Redis access needed.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pipeline.stage3_faiss import FAISSResult, FAISS_HARD_BLOCK_THRESHOLD, FAISS_SOFT_BLOCK_THRESHOLD


class TestFAISSResult:
    # ── Named tuple construction ──────────────────────────────────────────────
    def test_block_result(self):
        result = FAISSResult(decision="BLOCK", topic="crypto scam", score=0.85)
        assert result.decision == "BLOCK"
        assert result.topic == "crypto scam"
        assert result.score == 0.85

    def test_hint_result(self):
        result = FAISSResult(decision="HINT", topic="drug dealing", score=0.71)
        assert result.decision == "HINT"
        assert result.topic == "drug dealing"
        assert result.score == 0.71

    def test_allow_result(self):
        result = FAISSResult(decision="ALLOW", topic=None, score=0.40)
        assert result.decision == "ALLOW"
        assert result.topic is None

    # ── Backward-compat: old callers used `is_blocked = result[0]` style ─────
    def test_block_decision_is_truthy_string(self):
        result = FAISSResult(decision="BLOCK", topic="violence", score=0.90)
        assert (result.decision == "BLOCK") is True

    def test_hint_is_not_block(self):
        result = FAISSResult(decision="HINT", topic="violence", score=0.71)
        assert (result.decision == "BLOCK") is False

    def test_allow_is_not_block(self):
        result = FAISSResult(decision="ALLOW", topic=None, score=0.30)
        assert (result.decision == "BLOCK") is False

    # ── Threshold constants sanity check ─────────────────────────────────────
    def test_hard_block_above_soft(self):
        assert FAISS_HARD_BLOCK_THRESHOLD > FAISS_SOFT_BLOCK_THRESHOLD

    def test_hard_threshold_value(self):
        assert FAISS_HARD_BLOCK_THRESHOLD == 0.82

    def test_soft_threshold_value(self):
        assert FAISS_SOFT_BLOCK_THRESHOLD == 0.65

    # ── Zone boundary logic ───────────────────────────────────────────────────
    def test_score_above_hard_is_block_zone(self):
        score = 0.90
        assert score >= FAISS_HARD_BLOCK_THRESHOLD

    def test_score_in_soft_zone(self):
        score = 0.72
        assert FAISS_SOFT_BLOCK_THRESHOLD <= score < FAISS_HARD_BLOCK_THRESHOLD

    def test_score_below_soft_is_allow_zone(self):
        score = 0.55
        assert score < FAISS_SOFT_BLOCK_THRESHOLD
