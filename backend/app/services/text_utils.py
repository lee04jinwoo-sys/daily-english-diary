import re
from typing import Iterable, List, Tuple

from app.schemas.review import SuggestionItem

# One sentence rule for the whole app (frontend utils/sentences.ts splitSentences mirrors it).
# A run of . ! ? (plus closing quotes/brackets) ends a sentence only when whitespace and then a
# non-lowercase character follow, so a question quoted inside a sentence, "3.5", "U.S. last year"
# or a title such as "Mr. Kim" do not cut it into fragments. A newline always ends a sentence.
_CLOSERS = "\"')]\u201d\u2019"
_ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "e.g", "i.e", "cf"}


def _ends_sentence(text: str, first: int, after: int) -> bool:
    """Whether the punctuation run text[first:after] ends a sentence."""
    if after >= len(text):
        return True
    if not text[after].isspace():
        return False
    k = after
    while k < len(text) and text[k].isspace():
        k += 1
    if k >= len(text):
        return True
    if text[k].islower():
        return False
    if text[first] == ".":
        w = first
        while w > 0 and (text[w - 1].isalpha() or text[w - 1] == "."):
            w -= 1
        if text[w:first].lower() in _ABBREVIATIONS:
            return False
    return True


def split_sentences(text: str) -> List[Tuple[int, int]]:
    """Character spans of sentences in text (whitespace trimmed)."""
    spans: List[Tuple[int, int]] = []

    def add(start: int, end: int) -> None:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if end > start:
            spans.append((start, end))

    start = i = 0
    while i < len(text):
        if text[i] == "\n":
            add(start, i)
            start = i = i + 1
        elif text[i] in ".!?":
            j = i
            while j < len(text) and text[j] in ".!?":
                j += 1
            while j < len(text) and text[j] in _CLOSERS:
                j += 1
            if _ends_sentence(text, i, j):
                add(start, j)
                start = j
            i = j
        else:
            i += 1
    add(start, len(text))
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
