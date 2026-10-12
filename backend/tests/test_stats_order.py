"""Stats trends follow the order essays were written, not calendar dates.

- Every essay with text gets a number (1, 2, 3 ...) in creation order; the same number is used
  in essay_trends, band_trends and writing_trends.
- Two essays written on the same day are two points, not one merged day.
- Averages are over essays.
"""
import pytest

from app.services.gemini_service import gemini_service
from tests.fakes import Router, accept_all


def text(n):
    return " ".join(f"Line {i} has teh error." for i in range(n))  # 5 words per sentence


async def essay(client, monkeypatch, n_sentences, n_errors=0, review=True, minutes=10):
    e = (await client.post("/api/essays", json={"prompt": "Topic?", "essay_type": "free"})).json()
    if n_sentences:
        await client.patch(f"/api/essays/{e['id']}", json={"content": text(n_sentences), "writing_seconds": minutes * 60})
    if review:
        cands = [{"sentence": i + 1, "original_phrase": "has teh error", "suggested_phrase": "has the error",
                  "tier": "accuracy", "category": "Spelling", "subcategory": "철자", "explanation": "x"}
                 for i in range(n_errors)]
        monkeypatch.setattr(gemini_service, "_client", Router(detect={"suggestions": cands}, verify=accept_all(n_errors)))
        assert (await client.post("/api/review", json={"essay_id": e["id"], "content": text(n_sentences)})).status_code == 200
    return e["id"]


@pytest.mark.anyio
async def test_trends_are_per_essay_and_numbered_in_writing_order(client, monkeypatch):
    a = await essay(client, monkeypatch, 20, n_errors=10)            # 1: 100 words, 10/100
    await essay(client, monkeypatch, 0, review=False)                  # empty draft: no number
    await essay(client, monkeypatch, 20, review=False)                 # 2: written, not reviewed
    c = await essay(client, monkeypatch, 40, n_errors=2)               # 3: 200 words, 1/100 (same day as 1)

    s = (await client.get("/api/stats")).json()
    assert "daily_trends" not in s

    t = s["essay_trends"]
    assert [(x["essay_id"], x["number"]) for x in t] == [(a, 1), (c, 3)]
    assert [x["word_count"] for x in t] == [100, 200]
    assert [x["error_density"] for x in t] == [10.0, 1.0]
    assert t[0]["date"] == t[1]["date"]                                 # same day, still two points
    assert [b["number"] for b in s["band_trends"]] == [1, 3]
    assert [w["number"] for w in s["writing_trends"]] == [1, 3]
    assert s["avg_error_density"] == 5.5                                # mean over essays
