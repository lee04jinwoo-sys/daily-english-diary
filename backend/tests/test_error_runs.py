"""The error step (detect -> verify) runs three times and the review uses one whole run: the one whose
accuracy-error count is the median. The CLI cannot fix the temperature, so a single run moves the count
from one review to the next; picking a whole run keeps the shown corrections and the score consistent.

Rules this file pins down:
- detect and verify each run three times.
- The run with the median accuracy count is shown, as it is (not a mix of runs).
- Style notes do not count toward the median.
- A failed run is skipped; with two left, the one with fewer accuracy errors is used.
- A verified run is preferred over one whose verifier answer was unusable.
- If every run fails, the review fails.
"""
import pytest

from app.services.gemini_service import gemini_service
from tests.fakes import Router, accept_all

CONTENT = "I like dog. She go to school. They has a car. It is good."


def cand(sentence, orig, sugg, tier="accuracy"):
    return {"sentence": sentence, "original_phrase": orig, "suggested_phrase": sugg, "tier": tier,
            "category": "Grammar", "subcategory": "x", "explanation": "x"}


ONE = {"suggestions": [cand(1, "dog", "dogs")]}
TWO = {"suggestions": [cand(1, "dog", "dogs"), cand(2, "go", "goes")]}
THREE = {"suggestions": [cand(1, "dog", "dogs"), cand(2, "go", "goes"), cand(3, "has", "have")]}


async def review(client, monkeypatch, router):
    monkeypatch.setattr(gemini_service, "_client", router)
    r = await client.post("/api/essays", json={"prompt": "Pets?", "essay_type": "free"})
    assert r.status_code < 300, r.text
    e = r.json()
    return await client.post("/api/review", json={"essay_id": e["id"], "content": CONTENT})


def phrases(body):
    return sorted(s["original_phrase"] for s in body["suggestions"])


@pytest.mark.anyio
async def test_detect_and_verify_each_run_three_times(client, monkeypatch):
    router = Router(detect=[ONE, ONE, ONE], verify=[accept_all(3)] * 3)
    res = await review(client, monkeypatch, router)
    assert res.status_code == 200, res.text
    assert router.count("detect") == 3
    assert router.count("verify") == 3


@pytest.mark.anyio
async def test_the_median_run_is_shown_whole(client, monkeypatch):
    router = Router(detect=[ONE, THREE, TWO], verify=[accept_all(3)] * 3)
    body = (await review(client, monkeypatch, router)).json()
    assert phrases(body) == ["dog", "go"]
    assert body["corrected_text"] == "I like dogs. She goes to school. They has a car. It is good."


@pytest.mark.anyio
async def test_style_notes_do_not_count_toward_the_median(client, monkeypatch):
    # Run 1: one accuracy error plus two style notes; runs 2-3: two and three accuracy errors.
    styled = {"suggestions": [cand(1, "dog", "dogs"), cand(2, "go", "head", tier="style"),
                              cand(4, "good", "great", tier="style")]}
    router = Router(detect=[styled, TWO, THREE], verify=[accept_all(3)] * 3)
    body = (await review(client, monkeypatch, router)).json()
    assert phrases(body) == ["dog", "go"]


@pytest.mark.anyio
async def test_a_failed_run_is_skipped_and_the_lower_of_two_is_used(client, monkeypatch):
    router = Router(detect=[THREE, "boom", ONE], verify=[accept_all(3)] * 2)
    body = (await review(client, monkeypatch, router)).json()
    assert phrases(body) == ["dog"]


@pytest.mark.anyio
async def test_a_verified_run_beats_an_unverified_one(client, monkeypatch):
    # Run 2 is unverified, so runs 1 and 3 decide (three and one errors): the lower one is used.
    router = Router(detect=[THREE, TWO, ONE], verify=[accept_all(3), {"x": 1}, accept_all(3)])
    body = (await review(client, monkeypatch, router)).json()
    assert body["suggestions_verified"] is True
    assert phrases(body) == ["dog"]


@pytest.mark.anyio
async def test_every_run_failing_fails_the_review(client, monkeypatch):
    router = Router(detect=["boom", "boom", "boom"])
    res = await review(client, monkeypatch, router)
    assert res.status_code >= 500
