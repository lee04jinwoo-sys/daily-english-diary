"""Second error detector: GECToR (gotutiyan/gector-roberta-base-5k) on a local server (../gec/server.py).

The main detector (an LLM) misses some plain errors; a 2026-11-24 blind check on 8 essays found that about
half of GECToR's edits outside the main detector's candidates were real errors, but 8% were harmful. So its
edits are never applied directly: they become extra candidates and the verifier decides them.
If the server is not running, the review goes on without it.
"""
import difflib
import logging
import re
from typing import List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_PUNCT = re.compile(r"[^\w\s]")


async def correct(sentences: List[str]) -> Optional[List[str]]:
    """Corrected sentences in the same order, or None when the server is off, slow or answers badly."""
    if not settings.GEC_ENABLED or not sentences:
        return None
    try:
        async with httpx.AsyncClient(timeout=settings.GEC_TIMEOUT, trust_env=False) as client:
            res = await client.post(f"{settings.GEC_URL}/correct", json={"sentences": sentences})
            res.raise_for_status()
            out = res.json().get("corrected")
    except Exception as e:
        logger.info(f"GECToR server not used: {e}")
        return None
    if not isinstance(out, list) or len(out) != len(sentences) or not all(isinstance(s, str) for s in out):
        logger.warning("GECToR server answer did not match the sentences; ignored")
        return None
    return out


def _detok(text: str) -> str:
    """GECToR writes inserted punctuation as separate tokens ('In particular , the')."""
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r"\s+('s|n't|'re|'ve|'ll|'d|'m)\b", r"\1", text)


def _broken(text: str) -> bool:
    """Output GECToR sometimes produces that is never a correction."""
    return bool(re.search(r"\b(\w+)(\s+\1\b){2,}", text, re.I) or re.search(r"([a-z])\1{3,}", text, re.I))


def edits_to_candidates(content: str, spans: List[tuple], corrected: List[str]) -> List[dict]:
    """Word-level edits per sentence as candidates with absolute offsets.

    An insertion or deletion takes in the word after it (or before it, at a sentence end), so the
    original phrase is never empty. Punctuation-only edits and broken output are left out.
    """
    out: List[dict] = []
    for n, ((a, b), fixed) in enumerate(zip(spans, corrected), start=1):
        sentence = content[a:b]
        ow = [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", sentence)]
        pw = fixed.split()
        if not ow or _broken(fixed):          # a confused sentence: none of its edits are trusted
            continue
        sm = difflib.SequenceMatcher(None, [w for w, _, _ in ow], pw, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            lo, hi = i1, i2
            if i1 == i2 or j1 == j2:          # insertion or deletion: take in the next word (an article
                if hi < len(ow):              # belongs to its noun), or the previous one at a sentence end
                    hi += 1
                elif lo > 0:
                    lo -= 1
                else:
                    continue
            new_words = [w for w, _, _ in ow[lo:i1]] + pw[j1:j2] + [w for w, _, _ in ow[i2:hi]]
            start, end = ow[lo][1], ow[hi - 1][2]
            original = sentence[start:end]
            suggested = _detok(" ".join(new_words))
            if not suggested or suggested == original:
                continue
            if _PUNCT.sub("", original).split() == _PUNCT.sub("", suggested).split():
                continue                      # only punctuation changed
            out.append({"sentence": n, "original_phrase": original, "suggested_phrase": suggested,
                        "start_idx": a + start, "end_idx": a + end, "category": "Grammar",
                        "subcategory": "기타 문법", "tier": "accuracy", "explanation": ""})
    return out
