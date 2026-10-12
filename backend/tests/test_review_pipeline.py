"""Review pipeline: find errors by sentence number -> verify each one -> group verified ones into patterns.

Rules this file pins down:
- Errors are located by sentence number, so a phrase that also appears elsewhere is not dropped.
- Only corrections the verifier accepts are shown and applied.
- A recurring pattern is built from verified corrections only; its examples come from those corrections.
- If the verifier response is unusable, candidates are kept and the review says it was not verified.
- Each Gemini call is recorded (label, seconds, tokens).
"""
import json

import pytest

from app.core.config import settings
from app.services.gemini_service import gemini_service
from tests.fakes import MAIN, Router

# "internet" appears in S1 (already correct) and S2 (missing "the").
CONTENT = "It is a hot topic on the internet. I use social media and internet daily. My life is busy."

def detect(*items):
    return {"suggestions": list(items)}


def cand(sentence, orig, sugg, tier="accuracy", sub="관사(Article)"):
    return {"sentence": sentence, "original_phrase": orig, "suggested_phrase": sugg, "tier": tier,
            "category": "Grammar", "subcategory": sub, "explanation": "x"}


async def review(client, monkeypatch, router, content=CONTENT):
    monkeypatch.setattr(gemini_service, "_client", router)
    e = (await client.post("/api/essays", json={"prompt": "Web?", "essay_type": "free"})).json()
    res = await client.post("/api/review", json={"essay_id": e["id"], "content": content})
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.anyio
async def test_phrase_repeated_elsewhere_is_located_by_sentence_number(client, monkeypatch):
    router = Router(
        detect=detect(cand(2, "internet", "the internet")),
        verify={"verdicts": [{"id": "c1", "valid": True}], "patterns": []},
    )
    body = await review(client, monkeypatch, router)
    [s] = body["suggestions"]
    assert s["original_phrase"] == "internet"
    assert CONTENT[s["start_idx"]:s["end_idx"]] == "internet"
    assert s["start_idx"] > CONTENT.index("daily") - 20  # the S2 occurrence, not S1
    assert body["corrected_text"] == (
        "It is a hot topic on the internet. I use social media and the internet daily. My life is busy.")


@pytest.mark.anyio
async def test_detection_prompt_numbers_sentences(client, monkeypatch):
    router = Router()
    await review(client, monkeypatch, router)
    p = router.prompts["detect"]
    assert "[S1] It is a hot topic on the internet." in p
    assert "[S3] My life is busy." in p


@pytest.mark.anyio
async def test_rejected_candidates_are_not_shown_or_applied(client, monkeypatch):
    router = Router(
        detect=detect(cand(2, "social media and internet", "social media and the internet"),
                      cand(3, "My life", "My lives")),
        verify={"verdicts": [{"id": "c1", "valid": True}, {"id": "c2", "valid": False}], "patterns": []},
    )
    body = await review(client, monkeypatch, router)
    assert [s["original_phrase"] for s in body["suggestions"]] == ["social media and internet"]
    assert "My lives" not in body["corrected_text"]
    assert body["suggestions_verified"] is True


@pytest.mark.anyio
async def test_candidate_without_a_verdict_is_dropped(client, monkeypatch):
    router = Router(
        detect=detect(cand(2, "social media and internet", "social media and the internet"),
                      cand(3, "My life", "My lives")),
        verify={"verdicts": [{"id": "c1", "valid": True}], "patterns": []},
    )
    body = await review(client, monkeypatch, router)
    assert [s["original_phrase"] for s in body["suggestions"]] == ["social media and internet"]


@pytest.mark.anyio
async def test_patterns_come_only_from_verified_corrections(client, monkeypatch):
    content = "I graduated from high school. I met teacher there. I like the internet. Life is busy."
    router = Router(
        detect=detect(cand(1, "from high school", "from a high school"),
                      cand(2, "met teacher", "met a teacher"),
                      cand(4, "Life is", "A life is")),
        verify={
            "verdicts": [{"id": "c1", "valid": True}, {"id": "c2", "valid": True}, {"id": "c3", "valid": False}],
            "patterns": [
                {"pattern": "가산명사 단수 관사 누락", "ids": ["c1", "c2", "c3", "c99"], "fix": "a + 명사", "tip": "t"},
                {"pattern": "근거 하나뿐인 패턴", "ids": ["c1"], "fix": "x", "tip": "t"},
                {"pattern": "전부 거부된 패턴", "ids": ["c3"], "fix": "x", "tip": "t"},
            ],
        },
    )
    body = await review(client, monkeypatch, router, content)
    [p] = body["recurring_patterns"]
    assert p["pattern"] == "가산명사 단수 관사 누락"
    assert p["count"] == 2
    assert p["examples"] == ["from high school", "met teacher"]


@pytest.mark.anyio
async def test_main_call_no_longer_finds_errors(client, monkeypatch):
    router = Router(main=dict(MAIN, suggestions=[cand(1, "hot topic", "hot-button topic")],
                              recurring_patterns=[{"pattern": "옛 패턴", "count": 2, "examples": ["internet"]}]))
    body = await review(client, monkeypatch, router)
    assert body["suggestions"] == []
    assert body["recurring_patterns"] == []
    p = router.prompts["main"]
    assert '"suggestions"' not in p
    assert '"recurring_patterns"' not in p


@pytest.mark.anyio
async def test_unusable_verifier_keeps_candidates_and_says_so(client, monkeypatch):
    router = Router(
        detect=detect(cand(2, "social media and internet", "social media and the internet")),
        verify={"something": "else"},
    )
    body = await review(client, monkeypatch, router)
    assert [s["original_phrase"] for s in body["suggestions"]] == ["social media and internet"]
    assert body["suggestions_verified"] is False
    assert body["recurring_patterns"] == []


@pytest.mark.anyio
async def test_no_candidates_skips_the_verifier(client, monkeypatch):
    router = Router(detect={"suggestions": []})
    body = await review(client, monkeypatch, router)
    assert "verify" not in router.prompts
    assert body["suggestions"] == []
    assert body["suggestions_verified"] is True


@pytest.mark.anyio
async def test_each_call_is_recorded(client, monkeypatch, tmp_path):
    metrics = tmp_path / "metrics.jsonl"
    monkeypatch.setattr(settings, "REVIEW_METRICS_PATH", metrics)
    router = Router(
        detect=detect(cand(2, "social media and internet", "social media and the internet")),
        verify={"verdicts": [{"id": "c1", "valid": True}], "patterns": []},
    )
    await review(client, monkeypatch, router)
    rows = [json.loads(line) for line in metrics.read_text().splitlines()]
    calls = [r for r in rows if r["label"] != "summary"]
    assert sorted(r["label"] for r in calls) == ["detect", "main"] + ["score_content"] * 3 + ["score_language"] * 3 + ["verify"]
    for r in calls:
        assert r["seconds"] >= 0
        assert r["output_tokens"] == 50
        assert r["thinking_tokens"] == 10
        assert r["essay_id"]
    [summary] = [r for r in rows if r["label"] == "summary"]
    assert (summary["candidates"], summary["kept"], summary["dropped_unlocated"]) == (1, 1, 0)
    assert summary["verified"] is True
