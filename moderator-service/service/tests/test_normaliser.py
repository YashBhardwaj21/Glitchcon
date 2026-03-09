"""
tests/test_normaliser.py
------------------------
Unit tests for the leet-speak / bypass normaliser in stage1_prefilter.py.
No DB, Redis, or network access needed.
"""
import sys
import os

# Allow importing from app/ without installing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pipeline.stage1_prefilter import normalise_for_lookup


class TestNormaliseForLookup:
    # ── Leet-speak substitution ───────────────────────────────────────────────
    def test_at_sign_becomes_a(self):
        assert "asshole" in normalise_for_lookup("@ssh0le")

    def test_zero_becomes_o(self):
        assert normalise_for_lookup("sh0t") == "shot"

    def test_dollar_becomes_s(self):
        assert normalise_for_lookup("$hit") == "shit"

    def test_three_becomes_e(self):
        assert normalise_for_lookup("s3x") == "sex"

    def test_combined_leet(self):
        result = normalise_for_lookup("@$$h0le")
        assert "asshole" in result

    # ── Repeated character collapsing ─────────────────────────────────────────
    def test_repeated_chars_collapsed(self):
        assert normalise_for_lookup("fuuuuck") == "fuck"

    def test_double_char_preserved(self):
        # Only 3+ repetitions should collapse; 2 is kept
        result = normalise_for_lookup("fuuck")
        assert result == "fuuck"  # 2 repeats, not collapsed

    # ── Spaces between letters ────────────────────────────────────────────────
    def test_spaces_between_letters_removed(self):
        assert normalise_for_lookup("f u c k") == "fuck"

    def test_spaces_not_removed_across_words(self):
        # Spaces between actual words should not be fully collapsed
        result = normalise_for_lookup("hello world")
        assert " " in result

    # ── Punctuation separators ────────────────────────────────────────────────
    def test_dots_between_letters_removed(self):
        assert normalise_for_lookup("f.u.c.k") == "fuck"

    def test_dashes_between_letters_removed(self):
        assert normalise_for_lookup("f-u-c-k") == "fuck"

    def test_underscores_between_letters_removed(self):
        assert normalise_for_lookup("f_u_c_k") == "fuck"

    # ── Combined bypass attempts ──────────────────────────────────────────────
    def test_full_bypass_combination(self):
        # "m@d@rch0d" → "madarchod"
        result = normalise_for_lookup("m@d@rch0d")
        assert result == "madarchod"

    def test_spaced_leet(self):
        # "f u c k" → "fuck"
        result = normalise_for_lookup("f u c k")
        assert result == "fuck"

    # ── Idempotency ───────────────────────────────────────────────────────────
    def test_clean_text_unchanged(self):
        # Normal text should pass through without alteration (modulo lowercase)
        assert normalise_for_lookup("Hello World") == "hello world"

    def test_lowercase_applied(self):
        assert normalise_for_lookup("FUCK") == "fuck"
