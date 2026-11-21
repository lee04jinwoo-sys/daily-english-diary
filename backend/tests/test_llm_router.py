"""Free-tier LLM routing: free routes first, the paid Gemini key only when every free route fails."""
import json

import pytest

from app.services import gemini_service as gs
from app.services import llm_router
from app.services.llm_router import AllRoutesFailed, Route, generate_json
from tests.fakes import Router

ROUTES = [
    Route("a", "https://a.example/v1/chat/completions", "model-a", "KEY_A"),
    Route("b", "https://b.example/v1/chat/completions", "model-b", "KEY_B"),
]
ENV = {"KEY_A": "ka", "KEY_B": "kb"}


class FakeResponse:
    def __init__(self, status_code=200, content=None, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {"choices": [{"message": {"content": content}}]}

    def json(self):
        return self._body


def make_post(*outcomes):
    """Each call consumes one outcome: a FakeResponse is returned, an Exception is raised."""
    calls = []

    async def post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    post.calls = calls
    return post


@pytest.mark.anyio
async def test_first_route_answers_and_second_is_untouched():
    post = make_post(FakeResponse(content='{"ok": 1}'))
    data, name = await generate_json("hello", 0.2, routes=ROUTES, post=post, env=ENV)
    assert (data, name) == ({"ok": 1}, "a")
    assert len(post.calls) == 1
    sent = post.calls[0]
    assert sent["headers"]["Authorization"] == "Bearer ka"
    assert sent["json"]["model"] == "model-a"
    assert sent["json"]["messages"] == [{"role": "user", "content": "hello"}]
    assert sent["json"]["response_format"] == {"type": "json_object"}


@pytest.mark.anyio
async def test_route_without_key_is_skipped_with_no_request():
    post = make_post(FakeResponse(content='{"ok": 1}'))
    _, name = await generate_json("p", 0.2, routes=ROUTES, post=post, env={"KEY_B": "kb"})
    assert name == "b"
    assert len(post.calls) == 1 and post.calls[0]["url"].startswith("https://b.example")


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [
    FakeResponse(status_code=429),
    FakeResponse(status_code=503),
    TimeoutError("slow"),
    FakeResponse(content='{"broken": '),
    FakeResponse(content=None),
    FakeResponse(body={"unexpected": True}),
])
async def test_failure_falls_through_to_next_route(failure):
    post = make_post(failure, FakeResponse(content='{"ok": 2}'))
    data, name = await generate_json("p", 0.2, routes=ROUTES, post=post, env=ENV)
    assert (data, name) == ({"ok": 2}, "b")
    assert len(post.calls) == 2


@pytest.mark.anyio
async def test_fenced_json_is_parsed():
    post = make_post(FakeResponse(content='```json\n{"ok": 3}\n```'))
    data, _ = await generate_json("p", 0.2, routes=ROUTES, post=post, env=ENV)
    assert data == {"ok": 3}


@pytest.mark.anyio
async def test_all_routes_failing_raises_with_every_reason():
    post = make_post(FakeResponse(status_code=429), TimeoutError("slow"))
    with pytest.raises(AllRoutesFailed) as e:
        await generate_json("p", 0.2, routes=ROUTES, post=post, env=ENV)
    assert "a: " in str(e.value) and "b: " in str(e.value)


@pytest.mark.anyio
async def test_no_keys_fails_without_any_request():
    post = make_post()
    with pytest.raises(AllRoutesFailed):
        await generate_json("p", 0.2, routes=ROUTES, post=post, env={})
    assert post.calls == []


# --- wiring into GeminiService._generate_json ---------------------------------

def fake_free(monkeypatch, result):
    """Replace the router; result is a dict to return or an exception to raise. Returns the call log."""
    calls = []

    async def fake(prompt, temperature, **kw):
        calls.append(prompt)
        if isinstance(result, Exception):
            raise result
        return result, "fake-free"

    monkeypatch.setattr(llm_router, "generate_json", fake)
    return calls


@pytest.mark.anyio
async def test_free_first_answer_skips_the_paid_client(monkeypatch):
    calls = fake_free(monkeypatch, {"ok": "free"})
    paid = Router()
    monkeypatch.setattr(gs.gemini_service, "_client", paid)
    assert await gs.gemini_service._generate_json("p", 0.2, free_first=True) == {"ok": "free"}
    assert calls == ["p"] and paid.calls == []


@pytest.mark.anyio
async def test_free_first_failure_falls_back_to_the_paid_client(monkeypatch):
    fake_free(monkeypatch, AllRoutesFailed("all down"))
    paid = Router(main={"ok": "paid"})
    monkeypatch.setattr(gs.gemini_service, "_client", paid)
    assert await gs.gemini_service._generate_json("p", 0.2, free_first=True) == {"ok": "paid"}
    assert len(paid.calls) == 1


@pytest.mark.anyio
async def test_default_never_touches_free_routes(monkeypatch):
    """Scoring and error detection stay on the paid model so band trends stay comparable."""
    calls = fake_free(monkeypatch, {"ok": "free"})
    paid = Router(main={"ok": "paid"})
    monkeypatch.setattr(gs.gemini_service, "_client", paid)
    assert await gs.gemini_service._generate_json("p", 0.2) == {"ok": "paid"}
    assert calls == []


@pytest.mark.anyio
async def test_lookup_word_goes_free_first(monkeypatch):
    calls = fake_free(monkeypatch, {"word": "ubiquitous", "meaning": "어디에나 있는"})
    monkeypatch.setattr(gs.gemini_service, "_client", Router())
    out = await gs.gemini_service.lookup_word("ubiquitous", "ctx")
    assert out["meaning"] == "어디에나 있는" and len(calls) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("card_type", ["sentence", "vocab"])
async def test_anki_preview_goes_free_first(monkeypatch, card_type):
    calls = fake_free(monkeypatch, {"translation": "t", "meaning": "m", "front": "x"})
    monkeypatch.setattr(gs.gemini_service, "_client", Router())
    await gs.gemini_service.generate_anki_card_preview(card_type, "some text", "ctx")
    assert len(calls) == 1


@pytest.mark.anyio
async def test_sentence_pairs_go_free_first(monkeypatch):
    from app.schemas.review import ReviewResponse
    from tests.test_essays import FAKE_REVIEW
    calls = fake_free(monkeypatch, {"pairs": []})
    monkeypatch.setattr(gs.gemini_service, "_client", Router())
    review = ReviewResponse(**{**FAKE_REVIEW, "essay_id": "e1", "original_text": "I like cats.", "upgraded_text": "Cats delight me."})
    await gs.gemini_service.generate_sentence_pairs(review)
    assert len(calls) == 1
