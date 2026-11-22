"""Sentence-by-sentence study pairs: every learner sentence gets its own rewrite and its own translations.

The C1+ rewrite of the whole essay is not sentence-parallel with the learner's text (it is often shorter),
so pairing by position put the wrong Korean meaning on sentences and, past the end, left blanks.
"""
import pytest

from tests.test_lean_review import CONTENT, PAIRS, _reviewed_essay


def pair(index, **over):
    p = {"index": index, "native": f"native {index}", "translation": f"교정 해석 {index}",
         "native_translation": f"원어민 해석 {index}", "explanation": "x", "vocab": []}
    p.update(over)
    return p


@pytest.mark.anyio
async def test_prompt_lists_each_sentence_and_does_not_include_the_whole_rewrite(client, monkeypatch):
    essay_id, body, rec = await _reviewed_essay(client, monkeypatch, PAIRS)
    await client.post(f"/api/essays/{essay_id}/sentence-pairs")
    prompt = rec.prompts["pairs"]
    assert "1. Many people work long hours." in prompt
    assert "2. I use social media and the internet every day." in prompt
    assert body["upgraded_text"] not in prompt          # nothing to align against by position
    assert "[다시 쓴 글]" not in prompt


@pytest.mark.anyio
async def test_each_pair_has_a_translation_for_the_corrected_and_for_the_native_sentence(client, monkeypatch):
    essay_id, _, _ = await _reviewed_essay(client, monkeypatch, PAIRS)
    pairs = (await client.post(f"/api/essays/{essay_id}/sentence-pairs")).json()
    assert pairs[0]["translation"] == "많은 사람이 오래 일한다."
    assert pairs[0]["native_translation"] == "많은 사람이 장시간 일한다."
    assert pairs[1]["native_translation"] == "나는 매일 소셜 미디어와 인터넷을 쓴다."


@pytest.mark.anyio
@pytest.mark.parametrize("bad", [
    {"pairs": [pair(1)]},                                        # sentence 2 missing
    {"pairs": [pair(1), pair(2, translation="")]},               # blank Korean meaning
    {"pairs": [pair(1), pair(2, native_translation="")]},
    {"pairs": [pair(1), pair(2, native="")]},
])
async def test_incomplete_answer_is_retried_once(client, monkeypatch, bad):
    good = {"pairs": [pair(1), pair(2)]}
    essay_id, _, rec = await _reviewed_essay(client, monkeypatch, bad, good)
    res = await client.post(f"/api/essays/{essay_id}/sentence-pairs")
    assert res.status_code == 200, res.text
    assert [p["native"] for p in res.json()] == ["native 1", "native 2"]
    assert rec.count("pairs") == 2


@pytest.mark.anyio
async def test_still_incomplete_after_the_retry_is_an_error_and_nothing_is_stored(client, monkeypatch):
    bad = {"pairs": [pair(1)]}
    essay_id, _, rec = await _reviewed_essay(client, monkeypatch, bad, bad)
    res = await client.post(f"/api/essays/{essay_id}/sentence-pairs")
    assert res.status_code == 502
    assert rec.count("pairs") == 2
    saved = (await client.get(f"/api/essays/{essay_id}")).json()
    assert saved["review"]["sentence_pairs"] == []      # no half-filled pairs to build Anki cards from


@pytest.mark.anyio
async def test_an_extra_unknown_index_is_ignored(client, monkeypatch):
    essay_id, _, _ = await _reviewed_essay(client, monkeypatch, {"pairs": [pair(1), pair(2), pair(9)]})
    pairs = (await client.post(f"/api/essays/{essay_id}/sentence-pairs")).json()
    assert [p["index"] for p in pairs] == [1, 2]
