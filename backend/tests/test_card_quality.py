"""Before a grammar card is added: Sonnet (Claude CLI) fixes errors outside the blank and writes the Korean
translation, the code checks the shape, and a second Sonnet call checks grammar and that the translation
matches. The card then carries that translation, so Anki Manager does not write its own."""
import json

import pytest

from app.core.config import settings
from app.schemas.anki import GrammarCardRequest
from app.services import anki_service as anki_module
from app.services import claude_cli
from app.services.anki_service import anki_service
from app.services.gemini_service import GeminiError, gemini_service

ITEM = {"id": "a", "sentence": "The result of the accidents are unpredictable.", "answer": "accidents", "mistake": "accident"}
GOOD = "The result of the accidents is unpredictable."
KO = "그 사고들의 결과는 예측할 수 없다."


def drafts(**by_id):
    return {"items": [{"id": k, "sentence": s, "translation": t} for k, (s, t) in by_id.items()]}


def verdict(ok=(), bad=()):
    return {"items": [{"id": i, "grammar_ok": True, "translation_ok": True} for i in ok]
            + [{"id": i, "grammar_ok": False, "translation_ok": True, "problem": f"problem {i}"} for i in bad]}


def script(monkeypatch, *answers):
    calls = []

    async def fake(prompt, model=None, run=None):
        calls.append({"prompt": prompt, "model": model})
        a = answers[len(calls) - 1]
        if isinstance(a, Exception):
            raise a
        return a, {"input_tokens": 1, "output_tokens": 1, "thinking_tokens": 0}

    monkeypatch.setattr(claude_cli, "generate_json", fake)
    return calls


@pytest.mark.anyio
async def test_a_fixed_sentence_and_its_translation_come_back(monkeypatch):
    calls = script(monkeypatch, drafts(a=(GOOD, KO)), verdict(ok=["a"]))
    out = await gemini_service.prepare_grammar_cards([ITEM])
    assert out == {"cards": {"a": {"sentence": GOOD, "translation": KO}}, "rejected": {}}
    assert len(calls) == 2
    assert all(c["model"] == settings.CLAUDE_CARD_MODEL for c in calls)
    assert "accidents" in calls[0]["prompt"] and ITEM["sentence"] in calls[0]["prompt"]
    assert GOOD in calls[1]["prompt"] and KO in calls[1]["prompt"]


def test_the_card_model_is_sonnet_by_default():
    assert settings.CLAUDE_CARD_MODEL == "claude-sonnet-5-5"


@pytest.mark.anyio
@pytest.mark.parametrize("bad_sentence,bad_translation", [
    ("The result of the accident is unpredictable.", KO),                       # the blank answer is gone
    ("The accidents and the accidents are unpredictable.", KO),                 # answer twice -> two blanks
    ("The accidents happened. The result is unpredictable.", KO),               # two sentences
    ("the result of the accidents is unpredictable.", KO),                      # not a sentence start
    (GOOD, "The result is unpredictable."),                                     # translation is not Korean
    (GOOD, ""),
])
async def test_code_rules_send_an_item_back_once_and_then_reject_it(monkeypatch, bad_sentence, bad_translation):
    calls = script(monkeypatch, drafts(a=(bad_sentence, bad_translation)), drafts(a=(bad_sentence, bad_translation)))
    out = await gemini_service.prepare_grammar_cards([ITEM])
    assert out["cards"] == {} and "a" in out["rejected"]
    assert len(calls) == 2           # nothing reached the checker


@pytest.mark.anyio
async def test_the_checker_rejection_is_retried_and_its_reason_is_kept(monkeypatch):
    calls = script(monkeypatch, drafts(a=(GOOD, KO)), verdict(bad=["a"]), drafts(a=(GOOD, KO)), verdict(bad=["a"]))
    out = await gemini_service.prepare_grammar_cards([ITEM])
    assert out == {"cards": {}, "rejected": {"a": "problem a"}}
    assert len(calls) == 4


@pytest.mark.anyio
async def test_a_retry_that_passes_is_accepted_and_only_failing_items_are_resent(monkeypatch):
    b = {"id": "b", "sentence": "She go to school.", "answer": "go", "mistake": "goes"}  # deliberately odd answer
    calls = script(monkeypatch,
                   drafts(a=(GOOD, KO), b=("She will go to school.", "그녀는 학교에 갈 것이다.")),
                   verdict(ok=["b"], bad=["a"]),
                   drafts(a=("The result of the accidents was unpredictable.", "그 사고들의 결과는 예측할 수 없었다.")),
                   verdict(ok=["a"]))
    out = await gemini_service.prepare_grammar_cards([ITEM, b])
    assert set(out["cards"]) == {"a", "b"} and out["rejected"] == {}
    assert "id=a" in calls[2]["prompt"] and "id=b" not in calls[2]["prompt"]


@pytest.mark.anyio
async def test_the_checker_may_answer_with_a_bare_list(monkeypatch):
    script(monkeypatch, drafts(a=(GOOD, KO)), [{"id": "a", "grammar_ok": True, "translation_ok": True}])
    assert (await gemini_service.prepare_grammar_cards([ITEM]))["cards"]["a"]["sentence"] == GOOD


@pytest.mark.anyio
async def test_no_items_means_no_call(monkeypatch):
    calls = script(monkeypatch)
    assert await gemini_service.prepare_grammar_cards([]) == {"cards": {}, "rejected": {}}
    assert calls == []


@pytest.mark.anyio
async def test_a_cli_failure_is_raised(monkeypatch):
    script(monkeypatch, claude_cli.ClaudeCliError("limit"))
    with pytest.raises(GeminiError):
        await gemini_service.prepare_grammar_cards([ITEM])


@pytest.mark.anyio
async def test_endpoint(client, monkeypatch):
    script(monkeypatch, drafts(a=(GOOD, KO)), verdict(ok=["a"]))
    res = await client.post("/api/anki/prepare-grammar-cards", json={"items": [ITEM]})
    assert res.status_code == 200
    assert res.json() == {"cards": {"a": {"sentence": GOOD, "translation": KO}}, "rejected": {}}


@pytest.mark.anyio
async def test_endpoint_reports_a_cli_failure_as_502(client, monkeypatch):
    script(monkeypatch, claude_cli.ClaudeCliError("limit"))
    assert (await client.post("/api/anki/prepare-grammar-cards", json={"items": [ITEM]})).status_code == 502


# --- the translation travels with the card ---------------------------------------

@pytest.fixture
def gateway(monkeypatch):
    sent = []

    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"success": True, "note_id": 1, "duplicate": False}

    def post(url, json, timeout):
        sent.append(json)
        return Resp()

    monkeypatch.setattr(anki_module.requests, "post", post)
    monkeypatch.setattr(anki_service, "invoke", lambda action, **p: 6 if action == "version" else ([{"canAdd": True}] if action == "canAddNotesWithErrorDetail" else None))
    return sent


def test_the_prepared_translation_is_sent_to_the_gateway(gateway):
    anki_service.add_grammar_card(GrammarCardRequest(sentence=GOOD, answer="accidents", mistake="accident", translation=KO))
    assert gateway[0]["translation"] == KO


def test_without_a_translation_the_gateway_writes_its_own(gateway):
    anki_service.add_grammar_card(GrammarCardRequest(sentence=GOOD, answer="accidents", mistake="accident"))
    assert not gateway[0].get("translation")
