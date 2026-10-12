"""Lean review: less output, code-derived fields, sentence pairs generated on demand."""
import json

import pytest

from app.services.gemini_service import gemini_service
from tests.fakes import Router, accept_all
from tests.test_essays import FAKE_REVIEW

CONTENT = "Many people works long hours. I use social media and internet every day."


def review_payload(**over):
    p = dict(FAKE_REVIEW)
    p.update(
        suggestions=[
            {"original_phrase": "Many people works", "suggested_phrase": "Many people work", "tier": "accuracy",
             "category": "Grammar", "subcategory": "수일치", "explanation": "x"},
            {"original_phrase": "social media and internet", "suggested_phrase": "social media and the internet",
             "tier": "accuracy", "category": "Grammar", "subcategory": "관사", "explanation": "x"},
            {"original_phrase": "every day", "suggested_phrase": "daily", "tier": "style",
             "category": "Clarity", "subcategory": "문체", "explanation": "x"},
            {"original_phrase": "hallucinated phrase", "suggested_phrase": "x", "tier": "accuracy",
             "category": "Grammar", "subcategory": "x", "explanation": "not in text"},
        ],
        recurring_patterns=[
            {"pattern": "관사 누락", "count": 2, "examples": ["social media and internet", "not in the essay"],
             "fix": "the internet", "tip": "t"},
            {"pattern": "가짜 패턴", "count": 2, "examples": ["nowhere", "also nowhere"], "fix": "x", "tip": "t"},
        ],
        sentence_pairs=[{"original": "should be ignored", "native": "x", "translation": "x", "explanation": "x"}],
        key_expressions=[{"expression": "work long hours", "meaning": "장시간 일하다", "pos": "idiom"}],
    )
    p.pop("corrected_text", None)
    p.update(over)
    return p


def router_for(payload, pairs=None, patterns=None):
    """Main call gets the payload without errors; the detector gets its suggestions; the verifier accepts all."""
    main = {k: v for k, v in payload.items() if k not in ("suggestions", "recurring_patterns")}
    return Router(main=main, detect={"suggestions": payload.get("suggestions", [])},
                  verify=accept_all(len(payload.get("suggestions", [])), patterns), pairs=pairs)


async def _reviewed_essay(client, monkeypatch, *pair_payloads):
    rec = router_for(review_payload(), pairs=list(pair_payloads) or None,
                     patterns=[{"pattern": "관사 누락", "ids": ["c2", "c9"], "fix": "the internet", "tip": "t"}])
    monkeypatch.setattr(gemini_service, "_client", rec)
    e = (await client.post("/api/essays", json={"prompt": "Work?", "essay_type": "free"})).json()
    await client.patch(f"/api/essays/{e['id']}", json={"content": CONTENT})
    body = (await client.post("/api/review", json={"essay_id": e["id"], "content": CONTENT})).json()
    return e["id"], body, rec


@pytest.mark.anyio
async def test_unlocatable_suggestions_and_examples_are_dropped(client, monkeypatch):
    _, body, _ = await _reviewed_essay(client, monkeypatch)
    assert "hallucinated phrase" not in [s["original_phrase"] for s in body["suggestions"]]
    # A pattern needs two verified corrections behind it; c9 does not exist, so nothing is left.
    assert body["recurring_patterns"] == []


@pytest.mark.anyio
async def test_corrected_text_is_built_from_accuracy_and_idiom_fixes(client, monkeypatch):
    _, body, _ = await _reviewed_essay(client, monkeypatch)
    assert body["corrected_text"] == "Many people work long hours. I use social media and the internet every day."


@pytest.mark.anyio
async def test_main_review_does_not_produce_sentence_pairs(client, monkeypatch):
    _, body, rec = await _reviewed_essay(client, monkeypatch)
    assert body["sentence_pairs"] == []
    prompt = rec.prompts["main"]
    assert "sentence_pairs" not in prompt
    assert "corrected_text" not in prompt


@pytest.mark.anyio
async def test_review_call_is_deterministic_and_essay_comes_last(client, monkeypatch):
    _, _, rec = await _reviewed_essay(client, monkeypatch)
    configs = {role: k["config"] for role, k in rec.calls}
    assert {role: c.temperature for role, c in configs.items()} == {"main": 0, "detect": 0, "verify": 0, "score": 0.7}
    assert configs["main"].thinking_config.thinking_budget == 2048
    assert configs["detect"].thinking_config.thinking_budget == 2048
    # Static instructions first so the prefix can be cached; the essay is at the very end.
    main = rec.prompts["main"]
    assert main.rindex(CONTENT) > main.index("[JSON 응답 규격]")
    detect = rec.prompts["detect"]
    assert detect.rindex("[S2]") > detect.index("[JSON 응답 규격]")


@pytest.mark.anyio
async def test_key_expressions_without_example_are_accepted(client, monkeypatch):
    _, body, _ = await _reviewed_essay(client, monkeypatch)
    assert body["key_expressions"][0]["expression"] == "work long hours"
    assert body["key_expressions"][0]["example"] == ""


PAIRS = {"pairs": [
    {"index": 1, "native": "Many people work long hours.", "translation": "많은 사람이 오래 일한다.",
     "explanation": "수일치", "vocab": [{"word": "long hours", "meaning": "장시간", "pos": "n"}]},
    {"index": 2, "native": "I use social media and the internet daily.", "translation": "매일 쓴다.",
     "explanation": "관사", "vocab": []},
]}


@pytest.mark.anyio
async def test_sentence_pairs_generated_on_demand_and_cached(client, monkeypatch):
    essay_id, _, rec = await _reviewed_essay(client, monkeypatch, PAIRS)
    r1 = await client.post(f"/api/essays/{essay_id}/sentence-pairs")
    assert r1.status_code == 200
    pairs = r1.json()
    assert [p["original"] for p in pairs] == ["Many people works long hours.",
                                              "I use social media and internet every day."]
    assert [p["corrected"] for p in pairs] == ["Many people work long hours.",
                                               "I use social media and the internet every day."]
    assert pairs[0]["native"] == "Many people work long hours."
    assert pairs[1]["translation"] == "매일 쓴다."

    r2 = await client.post(f"/api/essays/{essay_id}/sentence-pairs")
    assert r2.json() == pairs
    assert rec.count("pairs") == 1  # the second request is served from storage
    saved = (await client.get(f"/api/essays/{essay_id}")).json()
    assert len(saved["review"]["sentence_pairs"]) == 2


@pytest.mark.anyio
async def test_sentence_pairs_need_a_review(client):
    e = (await client.post("/api/essays", json={"prompt": "Work?", "essay_type": "free"})).json()
    assert (await client.post(f"/api/essays/{e['id']}/sentence-pairs")).status_code == 409


@pytest.mark.anyio
async def test_ambiguous_phrases_are_dropped(client, monkeypatch):
    # "internet" appears twice; the first one is already correct ("the internet").
    content = "It is a hot topic on the internet. I use social media and internet daily."
    payload = review_payload(suggestions=[
        {"original_phrase": "internet", "suggested_phrase": "the Internet", "tier": "accuracy",
         "category": "Grammar", "subcategory": "관사", "explanation": "x"},
        {"original_phrase": "social media and internet", "suggested_phrase": "social media and the internet",
         "tier": "accuracy", "category": "Grammar", "subcategory": "관사", "explanation": "x"},
    ], recurring_patterns=[])
    monkeypatch.setattr(gemini_service, "_client", router_for(payload))
    e = (await client.post("/api/essays", json={"prompt": "Web?", "essay_type": "free"})).json()
    body = (await client.post("/api/review", json={"essay_id": e["id"], "content": content})).json()
    assert [s["original_phrase"] for s in body["suggestions"]] == ["social media and internet"]
    assert body["corrected_text"] == "It is a hot topic on the internet. I use social media and the internet daily."


def test_prompt_asks_for_unique_phrases_and_specific_patterns():
    import inspect
    from app.services import review_prompts
    assert "한 번만" in inspect.getsource(review_prompts.build_detect_prompt)
    assert "구체적" in inspect.getsource(review_prompts.build_verify_prompt)


@pytest.mark.anyio
async def test_concurrent_sentence_pair_requests_generate_once(client, monkeypatch):
    import asyncio
    essay_id, _, rec = await _reviewed_essay(client, monkeypatch, PAIRS, PAIRS)
    r1, r2 = await asyncio.gather(
        client.post(f"/api/essays/{essay_id}/sentence-pairs"),
        client.post(f"/api/essays/{essay_id}/sentence-pairs"),
    )
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()
    assert rec.count("pairs") == 1  # exactly one pairs generation


class _RawRecorder:
    """Fake client returning raw response texts in order."""

    def __init__(self, *texts):
        self.texts = list(texts)
        self.calls = 0
        rec = self

        class Models:
            async def generate_content(self, *a, **k):
                rec.calls += 1
                text = rec.texts.pop(0)

                class R:
                    pass
                R.text = text
                return R()

        class Aio:
            models = Models()
        self.aio = Aio()


@pytest.mark.anyio
async def test_malformed_json_is_retried_once(monkeypatch):
    rec = _RawRecorder('{"pairs": [ {"index": 1, "native": "x" "broken"', json.dumps({"ok": 1}))
    monkeypatch.setattr(gemini_service, "_client", rec)
    assert await gemini_service._generate_json("p", 0.2) == {"ok": 1}
    assert rec.calls == 2


@pytest.mark.anyio
async def test_malformed_json_twice_raises(monkeypatch):
    rec = _RawRecorder("{bad", "{still bad")
    monkeypatch.setattr(gemini_service, "_client", rec)
    with pytest.raises(json.JSONDecodeError):
        await gemini_service._generate_json("p", 0.2)
    assert rec.calls == 2
