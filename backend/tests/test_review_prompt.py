"""Review output focused on language production: recurring patterns, no contraction nitpicks."""
import inspect
import json

import pytest

from app.schemas.review import ReviewResponse
from app.services.gemini_service import gemini_service, is_contraction_only
from tests.fakes import Router, accept_all
from tests.test_essays import FAKE_REVIEW


def test_contraction_only_detection():
    assert is_contraction_only("the public doesn't have", "the public does not have")
    assert is_contraction_only("it's worth noting", "it is worth noting")
    assert is_contraction_only("I can't go", "I cannot go")
    assert is_contraction_only("They won't", "They will not")
    assert not is_contraction_only("Many people works", "Many people work")
    assert not is_contraction_only("doesn't have private life", "does not have a private life")


PATTERN = {
    "pattern": "privacy를 '사생활 내용'의 뜻으로 사용",
    "ids": ["c1", "c2"],
    "fix": "their private lives / personal information",
    "tip": "privacy는 '사생활을 지킬 권리·상태'. 내용은 private life.",
}


@pytest.mark.anyio
async def test_recurring_patterns_and_contractions(client, monkeypatch):
    content = "The public doesn't have the right to know their privacy. No one should reveal their privacy."
    router = Router(
        detect={"suggestions": [
            {"sentence": 1, "original_phrase": "doesn't have", "suggested_phrase": "does not have",
             "tier": "accuracy", "category": "Grammar", "subcategory": "격식", "explanation": "축약형"},
            {"sentence": 1, "original_phrase": "know their privacy", "suggested_phrase": "know about their private lives",
             "tier": "idiom", "category": "Vocabulary", "subcategory": "어휘", "explanation": "privacy"},
            {"sentence": 2, "original_phrase": "reveal their privacy", "suggested_phrase": "reveal their private lives",
             "tier": "idiom", "category": "Vocabulary", "subcategory": "어휘", "explanation": "privacy"},
        ]},
        verify=accept_all(2, [PATTERN]),
    )
    monkeypatch.setattr(gemini_service, "_client", router)
    e = (await client.post("/api/essays", json={"prompt": "Privacy?", "essay_type": "free"})).json()
    body = (await client.post("/api/review", json={"essay_id": e["id"], "content": content})).json()

    # The contraction expansion never reaches the verifier.
    assert "doesn't have" not in router.prompts["verify"].split("[교정 후보]")[1]
    assert [s["original_phrase"] for s in body["suggestions"]] == ["know their privacy", "reveal their privacy"]
    assert body["recurring_patterns"][0]["count"] == 2
    assert body["recurring_patterns"][0]["examples"] == ["know their privacy", "reveal their privacy"]
    saved = (await client.get(f"/api/essays/{e['id']}")).json()
    assert saved["review"]["recurring_patterns"][0]["fix"].startswith("their private lives")


@pytest.mark.anyio
async def test_malformed_patterns_are_skipped(client, monkeypatch):
    content = "I met teacher. I saw doctor."
    router = Router(
        detect={"suggestions": [
            {"sentence": 1, "original_phrase": "met teacher", "suggested_phrase": "met a teacher", "tier": "accuracy"},
            {"sentence": 2, "original_phrase": "saw doctor", "suggested_phrase": "saw a doctor", "tier": "accuracy"},
        ]},
        verify=accept_all(2, [
            "not a dict",
            {"pattern": "", "ids": ["c1", "c2"]},
            {"pattern": "한 개짜리", "ids": "c1"},
            {"pattern": "관사 누락", "ids": ["c1", "c2", "c2"], "fix": "a/the", "tip": ""},
        ]),
    )
    monkeypatch.setattr(gemini_service, "_client", router)
    e = (await client.post("/api/essays", json={"prompt": "Jobs?", "essay_type": "free"})).json()
    body = (await client.post("/api/review", json={"essay_id": e["id"], "content": content})).json()
    assert body["recurring_patterns"] == [
        {"pattern": "관사 누락", "count": 2, "examples": ["met teacher", "saw doctor"], "fix": "a/the", "tip": ""}
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
    from app.services import review_prompts
    assert "형식" in review_prompts.LEARNER and "감점하지" in review_prompts.LEARNER
    for build in ("build_main_prompt", "build_detect_prompt", "build_verify_prompt"):
        assert "LEARNER" in inspect.getsource(getattr(review_prompts, build)) or build == "build_verify_prompt"
    assert "patterns" in inspect.getsource(review_prompts.build_verify_prompt)


@pytest.mark.anyio
async def test_no_op_suggestions_are_dropped(client, monkeypatch):
    content = "Some people became famous because their post went viral."
    router = Router(detect={"suggestions": [
        {"original_phrase": "their post went viral", "suggested_phrase": "their post went viral",
         "tier": "accuracy", "category": "Grammar", "subcategory": "x", "explanation": "x"},
        {"original_phrase": "became famous", "suggested_phrase": " became famous ",
         "tier": "style", "category": "Clarity", "subcategory": "x", "explanation": "x"},
    ]})
    monkeypatch.setattr(gemini_service, "_client", router)
    e = (await client.post("/api/essays", json={"prompt": "Fame?", "essay_type": "free"})).json()
    body = (await client.post("/api/review", json={"essay_id": e["id"], "content": content})).json()
    assert body["suggestions"] == []
