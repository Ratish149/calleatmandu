"""Lightweight, offline heuristics for evaluating AI reply quality.

This module is for evaluation and tests only — it is never used to rewrite or
patch production replies. It scores a reply on the dimensions the product cares
about: naturalness signals, language/script consistency, conciseness and
whether it left obvious template placeholders behind.
"""

import re
from typing import Any, Dict, List, Tuple

DEVANAGARI_RANGE = re.compile(r"[\u0900-\u097F]")

# Common spoken Nepali particles / function words. Their presence is a signal
# that a Latin-letter reply is actually romanized Nepali rather than English.
ROMANIZED_MARKERS = frozenset(
    {
        "hai",
        "ni",
        "la",
        "ta",
        "cha",
        "chha",
        "ho",
        "huncha",
        "hunchha",
        "chhan",
        "kati",
        "kasari",
        "kina",
        "ma",
        "ko",
        "ka",
        "pani",
        "tapai",
        "tapailai",
        "hajur",
        "hus",
        "garera",
        "garna",
        "bhandinchu",
        "pathaunus",
        "dinus",
        "milcha",
        "man",
        "thaha",
        "bhayo",
        "pugyo",
        "sakcha",
        "lagcha",
        "parcha",
    }
)

# Everyday English words that Nepalis genuinely mix into conversation. A few of
# these are expected in a natural reply; a flood of them suggests the model
# slipped into English.
ENGLISH_LOANWORDS = frozenset(
    {
        "delivery",
        "order",
        "menu",
        "time",
        "payment",
        "discount",
        "cancel",
        "check",
        "price",
        "offer",
        "cash",
        "online",
        "location",
        "traffic",
        "min",
        "item",
        "options",
        "option",
        "call",
    }
)

PLACEHOLDER_RE = re.compile(r"\bxxx\b|<[a-z_]+>|\[[a-z_]+\]", re.IGNORECASE)

# Representative customer messages used to compare reply quality. They map to
# the real intents customers ask about over DM.
REPRESENTATIVE_CASES: List[Tuple[str, str]] = [
    ("khaana kati chhito deliver huncha?", "delivery_time"),
    ("tapaiko menu pathaunus na", "menu"),
    ("chicken momo kati parcha?", "price"),
    ("payment kasari garni?", "payment"),
    ("kunai discount cha?", "discount"),
    ("mero order kahaan pugyo?", "order_status"),
    ("order cancel garna milcha?", "cancellation"),
]

_SENTENCE_SPLIT = re.compile(r"[.!?\n]+")


def _words(text: str) -> List[str]:
    return re.findall(r"[a-z]+", text.lower())


def _sentence_count(text: str) -> int:
    return len([chunk for chunk in _SENTENCE_SPLIT.split(text) if chunk.strip()])


def assess_reply(text: Any, language: str = "romanized") -> Dict[str, Any]:
    """Return simple quality metrics for a candidate reply.

    The result is intentionally heuristic and is meant to support manual review
    and regression tests, not to gate or mutate production output.
    """
    if not isinstance(text, str) or not text.strip():
        return {
            "empty": True,
            "word_count": 0,
            "sentence_count": 0,
            "has_devanagari": False,
            "romanized_marker_hits": 0,
            "english_loanword_hits": 0,
            "english_loanword_ratio": 0.0,
            "has_placeholder": False,
            "is_concise": False,
            "language_consistent": False,
            "naturalness_score": 0,
        }

    cleaned = text.strip()
    words = _words(cleaned)
    word_count = len(words)
    devanagari_hits = len(DEVANAGARI_RANGE.findall(cleaned))
    romanized_hits = sum(1 for word in words if word in ROMANIZED_MARKERS)
    english_hits = sum(1 for word in words if word in ENGLISH_LOANWORDS)
    sentence_count = _sentence_count(cleaned)
    english_ratio = (english_hits / word_count) if word_count else 0.0

    is_concise = word_count <= 60 and sentence_count <= 3

    if language == "devanagari":
        language_consistent = devanagari_hits > 0
    else:
        language_consistent = devanagari_hits == 0 and romanized_hits > 0

    # Naturalness heuristic: use spoken Nepali particles and mix in a modest
    # amount of everyday English (0-40% of words) rather than pure English.
    naturalness_score = 0
    if romanized_hits > 0:
        naturalness_score += 1
    if 0.0 < english_ratio <= 0.4:
        naturalness_score += 1
    if is_concise:
        naturalness_score += 1

    return {
        "empty": False,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "has_devanagari": devanagari_hits > 0,
        "romanized_marker_hits": romanized_hits,
        "english_loanword_hits": english_hits,
        "english_loanword_ratio": round(english_ratio, 3),
        "has_placeholder": bool(PLACEHOLDER_RE.search(cleaned)),
        "is_concise": is_concise,
        "language_consistent": language_consistent,
        "naturalness_score": naturalness_score,
    }
