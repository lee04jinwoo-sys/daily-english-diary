"""Phase 1: diary -> argumentative essay."""
import random
from collections import Counter

import pytest

from app.services import topic_service as topic_module
from app.services.gemini_service import gemini_service
from app.services.topic_service import ESSAY_TYPES, THEMES, load_topics, pick_topic


# ---------- topic bank (IELTS Task 2 questions, see scripts/build_ielts_topics.py) ----------

def test_topic_bank_is_well_formed():
    topics = load_topics()
    assert len(topics) >= 1000
    ids = [t["id"] for t in topics]
    assert len(ids) == len(set(ids)), "topic ids must be unique"
    for t in topics:
        assert t["type"] in ESSAY_TYPES and t["type"] not in ("free", "hypothetical")
        assert t["category"] == "ielts"
        assert t["theme"] in THEMES
        assert len(t["prompt"]) >= 60 and t["essays"] >= 1
    # every Task 2 type is in the bank
    assert {t["type"] for t in topics} == {"agree_disagree", "discuss_both", "adv_disadv", "problem_solution",
                                           "two_part"}


def _topic(i, type_, theme="education"):
    return {"id": f"t{i}", "category": "ielts", "type": type_, "theme": theme, "prompt": f"Prompt {i}?", "essays": 1}


def test_pick_topic_skips_used_and_excluded():
    topics = load_topics()
    used = {t["id"] for t in topics[:-2]}
    excluded = {topics[-1]["id"]}
    picked = pick_topic(topics, used_ids=used, exclude_ids=excluded, last_type=None, rng=random.Random(0))
    assert picked["id"] == topics[-2]["id"]


def test_pick_topic_recycles_when_bank_exhausted():
    topics = load_topics()
    used = {t["id"] for t in topics}
    picked = pick_topic(topics, used_ids=used, exclude_ids=set(), last_type=None, rng=random.Random(0))
    assert picked is not None


def test_pick_topic_avoids_last_type_and_theme():
    topics = load_topics()
    for seed in range(30):
        picked = pick_topic(topics, used_ids=set(), exclude_ids=set(), last_type="agree_disagree",
                            last_theme="education", rng=random.Random(seed))
        assert picked["type"] != "agree_disagree" and picked["theme"] != "education"


def test_pick_topic_balances_types_not_bank_share():
    # 90% of this bank is agree_disagree; suggestions should still spread across types.
    topics = [_topic(i, "agree_disagree") for i in range(90)] + [_topic(100 + i, "two_part") for i in range(10)]
    rng = random.Random(42)
    counts = Counter(pick_topic(topics, used_ids=set(), exclude_ids=set(), last_type=None, rng=rng)["type"]
                     for _ in range(2000))
    assert 0.4 < counts["two_part"] / 2000 < 0.6


def test_pick_topic_falls_back_when_only_last_theme_is_left():
    topics = [_topic(1, "two_part", "education")]
    picked = pick_topic(topics, used_ids=set(), exclude_ids=set(), last_type="two_part", last_theme="education",
                        rng=random.Random(0))
    assert picked["id"] == "t1"


@pytest.mark.anyio
async def test_suggest_endpoint_skips_topics_already_written(client, monkeypatch):
    topics = load_topics()[:2]
    monkeypatch.setattr(topic_module, "load_topics", lambda: topics)
    await client.post("/api/essays", json={"topic_id": topics[0]["id"], "prompt": topics[0]["prompt"],
                                           "essay_type": topics[0]["type"], "category": topics[0]["category"]})
    res = await client.get("/api/topics/suggest")
    assert res.status_code == 200
    assert res.json()["id"] == topics[1]["id"]


# ---------- essays ----------

@pytest.mark.anyio
async def test_free_topic_and_multiple_essays_per_day(client):
    a = await client.post("/api/essays", json={"prompt": "Is chess a sport?", "essay_type": "free"})
    b = await client.post("/api/essays", json={"prompt": "Should I learn Rust?", "essay_type": "free"})
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["id"] != b.json()["id"]
    assert a.json()["topic_id"] is None
    assert a.json()["category"] == "free"

    lst = (await client.get("/api/essays")).json()
    assert lst["total_count"] == 2


@pytest.mark.anyio
async def test_essay_autosave_and_get(client):
    e = (await client.post("/api/essays", json={"prompt": "Is chess a sport?", "essay_type": "free"})).json()
    res = await client.patch(f"/api/essays/{e['id']}", json={"content": "Chess is a sport because it is hard."})
    assert res.status_code == 200
    got = (await client.get(f"/api/essays/{e['id']}")).json()
    assert got["content"].startswith("Chess")
    assert got["word_count"] == 8
    assert got["is_reviewed"] is False


@pytest.mark.anyio
async def test_unknown_essay_is_404(client):
    assert (await client.get("/api/essays/nope")).status_code == 404


@pytest.mark.anyio
async def test_revise_creates_linked_copy(client):
    e = (await client.post("/api/essays", json={"prompt": "Is chess a sport?", "essay_type": "free"})).json()
    await client.patch(f"/api/essays/{e['id']}", json={"content": "Chess is a sport."})
    res = await client.post(f"/api/essays/{e['id']}/revise")
    assert res.status_code == 200
    r = res.json()
    assert r["revision_of"] == e["id"]
    assert r["prompt"] == e["prompt"]
    assert r["content"] == "Chess is a sport."
    assert r["id"] != e["id"]


FAKE_REVIEW = {
    "corrected_text": "Chess is a sport because it is hard.",
    "upgraded_text": "Chess qualifies as a sport because it demands intense effort.",
    "overall_feedback": "논지는 분명하지만 근거가 하나뿐입니다.",
    "rubric": {
        "task_response": {"band": 6.3, "comment": "입장은 있으나 전개 부족"},
        "coherence": {"band": 6, "comment": "c"},
        "lexical": {"band": 12, "comment": "l"},
        "grammar": {"band": -1, "comment": "g"},
        "overall_band": 6.74,
    },
    "argument": {
        "thesis": "명확함",
        "strongest_point": "s",
        "weakest_point": "w",
        "missing_counterargument": "체스는 신체 활동이 없다는 반론",
        "paragraph_comments": [{"paragraph": 1, "comment": "근거 추가"}],
    },
    "revision_focus": ["반론 문단 추가", "근거 2개 이상"],
    "suggestions": [{
        "original_phrase": "it is hard",
        "suggested_phrase": "it is demanding",
        "tier": "idiom",
        "category": "Vocabulary",
        "subcategory": "어휘(Vocabulary)",
        "explanation": "더 정확한 단어",
    }],
    "sentence_pairs": [],
    "key_expressions": [],
}


class _FakeModels:
    def __init__(self, payload):
        self.payload = payload

    async def generate_content(self, *a, **k):
        import json

        class R:
            text = json.dumps(self.payload)
        return R()


class _FakeClient:
    def __init__(self, payload):
        class Aio:
            models = _FakeModels(payload)
        self.aio = Aio()


@pytest.mark.anyio
async def test_review_is_persisted_with_clamped_bands(client, monkeypatch):
    monkeypatch.setattr(gemini_service, "_client", _FakeClient(FAKE_REVIEW))
    e = (await client.post("/api/essays", json={"prompt": "Is chess a sport?", "essay_type": "free"})).json()
    content = "Chess is a sport because it is hard."
    await client.patch(f"/api/essays/{e['id']}", json={"content": content})

    res = await client.post("/api/review", json={"essay_id": e["id"], "content": content})
    assert res.status_code == 200
    body = res.json()
    r = body["rubric"]
    assert r["task_response"]["band"] == 6.5   # rounded to nearest 0.5
    assert r["lexical"]["band"] == 9.0         # clamped
    assert r["grammar"]["band"] == 0.0         # clamped
    # Overall is computed from the criteria (6.5, 6.0, 9.0, 0.0 -> 5.375 -> 5.5), not taken from the model.
    assert r["overall_band"] == 5.5
    assert body["suggestions"][0]["start_idx"] == content.index("it is hard")

    saved = (await client.get(f"/api/essays/{e['id']}")).json()
    assert saved["is_reviewed"] is True
    assert saved["overall_band"] == 5.5
    assert saved["review"]["argument"]["missing_counterargument"].startswith("체스")
    assert saved["review"]["revision_focus"] == ["반론 문단 추가", "근거 2개 이상"]
    sugs = (await client.get(f"/api/essays/{e['id']}/suggestions")).json()
    assert len(sugs) == 1 and sugs[0]["tier"] == "idiom"


@pytest.mark.anyio
async def test_review_of_unknown_essay_is_404(client):
    res = await client.post("/api/review", json={"essay_id": "nope", "content": "Some essay text."})
    assert res.status_code == 404


@pytest.mark.anyio
async def test_failed_review_leaves_essay_unreviewed(client, monkeypatch):
    class Boom:
        class aio:
            class models:
                @staticmethod
                async def generate_content(*a, **k):
                    raise RuntimeError("down")
    monkeypatch.setattr(gemini_service, "_client", Boom())
    e = (await client.post("/api/essays", json={"prompt": "Is chess a sport?", "essay_type": "free"})).json()
    res = await client.post("/api/review", json={"essay_id": e["id"], "content": "Chess is a sport."})
    assert res.status_code == 502
    saved = (await client.get(f"/api/essays/{e['id']}")).json()
    assert saved["is_reviewed"] is False
    assert saved["overall_band"] is None


@pytest.mark.anyio
async def test_delete_essay_removes_its_suggestions(client, monkeypatch):
    monkeypatch.setattr(gemini_service, "_client", _FakeClient(FAKE_REVIEW))
    e = (await client.post("/api/essays", json={"prompt": "Is chess a sport?", "essay_type": "free"})).json()
    await client.post("/api/review", json={"essay_id": e["id"], "content": "Chess is a sport because it is hard."})
    assert (await client.delete(f"/api/essays/{e['id']}")).status_code == 200
    assert (await client.get(f"/api/essays/{e['id']}")).status_code == 404
    assert (await client.get(f"/api/essays/{e['id']}/suggestions")).json() == []


@pytest.mark.anyio
async def test_stats_are_built_from_essays(client, monkeypatch):
    monkeypatch.setattr(gemini_service, "_client", _FakeClient(FAKE_REVIEW))
    e = (await client.post("/api/essays", json={"prompt": "Is chess a sport?", "essay_type": "free"})).json()
    content = "Chess is a sport because it is hard."
    await client.patch(f"/api/essays/{e['id']}", json={"content": content})
    await client.post("/api/review", json={"essay_id": e["id"], "content": content})

    s = (await client.get("/api/stats")).json()
    assert s["total_essays"] == 1
    assert s["total_words"] == 8
    assert s["current_streak"] == 1
    assert s["band_trends"][0]["overall_band"] == 5.5
    assert s["band_trends"][0]["lexical"] == 9.0
    assert s["type_bands"]["free"] == 5.5


@pytest.mark.anyio
async def test_sentence_length_suggestions_are_dropped(client, monkeypatch):
    content = "If these changes happen, I think more people will decide to have children in the future."
    payload = dict(FAKE_REVIEW, suggestions=[
        {"original_phrase": "If these changes happen, I think more people will decide to have children",
         "suggested_phrase": "Such systemic interventions would foster an environment conducive to parenthood",
         "tier": "style", "category": "Clarity", "subcategory": "문체", "explanation": "x"},
        {"original_phrase": "decide to have", "suggested_phrase": "choose to have",
         "tier": "style", "category": "Vocabulary", "subcategory": "어휘", "explanation": "y"},
    ])
    monkeypatch.setattr(gemini_service, "_client", _FakeClient(payload))
    e = (await client.post("/api/essays", json={"prompt": "Birth rates?", "essay_type": "free"})).json()
    body = (await client.post("/api/review", json={"essay_id": e["id"], "content": content})).json()
    assert [s["original_phrase"] for s in body["suggestions"]] == ["decide to have"]
