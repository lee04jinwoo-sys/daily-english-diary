"""POST /api/review/stream: each part of the review is sent as soon as it is ready (NDJSON).

Events: feedback and corrections (in completion order; corrections carries the grammar numbers), then done
with the full review after it has been saved. On failure an error event is sent and nothing is saved.
"""
import json

import pytest

from app.services.gemini_service import gemini_service
from tests.fakes import Router, accept_all

CONTENT = "Many people works long hours. I use social media and internet daily."


def cand(sentence, orig, sugg):
    return {"sentence": sentence, "original_phrase": orig, "suggested_phrase": sugg, "tier": "accuracy",
            "category": "Grammar", "subcategory": "수일치(Agreement)", "explanation": "x"}


async def stream(client, monkeypatch, router):
    monkeypatch.setattr(gemini_service, "_client", router)
    e = (await client.post("/api/essays", json={"prompt": "Work?", "essay_type": "free"})).json()
    await client.patch(f"/api/essays/{e['id']}", json={"content": CONTENT})
    res = await client.post("/api/review/stream", json={"essay_id": e["id"], "content": CONTENT})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/x-ndjson")
    return e["id"], [json.loads(line) for line in res.text.splitlines() if line.strip()]


@pytest.mark.anyio
async def test_all_parts_arrive_then_done_with_saved_review(client, monkeypatch):
    router = Router(detect={"suggestions": [cand(1, "Many people works", "Many people work")]}, verify=accept_all(1))
    essay_id, events = await stream(client, monkeypatch, router)
    names = [e["event"] for e in events]
    assert sorted(names[:-1]) == ["corrections", "feedback"]
    assert names[-1] == "done"

    by = {e["event"]: e["data"] for e in events}
    assert by["corrections"]["metrics"]["accuracy_errors"] == 1
    assert [s["original_phrase"] for s in by["corrections"]["suggestions"]] == ["Many people works"]
    assert by["corrections"]["corrected_text"].startswith("Many people work long hours.")
    assert by["feedback"]["upgraded_text"]

    done = by["done"]
    assert done["rubric"] is None and done["metrics"]["accuracy_errors"] == 1
    saved = (await client.get(f"/api/essays/{essay_id}")).json()
    assert saved["review"]["suggestions"][0]["original_phrase"] == "Many people works"
    assert saved["overall_band"] is None


@pytest.mark.anyio
async def test_failure_sends_error_and_saves_nothing(client, monkeypatch):
    router = Router(detect=["boom", "boom", "boom"])  # every error run fails
    essay_id, events = await stream(client, monkeypatch, router)
    assert events[-1]["event"] == "error"
    assert "done" not in [e["event"] for e in events]
    saved = (await client.get(f"/api/essays/{essay_id}")).json()
    assert saved["review"] is None


@pytest.mark.anyio
async def test_unknown_essay_is_404(client):
    res = await client.post("/api/review/stream", json={"essay_id": "nope", "content": CONTENT})
    assert res.status_code == 404
