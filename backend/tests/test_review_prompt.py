"""Review output focused on language production: recurring patterns, no contraction nitpicks."""
import json

import pytest

from app.schemas.review import ReviewResponse
from app.services.gemini_service import gemini_service, is_contraction_only
from tests.test_essays import FAKE_REVIEW, _FakeClient


def test_contraction_only_detection():
    assert is_contraction_only("the public doesn't have", "the public does not have")
    assert is_contraction_only("it's worth noting", "it is worth noting")
    assert is_contraction_only("I can't go", "I cannot go")
    assert is_contraction_only("They won't", "They will not")
    assert not is_contraction_only("Many people works", "Many people work")
    assert not is_contraction_only("doesn't have private life", "does not have a private life")


PATTERNS = [{
    "pattern": "privacy를 '사생활 내용'의 뜻으로 사용",
    "count": 4,
    "examples": ["know their privacy", "reveal their privacy"],
    "fix": "their private lives / personal information",
    "tip": "privacy는 '사생활을 지킬 권리·상태'. 내용은 private life.",
}]


@pytest.mark.anyio
async def test_recurring_patterns_and_contractions(client, monkeypatch):
    content = "The public doesn't have the right to know their privacy. No one should reveal their privacy."
    payload = dict(FAKE_REVIEW, recurring_patterns=PATTERNS, suggestions=[
        {"original_phrase": "doesn't have", "suggested_phrase": "does not have",
         "tier": "accuracy", "category": "Grammar", "subcategory": "격식", "explanation": "축약형"},
        {"original_phrase": "know their privacy", "suggested_phrase": "know about their private lives",
         "tier": "idiom", "category": "Vocabulary", "subcategory": "어휘", "explanation": "privacy"},
    ])
    monkeypatch.setattr(gemini_service, "_client", _FakeClient(payload))
    e = (await client.post("/api/essays", json={"prompt": "Privacy?", "essay_type": "free"})).json()
    body = (await client.post("/api/review", json={"essay_id": e["id"], "content": content})).json()

    assert [s["original_phrase"] for s in body["suggestions"]] == ["know their privacy"]
    assert body["recurring_patterns"][0]["count"] == 4
    assert body["recurring_patterns"][0]["examples"] == ["know their privacy", "reveal their privacy"]
    saved = (await client.get(f"/api/essays/{e['id']}")).json()
    assert saved["review"]["recurring_patterns"][0]["fix"].startswith("their private lives")


@pytest.mark.anyio
async def test_malformed_patterns_are_skipped(client, monkeypatch):
    payload = dict(FAKE_REVIEW, recurring_patterns=[
        "not a dict",
        {"pattern": "", "count": 2},
        {"pattern": "관사 누락", "count": "3", "examples": "a single string", "fix": "a/the", "tip": ""},
    ])
    monkeypatch.setattr(gemini_service, "_client", _FakeClient(payload))
    e = (await client.post("/api/essays", json={"prompt": "Privacy?", "essay_type": "free"})).json()
    body = (await client.post("/api/review", json={"essay_id": e["id"], "content": "Some essay with a single string."})).json()
    assert body["recurring_patterns"] == [
        {"pattern": "관사 누락", "count": 3, "examples": ["a single string"], "fix": "a/the", "tip": ""}
    ]


def test_old_reviews_without_patterns_still_load():
    old = dict(FAKE_REVIEW)
    old.pop("recurring_patterns", None)
    old.update(essay_id="x", original_text="t", rubric={
        k: {"band": 6.0, "comment": ""} for k in ("task_response", "coherence", "lexical", "grammar")
    } | {"overall_band": 6.0})
    r = ReviewResponse(**json.loads(json.dumps(old)))
    assert r.recurring_patterns == []


def test_prompt_does_not_grade_format():
    import inspect
    src = inspect.getsource(gemini_service.review_essay)
    assert "recurring_patterns" in src
    assert "형식" in src and "감점하지" in src


@pytest.mark.anyio
async def test_no_op_suggestions_are_dropped(client, monkeypatch):
    content = "Some people became famous because their post went viral."
    payload = dict(FAKE_REVIEW, suggestions=[
        {"original_phrase": "their post went viral", "suggested_phrase": "their post went viral",
         "tier": "accuracy", "category": "Grammar", "subcategory": "x", "explanation": "x"},
        {"original_phrase": "became famous", "suggested_phrase": " became famous ",
         "tier": "style", "category": "Clarity", "subcategory": "x", "explanation": "x"},
    ])
    monkeypatch.setattr(gemini_service, "_client", _FakeClient(payload))
    e = (await client.post("/api/essays", json={"prompt": "Fame?", "essay_type": "free"})).json()
    body = (await client.post("/api/review", json={"essay_id": e["id"], "content": content})).json()
    assert body["suggestions"] == []
