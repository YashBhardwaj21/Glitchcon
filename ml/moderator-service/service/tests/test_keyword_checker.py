"""
tests/test_keyword_checker.py
------------------------------
Unit tests for normalise_for_lookup used inside KeywordChecker.
Tests the lookup normaliser specifically for keyword matching use cases.
No DB, Redis, or network access needed.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pipeline.stage1_prefilter import normalise_for_lookup


class TestNormaliseForKeywordLookup:
    """
    Tests that verify normalise_for_lookup produces strings that would
    correctly match keyword set entries in Redis.
    """

    # ── Core keyword matching scenarios ──────────────────────────────────────
    def test_fuck_with_dots(self):
        """f.u.c.k should normalise to 'fuck' so it matches the banned word."""
        assert normalise_for_lookup("f.u.c.k") == "fuck"

    def test_fuck_with_spaces(self):
        """f u c k should normalise to 'fuck'."""
        assert normalise_for_lookup("f u c k") == "fuck"


    def test_asshole_leet_variant(self):
        """@ssh0le -> asshole."""
        result = normalise_for_lookup("@ssh0le")
        assert "asshole" in result

    def test_madarchod_variant(self):
        """m@d@rch0d should normalise to madarchod."""
        result = normalise_for_lookup("m@d@rch0d")
        assert result == "madarchod"

    def test_shit_with_dollar(self):
        """$hit -> shit."""
        assert normalise_for_lookup("$hit") == "shit"

    def test_repeated_chars_do_not_block_match(self):
        """fuuuuck should still match 'fuck' after collapsing."""
        assert normalise_for_lookup("fuuuuck") == "fuck"

    # ── Verify clean text still produces good output ──────────────────────────
    def test_normal_word_unchanged(self):
        """Ordinary words should pass through intact (lowercased)."""
        assert normalise_for_lookup("programming") == "programming"

    def test_mixed_case_lowercased(self):
        """Test that output is always lowercase."""
        assert normalise_for_lookup("PYTHON") == "python"

    # ── Seed script is_valid_keyword filter ──────────────────────────────────
    def test_is_valid_keyword_rejects_short(self):
        from scripts.seed_datasets import is_valid_keyword
        assert is_valid_keyword("ab") is False   # len < 4

    def test_is_valid_keyword_rejects_url(self):
        from scripts.seed_datasets import is_valid_keyword
        assert is_valid_keyword("https://t.co/abc") is False

    def test_is_valid_keyword_rejects_mention(self):
        from scripts.seed_datasets import is_valid_keyword
        assert is_valid_keyword("@BJP4India") is False

    def test_is_valid_keyword_rejects_hashtag(self):
        from scripts.seed_datasets import is_valid_keyword
        assert is_valid_keyword("#modi") is False

    def test_is_valid_keyword_rejects_pure_number(self):
        from scripts.seed_datasets import is_valid_keyword
        assert is_valid_keyword("1234") is False

    def test_is_valid_keyword_rejects_rt(self):
        from scripts.seed_datasets import is_valid_keyword
        assert is_valid_keyword("rt") is False

    def test_is_valid_keyword_accepts_real_abuse_word(self):
        from scripts.seed_datasets import is_valid_keyword
        assert is_valid_keyword("madarchod") is True

    def test_is_valid_keyword_accepts_normal_word(self):
        from scripts.seed_datasets import is_valid_keyword
        # Should accept ordinary 4+ letter words (filter is for structure, not semantics)
        assert is_valid_keyword("bhai") is True
