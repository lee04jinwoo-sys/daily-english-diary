"""Grammar-first numbers replace the band scores (user decision 2026-11-26).

Rules this file pins down:
- Three numbers, counted from the verified corrections, no model call:
  accuracy errors per 100 words (one decimal), share of sentences without an accuracy error (whole %),
  and awkward expressions (idiom + style notes, reference only).
- A review makes no scoring calls and carries no rubric; the stream sends feedback and corrections only,
  and the corrections event carries the numbers.
- Old reviews stored with a rubric get the numbers too, counted from their stored corrections.
- The essay list and stats use the numbers; band fields are gone from stats.
"""
import json
import sqlite3

import pytest

from app.core.config import settings
from app.services.gemini_service import gemini_service
from app.services.grammar_metrics import grammar_metrics
from tests.fakes import Router, accept_all

# 4 sentences, 20 words.
CONTENT = "I like dog very much. She go to school every day. They has a car. It is good for us."


def sug(phrase, tier="accuracy"):
    start = CONTENT.index(phrase)
    return {"original_phrase": phrase, "tier": tier, "start_idx": start, "end_idx": start + len(phrase)}


def test_the_three_numbers():
    m = grammar_metrics(CONTENT, [sug("dog"), sug("go"), sug("very much", "style"), sug("for us", "idiom")])
    assert m.words == 20
    assert m.sentences == 4
    assert m.accuracy_errors == 2
    assert m.errors_per_100 == 10.0
    assert m.clean_sentences == 2
    assert m.clean_sentence_pct == 50
    assert m.awkward == 2


def test_two_errors_in_one_sentence_make_one_unclean_sentence():
    m = grammar_metrics(CONTENT, [sug("They"), sug("has")])
    assert m.clean_sentences == 3 and m.clean_sentence_pct == 75
    assert m.errors_per_100 == 10.0


def test_empty_text_is_all_zero():
    m = grammar_metrics("", [])
    assert (m.words, m.sentences, m.errors_per_100, m.clean_sentence_pct) == (0, 0, 0.0, 0)


def cand(sentence, orig, sugg, tier="accuracy"):
    return {"sentence": sentence, "original_phrase": orig, "suggested_phrase": sugg, "tier": tier,
            "category": "Grammar", "subcategory": "x", "explanation": "x"}


DETECT = {"suggestions": [cand(1, "dog", "dogs"), cand(2, "go", "goes"), cand(4, "for us", "to us", "idiom")]}


async def new_essay(client):
    e = (await client.post("/api/essays", json={"prompt": "Pets?", "essay_type": "free"})).json()
    await client.patch(f"/api/essays/{e['id']}", json={"content": CONTENT})
    return e


@pytest.mark.anyio
async def test_a_review_has_numbers_and_no_scoring_calls(client, monkeypatch):
    router = Router(detect=[DETECT] * 3, verify=[accept_all(3)] * 3)
    monkeypatch.setattr(gemini_service, "_client", router)
    e = await new_essay(client)
    body = (await client.post("/api/review", json={"essay_id": e["id"], "content": CONTENT})).json()
    assert router.count("score_content") == 0 and router.count("score_language") == 0
    assert body["rubric"] is None
    m = body["metrics"]
    assert (m["accuracy_errors"], m["errors_per_100"], m["clean_sentence_pct"], m["awkward"]) == (2, 10.0, 50, 1)
    saved = (await client.get(f"/api/essays/{e['id']}")).json()
    assert saved["review"]["metrics"] == m


@pytest.mark.anyio
async def test_the_stream_sends_feedback_and_corrections_with_numbers(client, monkeypatch):
    monkeypatch.setattr(gemini_service, "_client", Router(detect=[DETECT] * 3, verify=[accept_all(3)] * 3))
    e = await new_essay(client)
    res = await client.post("/api/review/stream", json={"essay_id": e["id"], "content": CONTENT})
    events = [json.loads(line) for line in res.text.splitlines() if line.strip()]
    names = [ev["event"] for ev in events]
    assert sorted(names[:-1]) == ["corrections", "feedback"] and names[-1] == "done"
    corrections = next(ev["data"] for ev in events if ev["event"] == "corrections")
    assert corrections["metrics"]["errors_per_100"] == 10.0


OLD_REVIEW = {
    "essay_id": "", "original_text": CONTENT, "corrected_text": CONTENT, "upgraded_text": "", "overall_feedback": "f",
    "rubric": {k: {"band": 6.0, "comment": ""} for k in ("task_response", "coherence", "lexical", "grammar")}
    | {"overall_band": 6.0},
    "argument": {}, "suggestions": [
        dict(sug("dog"), id="a", suggested_phrase="dogs", category="Grammar", subcategory="x", explanation="x"),
    ],
}


def store_old_review(essay_id):
    db = sqlite3.connect(settings.DATABASE_PATH)
    db.execute("UPDATE essays SET review_json = ?, overall_band = 6.0 WHERE id = ?",
               (json.dumps(dict(OLD_REVIEW, essay_id=essay_id)), essay_id))
    db.commit()
    db.close()


@pytest.mark.anyio
async def test_an_old_review_gets_numbers_from_its_stored_corrections(client):
    e = await new_essay(client)
    store_old_review(e["id"])
    saved = (await client.get(f"/api/essays/{e['id']}")).json()
    assert saved["review"]["metrics"]["errors_per_100"] == 5.0
    assert saved["review"]["metrics"]["clean_sentence_pct"] == 75


@pytest.mark.anyio
async def test_the_list_shows_numbers(client):
    e = await new_essay(client)
    store_old_review(e["id"])
    other = (await client.post("/api/essays", json={"prompt": "Cars?", "essay_type": "free"})).json()
    items = {i["id"]: i for i in (await client.get("/api/essays")).json()["essays"]}
    assert items[e["id"]]["metrics"]["errors_per_100"] == 5.0
    assert items[other["id"]]["metrics"] is None
    assert "bands" not in items[e["id"]]


@pytest.mark.anyio
async def test_stats_use_numbers_not_bands(client, monkeypatch):
    monkeypatch.setattr(gemini_service, "_client", Router(detect=[DETECT] * 3, verify=[accept_all(3)] * 3))
    e = await new_essay(client)
    await client.post("/api/review", json={"essay_id": e["id"], "content": CONTENT})
    s = (await client.get("/api/stats")).json()
    for gone in ("band_trends", "avg_band", "type_bands"):
        assert gone not in s
    [day] = s["daily_activity"].values()
    assert day["reviewed"] is True and day["best_errors_per_100"] == 10.0
    assert "best_band" not in day
    [t] = s["essay_trends"]
    assert t["clean_sentence_pct"] == 50
    assert s["avg_clean_sentence_pct"] == 50
