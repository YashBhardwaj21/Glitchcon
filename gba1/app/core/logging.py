"""
gba1/app/core/logging.py
------------------------
Structured logging setup (mirrors the moderator-service pattern).
"""
import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


logger = logging.getLogger("gba1")
