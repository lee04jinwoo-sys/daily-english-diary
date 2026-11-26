"""Grammar-first numbers of a review, counted from its verified corrections (no model call).

Replaced the band scores on 2026-11-26: bands from the CLI moved between runs of the same essay,
and the learner's goal is grammar accuracy, not an IELTS estimate.
"""
from typing import Iterable

from app.schemas.review import GrammarMetrics
from app.services.text_utils import split_sentences

AWKWARD_TIERS = ("idiom", "style")


def _field(s, name):
    return s.get(name) if isinstance(s, dict) else getattr(s, name, None)


def grammar_metrics(text: str, suggestions: Iterable) -> GrammarMetrics:
    """Accuracy errors per 100 words, share of sentences without one, and awkward expressions."""
    words = len(text.split()) if text and text.strip() else 0
    spans = split_sentences(text) if words else []
    accuracy = [s for s in suggestions if _field(s, "tier") == "accuracy"]
    awkward = sum(1 for s in suggestions if _field(s, "tier") in AWKWARD_TIERS)
    starts = [_field(s, "start_idx") for s in accuracy]
    unclean = sum(1 for a, b in spans if any(isinstance(x, int) and a <= x < b for x in starts))
    clean = len(spans) - unclean
    return GrammarMetrics(
        words=words,
        sentences=len(spans),
        accuracy_errors=len(accuracy),
        errors_per_100=round(100 * len(accuracy) / words, 1) if words else 0.0,
        clean_sentences=clean,
        clean_sentence_pct=round(100 * clean / len(spans)) if spans else 0,
        awkward=awkward,
    )
