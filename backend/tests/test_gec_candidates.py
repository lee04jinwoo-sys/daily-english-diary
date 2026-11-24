"""Second detector (GECToR, local server): its corrections where the main detector found nothing become
extra candidates, and the verifier decides them like any other candidate.

Rules this file pins down:
- An insertion or deletion is anchored to the next word (the previous one at a sentence end), so every candidate has an original phrase.
- Edits that only add or remove punctuation are not candidates (no real errors among them in the 2026-11-24 check).
- Broken output (a word repeated three times, a letter repeated four times) is not a candidate.
- A GECToR edit overlapping a main-detector candidate is dropped; the main detector's wording wins.
- A candidate without an explanation gets the verifier's reason as its explanation.
- If the GECToR server is down, the review is the same as without it.
"""
import pytest

from app.services import gec_client
from app.services.gec_client import edits_to_candidates
from app.services.gemini_service import gemini_service
from tests.fakes import Router

CONTENT = "It is a hot topic on the internet. I use social media and internet daily. My life is busy."


def spans_of(content):
    from app.services.text_utils import split_sentences  # same splitter the review uses
    return split_sentences(content)


def test_insertion_is_anchored_to_the_next_word():
    spans = spans_of(CONTENT)
    corrected = [CONTENT[a:b] for a, b in spans]
    corrected[1] = "I use social media and the internet daily."
    [c] = edits_to_candidates(CONTENT, spans, corrected)
    assert (c["original_phrase"], c["suggested_phrase"], c["sentence"]) == ("internet", "the internet", 2)
    assert CONTENT[c["start_idx"]:c["end_idx"]] == "internet"


def test_replacement_and_deletion():
    content = "Most of the people agrees. He go home the yesterday."
    spans = spans_of(content)
    out = edits_to_candidates(content, spans, ["Most of the people agree.", "He goes home yesterday."])
    pairs = [(c["original_phrase"], c["suggested_phrase"]) for c in out]
    assert ("agrees.", "agree.") in pairs
    assert ("go", "goes") in pairs
    assert ("the yesterday.", "yesterday.") in pairs
    for c in out:
        assert content[c["start_idx"]:c["end_idx"]] == c["original_phrase"]


def test_punctuation_only_edits_are_skipped_and_spacing_is_fixed():
    content = "Of course many people agree. Especially, internet is fast."
    spans = spans_of(content)
    out = edits_to_candidates(content, spans, ["Of course , many people agree.", "In particular , the internet is fast."])
    assert [(c["original_phrase"], c["suggested_phrase"]) for c in out] == [("Especially,", "In particular, the")]


@pytest.mark.parametrize("bad", ["reading books to win against against against new tech.", "consider otherssss opinions."])
def test_broken_output_is_skipped(bad):
    content = "reading books to win against new tech." if "against" in bad else "consider others opinions."
    assert edits_to_candidates(content, spans_of(content), [bad]) == []


def test_capitalization_edit_is_kept():
    content = "Moreover, There are many."
    [c] = edits_to_candidates(content, spans_of(content), ["Moreover, there are many."])
    assert c["suggested_phrase"] == "there"


def gec_says(monkeypatch, fixed_sentences):
    seen = {}

    async def fake(sentences):
        seen["sentences"] = sentences
        return [fixed_sentences.get(i, s) for i, s in enumerate(sentences)]

    monkeypatch.setattr(gec_client, "correct", fake)
    return seen


async def review(client, monkeypatch, router, content=CONTENT):
    monkeypatch.setattr(gemini_service, "_client", router)
    e = (await client.post("/api/essays", json={"prompt": "Web?", "essay_type": "free"})).json()
    res = await client.post("/api/review", json={"essay_id": e["id"], "content": content})
    assert res.status_code == 200, res.text
    return res.json()


def cand(sentence, orig, sugg):
    return {"sentence": sentence, "original_phrase": orig, "suggested_phrase": sugg, "tier": "accuracy",
            "category": "Grammar", "subcategory": "관사(Article)", "explanation": "주 탐지 설명"}


@pytest.mark.anyio
async def test_gector_finding_goes_to_the_verifier_and_gets_its_reason(client, monkeypatch):
    gec_says(monkeypatch, {2: "My life is very busy."})        # S3: a change the main detector missed
    router = Router(
        detect={"suggestions": [cand(2, "internet", "the internet")]},
        verify={"verdicts": [{"id": "c1", "valid": True}, {"id": "c2", "valid": True, "reason": "강조 부사 추가"}],
                "patterns": []},
    )
    body = await review(client, monkeypatch, router)
    assert '"busy." → "very busy."' in router.prompts["verify"]
    by_orig = {s["original_phrase"]: s for s in body["suggestions"]}
    assert by_orig["internet"]["explanation"] == "주 탐지 설명"
    assert by_orig["busy."]["suggested_phrase"] == "very busy." and by_orig["busy."]["explanation"] == "강조 부사 추가"


@pytest.mark.anyio
async def test_gector_edit_overlapping_a_main_candidate_is_dropped(client, monkeypatch):
    gec_says(monkeypatch, {1: "I use social media and the internet daily."})
    router = Router(detect={"suggestions": [cand(2, "internet", "the internet")]},
                    verify={"verdicts": [{"id": "c1", "valid": True}], "patterns": []})
    body = await review(client, monkeypatch, router)
    assert [s["original_phrase"] for s in body["suggestions"]] == ["internet"]
    assert "\nc2 |" not in router.prompts["verify"]


@pytest.mark.anyio
async def test_rejected_gector_finding_is_not_shown(client, monkeypatch):
    gec_says(monkeypatch, {2: "My life are busy."})
    router = Router(verify={"verdicts": [{"id": "c1", "valid": False}], "patterns": []})
    body = await review(client, monkeypatch, router)
    assert body["suggestions"] == []


@pytest.mark.anyio
async def test_review_without_gector_server_is_unchanged(client, monkeypatch):
    router = Router(detect={"suggestions": [cand(2, "internet", "the internet")]},
                    verify={"verdicts": [{"id": "c1", "valid": True}], "patterns": []})
    body = await review(client, monkeypatch, router)       # conftest: server unavailable
    assert [s["original_phrase"] for s in body["suggestions"]] == ["internet"]
