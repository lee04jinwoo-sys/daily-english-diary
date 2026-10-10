import re
from typing import Iterable, List, Tuple

from app.schemas.review import SuggestionItem

_SENTENCE = re.compile(r"[^.!?\n]+(?:[.!?]+[\"')\]]*|$)")


def split_sentences(text: str) -> List[Tuple[int, int]]:
    """Character spans of sentences in text (whitespace trimmed)."""
    spans = []
    for m in _SENTENCE.finditer(text):
        start, end = m.start(), m.end()
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if end > start:
            spans.append((start, end))
    return spans


def apply_suggestions(text: str, suggestions: Iterable[SuggestionItem], tiers=("accuracy", "idiom"),
                      start: int = 0, end: int | None = None) -> str:
    """Apply located, non-overlapping suggestions of the given tiers inside text[start:end]."""
    end = len(text) if end is None else end
    picked, last_end = [], start
    for s in sorted(suggestions, key=lambda s: s.start_idx):
        if s.tier not in tiers or s.start_idx < last_end or s.end_idx > end:
            continue
        if text[s.start_idx:s.end_idx] != s.original_phrase:
            continue
        picked.append(s)
        last_end = s.end_idx
    out, pos = [], start
    for s in picked:
        out.append(text[pos:s.start_idx])
        out.append(s.suggested_phrase)
        pos = s.end_idx
    out.append(text[pos:end])
    return "".join(out)
