"""Similar sentences for grammar cards: one new sentence per extra fix of a sentence that already has a card.

Anki treats the same sentence as a duplicate, so the extra fixes get a new sentence that uses the same
corrected expression. The model writes them; the code decides which ones are usable.
"""
import pytest

from app.services.gemini_service import GeminiError, gemini_service, is_valid_similar_sentence

ITEM = {"id": "a", "answer": "goes", "mistake": "go", "sentence": "He goes to school every day."}


def item(id_, answer, mistake, sentence="Reference sentence here."):
    return {"id": id_, "answer": answer, "mistake": mistake, "sentence": sentence}


# --- the validity rules ---------------------------------------------------------

@pytest.mark.parametrize("sentence", [
    "My sister goes to the gym on Sundays.",
    "My sister GOES to the gym on Sundays.",         # case is the card's business, not ours
])
def test_valid_sentences(sentence):
    assert is_valid_similar_sentence(sentence, "goes", "go", "He goes to school every day.")


@pytest.mark.parametrize("sentence,why", [
    ("", "empty"),
    ("My sister walks to the gym.", "answer missing"),
    ("She goes there and he goes home.", "answer twice, so two blanks"),
    ("My sister goesx to the gym.", "answer only inside a longer word"),
    ("My sister goes to the gym, but they go late.", "the wrong form is also in the sentence"),
    ("He goes to school every day.", "same as the reference sentence"),
    ("My sister goes to the gym. She likes it.", "two sentences"),
    ("my sister goes to the gym on Sundays.", "starts in lowercase"),
    ("My sister goes to the gym on Sundays", "no final punctuation"),
])
def test_invalid_sentences(sentence, why):
    assert not is_valid_similar_sentence(sentence, "goes", "go", "He goes to school every day."), why


def test_wrong_form_inside_the_answer_is_not_a_conflict():
    # answer "is a", wrong form "is": the "is" belongs to the blank, not to the rest of the sentence
    assert is_valid_similar_sentence("There is a good reason for this.", "is a", "is", "There is a problem.")
    assert not is_valid_similar_sentence("There is a good reason, and this is why.", "is a", "is", "There is a problem.")


# --- generate_similar_sentences -------------------------------------------------

def script(monkeypatch, *answers):
    calls = []

    async def fake(prompt, temperature, **kw):
        calls.append({"prompt": prompt, "kw": kw})
        a = answers[len(calls) - 1]
        if isinstance(a, Exception):
            raise a
        return a

    monkeypatch.setattr(gemini_service, "_generate_json", fake)
    return calls


def reply(**by_id):
    return {"items": [{"id": k, "sentence": v} for k, v in by_id.items()]}


def ok(*ids, bad=()):
    """The verifier's answer: ok for `ids`, not ok (with a reason) for `bad`."""
    return {"items": [{"id": i, "ok": True} for i in ids] + [{"id": i, "ok": False, "problem": "x"} for i in bad]}


@pytest.mark.anyio
async def test_returns_valid_sentences_by_id_and_uses_free_routes_first(monkeypatch):
    calls = script(monkeypatch, reply(a="My sister goes to the gym on Sundays.", b="Many people work long hours."),
                   ok("a", "b"))
    out = await gemini_service.generate_similar_sentences([ITEM, item("b", "work", "works")])
    assert out == {"a": "My sister goes to the gym on Sundays.", "b": "Many people work long hours."}
    assert len(calls) == 2                                   # one to write, one to check
    assert all(c["kw"].get("free_first") is True for c in calls)
    assert "goes" in calls[0]["prompt"] and "He goes to school every day." in calls[0]["prompt"]


@pytest.mark.anyio
async def test_the_checker_rejects_ungrammatical_sentences_and_they_are_written_again(monkeypatch):
    """'cause people have' passes every mechanical rule, only a reader sees it is wrong."""
    calls = script(monkeypatch,
                   reply(a="Smartphones often cause people have trouble sleeping."),
                   ok(bad=["a"]),
                   reply(a="Smartphones often make people have trouble sleeping."),
                   ok("a"))
    out = await gemini_service.generate_similar_sentences([item("a", "people have", "people to have")])
    assert out == {"a": "Smartphones often make people have trouble sleeping."}
    assert len(calls) == 4


@pytest.mark.anyio
async def test_a_sentence_rejected_twice_is_left_out(monkeypatch):
    bad = "Smartphones often cause people have trouble sleeping."
    script(monkeypatch, reply(a=bad), ok(bad=["a"]), reply(a=bad), ok(bad=["a"]))
    assert await gemini_service.generate_similar_sentences([item("a", "people have", "people to have")]) == {}


@pytest.mark.anyio
async def test_an_id_the_checker_does_not_mention_is_not_accepted(monkeypatch):
    script(monkeypatch, reply(a="My sister goes to the gym on Sundays."), ok(), reply(a="Anna goes to the gym on Sundays."), ok())
    assert await gemini_service.generate_similar_sentences([ITEM]) == {}


@pytest.mark.anyio
async def test_the_checker_may_answer_with_a_bare_list(monkeypatch):
    """Free models sometimes drop the wrapping object."""
    script(monkeypatch, reply(a="My sister goes to the gym on Sundays."), [{"id": "a", "ok": True}])
    assert await gemini_service.generate_similar_sentences([ITEM]) == {"a": "My sister goes to the gym on Sundays."}


@pytest.mark.anyio
async def test_only_mechanically_valid_sentences_are_sent_to_the_checker(monkeypatch):
    calls = script(monkeypatch, reply(a="My sister goes to the gym on Sundays.", b="Nothing useful here."), ok("a"),
                   reply(b="Many people work long hours."), ok("b"))
    out = await gemini_service.generate_similar_sentences([ITEM, item("b", "work", "works")])
    assert out == {"a": "My sister goes to the gym on Sundays.", "b": "Many people work long hours."}
    assert "id=a" in calls[1]["prompt"] and "id=b" not in calls[1]["prompt"]   # b failed the mechanical rules
    assert "id=b" in calls[2]["prompt"] and "id=a" not in calls[2]["prompt"]   # only b is written again


@pytest.mark.anyio
async def test_an_item_with_no_valid_sentence_after_the_retry_is_left_out(monkeypatch):
    calls = script(monkeypatch, reply(a="bad"), reply(a="still bad"))
    assert await gemini_service.generate_similar_sentences([ITEM]) == {}
    assert len(calls) == 2                                   # nothing reached the checker


@pytest.mark.anyio
async def test_two_items_cannot_get_the_same_sentence(monkeypatch):
    same = "Anything goes in this old house."
    script(monkeypatch, reply(a=same, b=same), ok("a"), reply(b="Most people work late."))
    out = await gemini_service.generate_similar_sentences([item("a", "goes", "go"), item("b", "goes", "go")])
    assert out == {"a": same}


@pytest.mark.anyio
async def test_ids_that_were_not_asked_for_are_ignored(monkeypatch):
    script(monkeypatch, reply(a="My sister goes to the gym on Sundays.", zzz="Anything goes here."), ok("a"))
    assert set((await gemini_service.generate_similar_sentences([ITEM])).keys()) == {"a"}


@pytest.mark.anyio
async def test_no_items_means_no_model_call(monkeypatch):
    calls = script(monkeypatch)
    assert await gemini_service.generate_similar_sentences([]) == {}
    assert calls == []


@pytest.mark.anyio
async def test_a_model_failure_is_raised(monkeypatch):
    script(monkeypatch, RuntimeError("quota"))
    with pytest.raises(GeminiError):
        await gemini_service.generate_similar_sentences([ITEM])


@pytest.mark.anyio
async def test_a_failing_checker_is_raised_not_skipped(monkeypatch):
    """Unchecked sentences must never be accepted."""
    script(monkeypatch, reply(a="My sister goes to the gym on Sundays."), RuntimeError("quota"))
    with pytest.raises(GeminiError):
        await gemini_service.generate_similar_sentences([ITEM])


# --- HTTP -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_endpoint(client, monkeypatch):
    script(monkeypatch, reply(a="My sister goes to the gym on Sundays."), ok("a"))
    res = await client.post("/api/anki/similar-sentences", json={"items": [ITEM]})
    assert res.status_code == 200
    assert res.json() == {"sentences": {"a": "My sister goes to the gym on Sundays."}}


@pytest.mark.anyio
async def test_endpoint_reports_a_model_failure_as_502(client, monkeypatch):
    script(monkeypatch, RuntimeError("quota"))
    res = await client.post("/api/anki/similar-sentences", json={"items": [ITEM]})
    assert res.status_code == 502
