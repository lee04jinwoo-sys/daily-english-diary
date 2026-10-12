"""Bands come from two scorers, each run three times; the median of each criterion is kept.

- Content scorer ([밴드 채점-내용]): task_response and coherence, from the essay; starts right away.
- Language scorer ([밴드 채점-언어]): grammar and lexical, grounded in the verified corrections
  (count, density per 100 words, kinds); the essay is shown only to judge range. Runs after verification.
- No example band number in either prompt.
- Overall band = mean of the four medians, rounded the IELTS way (.25 up to .5, .75 up to next band).
- Each criterion records how far the runs disagreed (spread).
- Failed runs are skipped; if every run of a scorer fails, the review fails.
"""
import re

import pytest

from app.services.gemini_service import gemini_service, ielts_overall
from tests.fakes import Router

CONTENT = "Many people works long hours. I use social media and internet daily. My life is busy."


def content_score(tr, co, tag=""):
    return {"task_response": {"band": tr, "comment": f"tr-{tr}{tag}"}, "coherence": {"band": co, "comment": f"co-{co}{tag}"}}


def language_score(gr, lx, tag=""):
    return {"grammar": {"band": gr, "comment": f"gr-{gr}{tag}"}, "lexical": {"band": lx, "comment": f"lx-{lx}{tag}"}}


def cand(sentence, orig, sugg, tier="accuracy", sub="수일치(Agreement)"):
    return {"sentence": sentence, "original_phrase": orig, "suggested_phrase": sugg, "tier": tier,
            "category": "Grammar", "subcategory": sub, "explanation": "x"}


async def review(client, monkeypatch, router):
    monkeypatch.setattr(gemini_service, "_client", router)
    e = (await client.post("/api/essays", json={"prompt": "Work?", "essay_type": "free"})).json()
    return await client.post("/api/review", json={"essay_id": e["id"], "content": CONTENT})


def test_ielts_overall_rounding():
    assert ielts_overall([6.5, 6.0, 6.5, 6.0]) == 6.5    # 6.25 -> 6.5
    assert ielts_overall([7.0, 6.5, 6.5, 6.5]) == 6.5    # 6.625 -> 6.5
    assert ielts_overall([7.0, 7.0, 6.5, 6.5]) == 7.0    # 6.75 -> 7.0
    assert ielts_overall([6.0, 6.0, 6.0, 6.5]) == 6.0    # 6.125 -> 6.0


@pytest.mark.anyio
async def test_each_scorer_runs_three_times_and_medians_are_kept(client, monkeypatch):
    router = Router(
        score_content=[content_score(6.0, 6.5, "a"), content_score(7.0, 6.0, "b"), content_score(6.5, 6.5, "c")],
        score_language=[language_score(5.5, 6.0, "a"), language_score(6.0, 6.5, "b"), language_score(6.0, 6.0, "c")],
    )
    res = await review(client, monkeypatch, router)
    assert res.status_code == 200, res.text
    r = res.json()["rubric"]
    assert router.count("score_content") == 3 and router.count("score_language") == 3
    assert [r[k]["band"] for k in ("task_response", "coherence", "lexical", "grammar")] == [6.5, 6.5, 6.0, 6.0]
    assert r["overall_band"] == 6.5                                  # mean 6.25
    assert r["task_response"]["comment"] == "tr-6.5c"               # from a run that gave the median
    assert r["task_response"]["spread"] == 1.0
    assert r["grammar"]["spread"] == 0.5


@pytest.mark.anyio
async def test_language_scorer_sees_only_verified_corrections_and_density(client, monkeypatch):
    router = Router(
        detect={"suggestions": [cand(1, "Many people works", "Many people work"),
                                cand(2, "social media and internet", "social media and the internet", sub="관사(Article)"),
                                cand(3, "My life is busy", "My lives are busy")]},
        verify={"verdicts": [{"id": "c1", "valid": True}, {"id": "c2", "valid": True}, {"id": "c3", "valid": False}],
                "patterns": []},
    )
    await review(client, monkeypatch, router)
    p = router.prompts["score_language"]
    corrections = p.split("[검증된 교정]\n")[1].split("[학습자 에세이]")[0]
    assert '"Many people works" → "Many people work"' in corrections
    assert "social media and the internet" in corrections
    assert "My lives are busy" not in corrections                  # rejected by the verifier
    assert "교정 2개" in p and "100단어당 12.5개" in p            # 2 fixes in 16 words
    assert "관사(Article) 1" in p and "수일치(Agreement) 1" in p


@pytest.mark.anyio
async def test_content_scorer_does_not_wait_for_or_see_corrections(client, monkeypatch):
    router = Router(detect={"suggestions": [cand(1, "Many people works", "Many people work")]},
                    verify={"verdicts": [{"id": "c1", "valid": True}], "patterns": []})
    await review(client, monkeypatch, router)
    p = router.prompts["score_content"]
    assert "Many people work\"" not in p and "[검증된 교정]" not in p
    assert '"task_response"' in p and '"coherence"' in p
    assert '"grammar"' not in p and '"lexical"' not in p
    roles = [r for r, _ in router.calls]
    assert roles.index("verify") < roles.index("score_language")


@pytest.mark.anyio
async def test_no_anchor_numbers_and_essay_last(client, monkeypatch):
    router = Router(detect={"suggestions": [cand(1, "Many people works", "Many people work")]},
                    verify={"verdicts": [{"id": "c1", "valid": True}], "patterns": []})
    await review(client, monkeypatch, router)
    for role in ("score_content", "score_language"):
        p = router.prompts[role]
        assert not re.search(r'"band"\s*:\s*\d', p), role
        assert "밴드 7" in p and "밴드 5" in p, role
        assert p.rindex(CONTENT) > p.index("[JSON 응답 규격]"), role
    assert '"rubric"' not in router.prompts["main"]


@pytest.mark.anyio
async def test_failed_runs_are_skipped(client, monkeypatch):
    router = Router(score_content=[{"nonsense": 1}, content_score(7.0, 7.0), content_score(7.0, 7.0)],
                    score_language=[language_score(6.5, 6.5), {"bad": 2}, language_score(6.5, 6.5)])
    r = (await review(client, monkeypatch, router)).json()["rubric"]
    assert r["task_response"]["band"] == 7.0 and r["grammar"]["band"] == 6.5
    assert r["overall_band"] == 7.0                                # 6.75 -> 7.0


@pytest.mark.anyio
@pytest.mark.parametrize("role", ["score_content", "score_language"])
async def test_a_scorer_failing_every_run_fails_the_review(client, monkeypatch, role):
    router = Router(**{role: [{"x": 1}, {"y": 2}, {"z": 3}]})
    res = await review(client, monkeypatch, router)
    assert res.status_code == 502
