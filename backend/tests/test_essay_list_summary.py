"""The sidebar shows more than the prompt: criterion bands and the number of corrections, taken from
the stored review. The list must stay cheap and must never fail because one review is odd."""
import pytest

from tests.test_lean_review import _reviewed_essay


def item_of(listing, essay_id):
    return next(e for e in listing["essays"] if e["id"] == essay_id)


@pytest.mark.anyio
async def test_a_reviewed_essay_lists_its_criterion_bands_and_correction_counts(client, monkeypatch):
    essay_id, body, _ = await _reviewed_essay(client, monkeypatch)
    item = item_of((await client.get("/api/essays")).json(), essay_id)
    rubric = body["rubric"]
    assert item["bands"] == {k: rubric[k]["band"] for k in ("task_response", "coherence", "lexical", "grammar")}
    assert item["correction_count"] == len(body["suggestions"])
    assert item["grammar_count"] == sum(1 for s in body["suggestions"] if s["category"] == "Grammar")
    assert item["correction_count"] > 0 and item["grammar_count"] > 0


@pytest.mark.anyio
async def test_an_unreviewed_essay_has_no_bands_and_zero_counts(client):
    e = (await client.post("/api/essays", json={"prompt": "Work?", "essay_type": "free"})).json()
    item = item_of((await client.get("/api/essays")).json(), e["id"])
    assert item["bands"] is None and item["correction_count"] == 0 and item["grammar_count"] == 0


@pytest.mark.anyio
async def test_a_damaged_review_does_not_break_the_list(client, monkeypatch):
    essay_id, _, _ = await _reviewed_essay(client, monkeypatch)
    other = (await client.post("/api/essays", json={"prompt": "Other?", "essay_type": "free"})).json()
    from app.core.config import settings
    import sqlite3
    db = sqlite3.connect(settings.DATABASE_PATH)
    db.execute("UPDATE essays SET review_json = ? WHERE id = ?", ("{not json", other["id"]))
    db.execute("UPDATE essays SET review_json = ? WHERE id = ?", ('{"rubric": {"grammar": "x"}, "suggestions": 5}', essay_id))
    db.commit(); db.close()
    res = await client.get("/api/essays")
    assert res.status_code == 200
    listing = res.json()
    assert item_of(listing, other["id"])["bands"] is None
    assert item_of(listing, essay_id)["bands"] is None and item_of(listing, essay_id)["correction_count"] == 0
