"""Bands come from a separate scoring call run three times; the median of each criterion is kept.

- The main call no longer grades; the scoring prompt has no example band number to anchor on.
- Overall band = mean of the four criterion medians, rounded the IELTS way (.25 up to .5, .75 up to next band).
- Each criterion records how far the three runs disagreed (spread).
- If some scoring runs fail, the rest are used; if all fail, the review fails.
"""
import re

import pytest

from app.services.gemini_service import gemini_service, ielts_overall
from tests.fakes import Router


def score(tr, co, lx, gr, tag=""):
    return {k: {"band": b, "comment": f"{k}-{b}{tag}"}
            for k, b in (("task_response", tr), ("coherence", co), ("lexical", lx), ("grammar", gr))}


async def review(client, monkeypatch, router):
    monkeypatch.setattr(gemini_service, "_client", router)
    e = (await client.post("/api/essays", json={"prompt": "Work?", "essay_type": "free"})).json()
    return await client.post("/api/review", json={"essay_id": e["id"], "content": "Many people works long hours."})


def test_ielts_overall_rounding():
    assert ielts_overall([6.5, 6.0, 6.5, 6.0]) == 6.5    # 6.25 -> 6.5
    assert ielts_overall([7.0, 6.5, 6.5, 6.5]) == 6.5    # 6.625 -> 6.5
    assert ielts_overall([7.0, 7.0, 6.5, 6.5]) == 7.0    # 6.75 -> 7.0
    assert ielts_overall([6.0, 6.0, 6.0, 6.5]) == 6.0    # 6.125 -> 6.0


@pytest.mark.anyio
async def test_three_runs_median_per_criterion(client, monkeypatch):
    router = Router(score=[score(6.0, 6.5, 6.0, 5.5, "a"), score(7.0, 6.0, 6.5, 6.0, "b"), score(6.5, 6.5, 6.0, 6.0, "c")])
    res = await review(client, monkeypatch, router)
    assert res.status_code == 200
    r = res.json()["rubric"]
    assert router.count("score") == 3
    assert [r[k]["band"] for k in ("task_response", "coherence", "lexical", "grammar")] == [6.5, 6.5, 6.0, 6.0]
    assert r["overall_band"] == 6.5                      # mean 6.25
    assert r["task_response"]["comment"] == "task_response-6.5c"   # comment from a run that gave the median
    assert r["task_response"]["spread"] == 1.0
    assert r["lexical"]["spread"] == 0.5


@pytest.mark.anyio
async def test_failed_scoring_runs_are_skipped(client, monkeypatch):
    router = Router(score=[{"nonsense": 1}, score(7.0, 7.0, 6.5, 6.5), score(7.0, 7.0, 6.5, 6.5)])
    r = (await review(client, monkeypatch, router)).json()["rubric"]
    assert r["task_response"]["band"] == 7.0
    assert r["overall_band"] == 7.0


@pytest.mark.anyio
async def test_all_scoring_runs_failing_fails_the_review(client, monkeypatch):
    router = Router(score=[{"x": 1}, {"y": 2}, {"z": 3}])
    res = await review(client, monkeypatch, router)
    assert res.status_code == 502


@pytest.mark.anyio
async def test_main_call_no_longer_grades_and_score_prompt_has_no_anchor(client, monkeypatch):
    router = Router()
    await review(client, monkeypatch, router)
    assert '"rubric"' not in router.prompts["main"]
    p = router.prompts["score"]
    assert "[밴드 채점]" in p
    assert not re.search(r'"band"\s*:\s*\d', p)          # no example number to copy
    assert "밴드 7" in p and "밴드 5" in p               # descriptors calibrate the scale
    assert p.rindex("Many people works long hours.") > p.index("[JSON 응답 규격]")
