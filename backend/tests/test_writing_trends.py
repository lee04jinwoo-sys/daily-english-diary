"""Stats: writing speed (WPM) next to accuracy, per reviewed essay.

- Only reviewed essays with a recorded writing time (>= 1 minute) are included.
- wpm = words / active writing minutes; densities are corrections per 100 words
  (error_density: all tiers, accuracy_density: must-fix only).
- Each essay is compared with the mean of the previous up to 3 non-revision essays:
  speed changes within 10% and accuracy-density changes within 15% count as noise.
  improving: faster (or same speed) without more errors, or same speed with fewer errors
  rushed:    faster with more errors          careful: slower with fewer errors
  declining: more errors without being faster slower: slower, errors about the same
  steady:    nothing moved beyond the noise band
- Revisions (same topic rewritten) are shown but never used as a baseline.
"""
import pytest

from app.services.gemini_service import gemini_service
from app.services.stats_service import writing_signal
from tests.fakes import Router, accept_all


def test_writing_signal_rules():
    base = (10.0, 5.0)  # wpm, accuracy errors per 100 words
    assert writing_signal(None, None, 12.0, 5.0) is None          # no baseline yet
    assert writing_signal(*base, 12.0, 5.0) == "improving"        # faster, same accuracy
    assert writing_signal(*base, 12.0, 3.0) == "improving"        # faster and more accurate
    assert writing_signal(*base, 10.0, 3.0) == "improving"        # same speed, more accurate
    assert writing_signal(*base, 12.0, 7.0) == "rushed"           # faster, more errors
    assert writing_signal(*base, 8.0, 3.0) == "careful"           # slower, fewer errors
    assert writing_signal(*base, 8.0, 7.0) == "declining"         # slower, more errors
    assert writing_signal(*base, 10.0, 7.0) == "declining"        # same speed, more errors
    assert writing_signal(*base, 8.0, 5.0) == "slower"            # slower, same accuracy
    assert writing_signal(*base, 10.5, 5.5) == "steady"           # within the noise band
    assert writing_signal(10.0, 0.0, 10.0, 0.4) == "steady"       # tiny absolute change on a zero baseline


def essay_text(n_sentences):
    return " ".join(f"Line {i} has teh error." for i in range(n_sentences))  # 5 words each


async def write_and_review(client, monkeypatch, n_sentences, minutes, n_errors, revision_of=None):
    if revision_of:
        e = (await client.post(f"/api/essays/{revision_of}/revise")).json()
    else:
        e = (await client.post("/api/essays", json={"prompt": "Topic?", "essay_type": "free"})).json()
    content = essay_text(n_sentences)
    await client.patch(f"/api/essays/{e['id']}", json={"content": content, "writing_seconds": int(minutes * 60)})
    cands = [{"sentence": i + 1, "original_phrase": "has teh error", "suggested_phrase": "has the error",
              "tier": "accuracy", "category": "Spelling", "subcategory": "철자", "explanation": "x"}
             for i in range(n_errors)]
    monkeypatch.setattr(gemini_service, "_client", Router(detect={"suggestions": cands}, verify=accept_all(n_errors)))
    res = await client.post("/api/review", json={"essay_id": e["id"], "content": content})
    assert res.status_code == 200, res.text
    return e["id"]


@pytest.mark.anyio
async def test_trend_items_and_signals(client, monkeypatch):
    a = await write_and_review(client, monkeypatch, 20, 20, 10)   # 100 words, 5 wpm, 10/100
    await write_and_review(client, monkeypatch, 20, 10, 5)        # 10 wpm, 5/100   -> improving
    await write_and_review(client, monkeypatch, 20, 5, 15)        # 20 wpm, 15/100  -> rushed
    await write_and_review(client, monkeypatch, 20, 25, 2)        # 4 wpm,  2/100   -> careful
    rev = await write_and_review(client, monkeypatch, 20, 4, 1, revision_of=a)  # revision: shown, not a baseline

    # Not included: no writing time, or not reviewed.
    await write_and_review(client, monkeypatch, 20, 0, 1)
    e = (await client.post("/api/essays", json={"prompt": "Unreviewed", "essay_type": "free"})).json()
    await client.patch(f"/api/essays/{e['id']}", json={"content": essay_text(20), "writing_seconds": 600})

    t = (await client.get("/api/stats")).json()["writing_trends"]
    assert len(t) == 5
    assert [round(x["wpm"], 1) for x in t] == [5.0, 10.0, 20.0, 4.0, 25.0]
    assert [x["accuracy_density"] for x in t] == [10.0, 5.0, 15.0, 2.0, 1.0]
    assert t[0]["error_density"] == 10.0 and t[0]["word_count"] == 100 and t[0]["minutes"] == 20.0
    assert [x["signal"] for x in t[:4]] == [None, "improving", "rushed", "careful"]
    assert t[4]["essay_id"] == rev and t[4]["is_revision"] is True
    # The revision is compared with the last 3 originals (10, 20, 4 wpm; 5, 15, 2 per 100) but not used later.
    assert t[4]["signal"] == "improving"
