"""Deterministic cleanup for the IELTS Task 2 topic bank (see scripts/build_ielts_topics.py).

Source: the `topic` column of the Hugging Face dataset btnotpt/ielts_task_2 (Apache-2.0),
questions typed in by IELTS test takers together with their essays.
"""
import difflib
import re
from typing import Dict, Optional

MIN_LEN, MAX_LEN = 60, 700
DUPLICATE_JACCARD = 0.7  # word overlap at which two topics count as the same question
MAX_FIX_CHANGE = 0.15    # a spelling/grammar fix may change at most this share of the text

_VERSION_TAG = re.compile(r"\s*v\.\s*\d+\s*$", re.I)
_TASK1 = re.compile(
    r"\b(summari[sz]e|bar chart|line graph|pie chart|"
    r"the (chart|graph|table|diagram|map|plan|process)s? (below|above|show))", re.I)
_TOEFL = re.compile(r"specific reasons and examples|use specific", re.I)
# Mojibake from a UTF-8 / Latin-1 mix-up ("havenât") or replacement characters.
_BROKEN = re.compile(r"[À-ÿ�]")


def clean_prompt(text: str) -> str:
    text = _VERSION_TAG.sub("", text.strip())
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1].upper() + text[1:]


def is_candidate(text: str) -> bool:
    """A full Task 2 question: not Task 1 or TOEFL, not broken, not truncated, not a bare title."""
    if not MIN_LEN <= len(text) <= MAX_LEN:
        return False
    if _TASK1.search(text) or _TOEFL.search(text) or _BROKEN.search(text):
        return False
    return text.rstrip()[-1] in ".?!)"


def _words(text: str) -> frozenset:
    return frozenset(w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2)


def dedupe_variants(counts: Dict[str, int]) -> Dict[str, int]:
    """Merge copies of the same question; keep the most-written wording and sum the counts."""
    kept: Dict[str, int] = {}
    kept_words: list = []  # (text, words)
    for text, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        words = _words(text)
        for other, other_words in kept_words:
            union = len(words | other_words)
            if union and len(words & other_words) / union >= DUPLICATE_JACCARD:
                kept[other] += n
                break
        else:
            kept[text] = n
            kept_words.append((text, words))
    return kept


def accept_fix(original: str, fixed: str) -> Optional[str]:
    """The corrected question, or None when the model rewrote it instead of fixing it."""
    fixed = (fixed or "").strip()
    if not fixed:
        return None
    ratio = difflib.SequenceMatcher(None, original.lower(), fixed.lower()).ratio()
    return fixed if ratio >= 1 - MAX_FIX_CHANGE else None
