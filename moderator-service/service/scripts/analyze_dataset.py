"""
analyze_dataset.py
------------------
Standalone data analysis script for textdetox/multilingual_toxicity_dataset.
Run this BEFORE evaluate_pipeline.py to understand what you are working with.

Usage:
    python scripts/analyze_dataset.py
    python scripts/analyze_dataset.py --lang hi
    python scripts/analyze_dataset.py --lang en --sample 20
"""

import argparse
import sys
from collections import Counter

import pandas as pd
from datasets import load_dataset
from tqdm import tqdm

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

DATASET_ID   = "textdetox/multilingual_toxicity_dataset"
ALL_SPLITS   = ["en", "ru", "uk", "de", "es", "am", "zh", "ar",
                "hi", "it", "fr", "he", "hin", "tt", "ja"]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_split(lang: str) -> list[dict]:
    """Load a single language split and return as a list of dicts."""
    try:
        ds = load_dataset(DATASET_ID, split=lang)
        return list(ds)
    except Exception as e:
        print(f"  ⚠  Could not load split '{lang}': {e}")
        return []


def analyse_split(rows: list[dict], lang: str) -> dict:
    """Compute stats for one language split."""
    total   = len(rows)
    toxic   = sum(1 for r in rows if r.get("toxic") == 1)
    clean   = sum(1 for r in rows if r.get("toxic") == 0)
    unknown = total - toxic - clean

    lengths = [len(r.get("text", "")) for r in rows]
    avg_len = sum(lengths) / total if total else 0
    max_len = max(lengths) if lengths else 0
    min_len = min(lengths) if lengths else 0

    return {
        "lang":          lang,
        "total":         total,
        "toxic":         toxic,
        "clean":         clean,
        "unknown_label": unknown,
        "toxic_%":       round(100 * toxic / total, 1) if total else 0,
        "avg_len":       round(avg_len, 1),
        "min_len":       min_len,
        "max_len":       max_len,
    }


def print_separator(char="─", width=70):
    print(char * width)


def print_section(title: str):
    print_separator()
    print(f"  {title}")
    print_separator()


# ─────────────────────────────────────────────────────────────────────────────
# Full dataset overview
# ─────────────────────────────────────────────────────────────────────────────

def full_overview():
    print_section("FULL DATASET OVERVIEW — textdetox/multilingual_toxicity_dataset")
    print(f"  Splits available: {', '.join(ALL_SPLITS)}\n")

    stats = []
    for lang in tqdm(ALL_SPLITS, desc="Loading splits"):
        rows = load_split(lang)
        if rows:
            stats.append(analyse_split(rows, lang))

    df = pd.DataFrame(stats).set_index("lang")

    print("\n")
    print_section("PER-LANGUAGE STATISTICS")
    print(df.to_string())

    print("\n")
    print_section("TOTALS ACROSS ALL LANGUAGES")
    print(f"  Total rows:        {df['total'].sum():,}")
    print(f"  Total toxic:       {df['toxic'].sum():,}")
    print(f"  Total clean:       {df['clean'].sum():,}")
    print(f"  Overall toxic %:   {100 * df['toxic'].sum() / df['total'].sum():.1f}%")

    print("\n")
    print_section("LANGUAGES BY TOXIC % (descending)")
    sorted_df = df.sort_values("toxic_%", ascending=False)
    for lang, row in sorted_df.iterrows():
        bar = "█" * int(row["toxic_%"] / 2)
        print(f"  {lang:4}  {row['toxic_%']:5.1f}%  {bar}")

    print("\n")
    print_section("RECOMMENDATION FOR evaluate_pipeline.py")
    for lang, row in df.iterrows():
        if row["toxic"] >= 50 and row["clean"] >= 50:
            print(f"  ✅ {lang:4} — {row['toxic']} toxic / {row['clean']} clean — good for balanced eval")
        elif row["toxic"] < 50:
            print(f"  ⚠  {lang:4} — only {row['toxic']} toxic rows — not enough for 50/50 split")
        else:
            print(f"  ⚠  {lang:4} — only {row['clean']} clean rows — not enough for 50/50 split")


# ─────────────────────────────────────────────────────────────────────────────
# Single language deep dive
# ─────────────────────────────────────────────────────────────────────────────

def deep_dive(lang: str, sample_size: int = 10):
    print_section(f"DEEP DIVE — language: '{lang}'")

    rows = load_split(lang)
    if not rows:
        print(f"  No data found for split '{lang}'.")
        return

    stats = analyse_split(rows, lang)

    print(f"\n  Total rows:     {stats['total']}")
    print(f"  Toxic (1):      {stats['toxic']}  ({stats['toxic_%']}%)")
    print(f"  Clean (0):      {stats['clean']}")
    print(f"  Unknown label:  {stats['unknown_label']}")
    print(f"  Avg text len:   {stats['avg_len']} chars")
    print(f"  Min text len:   {stats['min_len']} chars")
    print(f"  Max text len:   {stats['max_len']} chars")

    # Label distribution
    label_counts = Counter(r.get("toxic") for r in rows)
    print(f"\n  Label distribution: {dict(label_counts)}")

    # Sample toxic rows
    toxic_rows = [r for r in rows if r.get("toxic") == 1]
    clean_rows = [r for r in rows if r.get("toxic") == 0]

    print(f"\n")
    print_section(f"SAMPLE TOXIC ROWS (first {sample_size})")
    if toxic_rows:
        for i, row in enumerate(toxic_rows[:sample_size], 1):
            text = row["text"][:120].replace("\n", " ")
            print(f"  [{i:2}] {text}")
    else:
        print("  None found.")

    print(f"\n")
    print_section(f"SAMPLE CLEAN ROWS (first {sample_size})")
    if clean_rows:
        for i, row in enumerate(clean_rows[:sample_size], 1):
            text = row["text"][:120].replace("\n", " ")
            print(f"  [{i:2}] {text}")
    else:
        print("  None found.")

    # Eval feasibility
    print(f"\n")
    print_section("EVAL FEASIBILITY")
    max_balanced = min(len(toxic_rows), len(clean_rows))
    print(f"  Max balanced eval size (50/50 split): {max_balanced * 2} rows")
    print(f"  ({max_balanced} toxic + {max_balanced} clean)")

    if max_balanced >= 50:
        print(f"\n  ✅ Sufficient for a 50/50 balanced evaluation.")
        print(f"\n  Use this in evaluate_pipeline.py:")
        print(f"""
    all_rows    = list(load_dataset("{DATASET_ID}", split="{lang}"))
    toxic_rows  = [r for r in all_rows if r["toxic"] == 1][:50]
    clean_rows  = [r for r in all_rows if r["toxic"] == 0][:50]
    test_rows   = toxic_rows + clean_rows
""")
    else:
        print(f"\n  ⚠  Only {max_balanced} balanced pairs available.")
        print(f"     Consider combining with another language split.")

    # Length distribution buckets
    print_section("TEXT LENGTH DISTRIBUTION")
    buckets = {"0–50": 0, "51–100": 0, "101–200": 0, "201–500": 0, "500+": 0}
    for r in rows:
        l = len(r.get("text", ""))
        if l <= 50:       buckets["0–50"]    += 1
        elif l <= 100:    buckets["51–100"]  += 1
        elif l <= 200:    buckets["101–200"] += 1
        elif l <= 500:    buckets["201–500"] += 1
        else:             buckets["500+"]    += 1

    total = len(rows)
    for bucket, count in buckets.items():
        pct = 100 * count / total
        bar = "█" * int(pct / 2)
        print(f"  {bucket:10}  {count:5} rows  ({pct:5.1f}%)  {bar}")


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Analyse textdetox/multilingual_toxicity_dataset"
    )
    parser.add_argument(
        "--lang",
        type=str,
        default=None,
        help="Language split to deep dive into (e.g. en, hi, hin, ta). "
             "If omitted, runs full overview of all splits."
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=10,
        help="Number of sample rows to print per category (default: 10)"
    )
    args = parser.parse_args()

    if args.lang:
        if args.lang not in ALL_SPLITS:
            print(f"Unknown split '{args.lang}'. Available: {', '.join(ALL_SPLITS)}")
            sys.exit(1)
        deep_dive(args.lang, args.sample)
    else:
        full_overview()


if __name__ == "__main__":
    main()