"""
gba1/scripts/seed_profiles.py
------------------------------
Seeds the AI Moderation Microservice with multilingual rules profiles
for all GBA1 demo groups.

Profiles created:
    wele_general    — General community chat (en/hi/hi-en)
    wele_sports     — Sports discussion group (en/hi/hi-en)
    wele_study      — Study / academic group (en/hi/ta/te/kn/ml)
    telegram_general — Telegram bot integration (en/hi/hi-en)

Usage (with moderator-service running):
    python gba1/scripts/seed_profiles.py
    python gba1/scripts/seed_profiles.py --base-url http://prod-service:8001
    python gba1/scripts/seed_profiles.py --dry-run

The script is idempotent: it skips profiles that already exist (HTTP 400).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

import httpx


# ─── Profile definitions ──────────────────────────────────────────────────────

GLOBAL_RULES = [
    "No hate speech, slurs, or derogatory language toward any group",
    "No threats, incitement to violence, or self-harm content",
    "No sharing of personal information (phone, email, Aadhaar, bank details)",
    "No sexual or explicit content",
    "No spam or repeated identical messages",
]

PROFILES: list[dict[str, Any]] = [
    # ── wele_general ─────────────────────────────────────────────────────────
    {
        "profile_id":   "wele_general",
        "group_topic":  "General community conversation and casual discussion",
        "global_rules": GLOBAL_RULES,
        "group_rules":  [
            "Keep conversations respectful and constructive",
            "No promotion of competing services or spam-level advertising",
            "Political and religious debate must remain civil and fact-based",
            "No sharing of unverified news or misinformation",
        ],
        "supported_languages":  ["en", "hi", "hi-en"],
        "keywords_by_language": {
            "en":    [],   # populated by load_wordlists.py
            "hi":    [],
            "hi-en": [],
        },
        "spam_limit":    5,
        "spam_window_s": 60,
        "faiss_threshold":                0.72,
        "llm_confidence_threshold_en":    0.65,
        "llm_confidence_threshold_indic": 0.60,
    },
    # ── wele_sports ───────────────────────────────────────────────────────────
    {
        "profile_id":   "wele_sports",
        "group_topic":  "Sports discussion — cricket, football, kabaddi, and other sports",
        "global_rules": GLOBAL_RULES,
        "group_rules":  [
            "Support healthy debate between fans of different teams",
            "Trolling or personal attacks on players are not allowed",
            "No match-fixing rumours or unverified betting content",
            "Celebrate wins gracefully — avoid taunting opposing fan bases",
            "No racist or casteist remarks about athletes",
        ],
        "supported_languages":  ["en", "hi", "hi-en"],
        "keywords_by_language": {
            "en":    [],
            "hi":    [],
            "hi-en": [],
        },
        "spam_limit":    8,    # sports groups are more active
        "spam_window_s": 60,
        "faiss_threshold":                0.70,
        "llm_confidence_threshold_en":    0.65,
        "llm_confidence_threshold_indic": 0.60,
    },
    # ── wele_study ────────────────────────────────────────────────────────────
    {
        "profile_id":   "wele_study",
        "group_topic":  "Academic study group for students across Indian languages",
        "global_rules": GLOBAL_RULES,
        "group_rules":  [
            "Stay on topic — exam preparation, study materials, academic questions",
            "No sharing of paid course materials or pirated content",
            "Constructive peer feedback only — no discouraging or belittling",
            "No advertisement of coaching centres or paid tutoring",
            "Be patient with beginners — everyone is here to learn",
        ],
        "supported_languages":  ["en", "hi", "hi-en", "ta", "te", "kn", "ml"],
        "keywords_by_language": {
            "en":    [],
            "hi":    [],
            "hi-en": [],
            "ta":    [],
            "te":    [],
            "kn":    [],
            "ml":    [],
        },
        "spam_limit":    5,
        "spam_window_s": 60,
        "faiss_threshold":                0.75,   # stricter — academic context
        "llm_confidence_threshold_en":    0.70,
        "llm_confidence_threshold_indic": 0.65,
    },
    # ── telegram_general ─────────────────────────────────────────────────────
    {
        "profile_id":   "telegram_general",
        "group_topic":  "Telegram bot moderation for general-purpose groups",
        "global_rules": GLOBAL_RULES,
        "group_rules":  [
            "No forwarded chain messages or viral misinformation",
            "No unsolicited DM promotions or referral links",
            "Bots and automation must be approved by the group admin",
            "No impersonation of admins or other members",
        ],
        "supported_languages":  ["en", "hi", "hi-en"],
        "keywords_by_language": {
            "en":    [],
            "hi":    [],
            "hi-en": [],
        },
        "spam_limit":    4,    # Telegram groups tend to get spammed harder
        "spam_window_s": 30,
        "faiss_threshold":                0.72,
        "llm_confidence_threshold_en":    0.65,
        "llm_confidence_threshold_indic": 0.60,
    },
]


# ─── Seeder ───────────────────────────────────────────────────────────────────

async def seed(base_url: str, api_key: str, dry_run: bool) -> None:
    print(f"\n{'='*60}")
    print(f"  GBA1 Multilingual Profile Seeder")
    print(f"  Service : {base_url}")
    print(f"  Dry run : {dry_run}")
    print(f"{'='*60}\n")

    if dry_run:
        for p in PROFILES:
            print(f"  [DRY-RUN] Would seed: {p['profile_id']!r} "
                  f"— languages: {p['supported_languages']}")
        print("\nDry run complete. No changes made.")
        return

    headers = {
        "X-API-Key":    api_key,
        "Content-Type": "application/json",
    }

    created, skipped, failed = 0, 0, 0

    async with httpx.AsyncClient(base_url=base_url, timeout=15.0, headers=headers) as c:
        for profile in PROFILES:
            pid = profile["profile_id"]
            try:
                resp = await c.post("/v1/profiles/", json=profile)

                if resp.status_code == 201:
                    print(f"  ✅ Created  | {pid:20s} — "
                          f"languages: {profile['supported_languages']}")
                    created += 1

                elif resp.status_code == 400:
                    body = resp.json()
                    if "already exists" in str(body.get("detail", "")).lower():
                        print(f"  ⏭  Exists   | {pid:20s} — skipping")
                        skipped += 1
                    else:
                        print(f"  ❌ Failed   | {pid:20s} — {body}")
                        failed += 1

                else:
                    print(f"  ❌ HTTP {resp.status_code} | {pid:20s} — {resp.text[:120]}")
                    failed += 1

            except httpx.RequestError as exc:
                print(f"  ❌ Network  | {pid:20s} — {exc}")
                failed += 1

    print(f"\n{'─'*60}")
    print(f"  Created : {created}")
    print(f"  Skipped : {skipped} (already exist)")
    print(f"  Failed  : {failed}")
    print(f"{'─'*60}\n")

    if failed:
        print("  ⚠  Some profiles failed. Check the output above.")
        sys.exit(1)
    else:
        print("  🎉 Seed complete!\n")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed GBA1 multilingual moderation profiles"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8001",
        help="AI Moderation Service base URL (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key (falls back to MODERATOR_API_KEY env var)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be seeded without making any requests",
    )
    args = parser.parse_args()

    api_key = args.api_key
    if not api_key and not args.dry_run:
        import os
        api_key = os.environ.get("MODERATOR_API_KEY", "")
        if not api_key:
            print("ERROR: --api-key or MODERATOR_API_KEY env var required.")
            sys.exit(1)

    asyncio.run(seed(args.base_url, api_key or "", args.dry_run))


if __name__ == "__main__":
    main()
