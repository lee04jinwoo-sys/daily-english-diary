"""Adding cards: duplicates are detected before any audio is generated. AnkiConnect is mocked."""
import pytest

from app.schemas.anki import SentenceCardRequest
from app.services.anki_service import anki_service


@pytest.fixture
def fake_anki(monkeypatch):
    calls = []

    def invoke(action, **params):
        calls.append(action)
        if action == "version":
            return 6
        if action == "canAddNotesWithErrorDetail":
            return [{"canAdd": False, "error": "cannot create note because it is a duplicate"}]
        if action == "modelFieldNames":
            return ["문장", "해설", "소리"]
        raise AssertionError(f"unexpected AnkiConnect write: {action}")

    monkeypatch.setattr(anki_service, "invoke", invoke)
    monkeypatch.setattr(anki_service, "generate_sentence_audio",
                        lambda text: (_ for _ in ()).throw(AssertionError("audio generated for a duplicate")))
    return calls


def test_duplicate_sentence_skips_audio_and_add(fake_anki):
    res = anki_service.add_sentence_card(SentenceCardRequest(sentence="He used to be healthy.", translation="t"))
    assert res.success and res.duplicate
    assert "addNote" not in fake_anki and "storeMediaFile" not in fake_anki


@pytest.mark.anyio
async def test_duplicate_vocab_skips_enrichment_and_audio(fake_anki, monkeypatch):
    from app.schemas.anki import VocabCardRequest
    from app.services import gemini_service as gmod

    async def boom(*a, **k):
        raise AssertionError("Gemini enrichment ran for a duplicate")
    monkeypatch.setattr(gmod.gemini_service, "lookup_word", boom)
    monkeypatch.setattr(anki_service, "generate_and_store_gtts",
                        lambda text: (_ for _ in ()).throw(AssertionError("audio generated for a duplicate")))
    res = await anki_service.add_vocab_card(VocabCardRequest(word="withdraw from the public eye", meaning="m"))
    assert res.success and res.duplicate
    assert "addNote" not in fake_anki
