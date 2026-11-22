"""Which grammar fixes of an essay are already cards: read back from Anki, where each card the app makes
carries the essay and the fix as tags (so the state survives reloads and restarts, with no copy to keep in sync)."""
import pytest

from app.schemas.anki import GrammarCardRequest
from app.services import anki_service as anki_module
from app.services.anki_service import anki_service


class FakeAnki:
    def __init__(self, notes=None):
        self.notes = notes or {}          # noteId -> {"modelName", "tags"}
        self.calls = []

    def __call__(self, action, **params):
        self.calls.append((action, params))
        if action == "version":
            return 6
        if action == "canAddNotesWithErrorDetail":
            return [{"canAdd": True}]
        if action == "addTags":
            return None
        if action == "findNotes":
            return list(self.notes)
        if action == "notesInfo":
            return [{"noteId": n, **self.notes[n]} for n in params["notes"]]
        raise AssertionError(f"unexpected AnkiConnect call: {action}")

    def params_of(self, action):
        return [p for a, p in self.calls if a == action]


@pytest.fixture
def anki(monkeypatch):
    def install(notes=None):
        fake = FakeAnki(notes)
        monkeypatch.setattr(anki_service, "invoke", fake)
        return fake
    return install


@pytest.fixture
def gateway(monkeypatch):
    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"success": True, "note_id": 123, "duplicate": False}
    monkeypatch.setattr(anki_module.requests, "post", lambda url, json, timeout: Resp())


# --- tagging on add -------------------------------------------------------------

def test_a_new_grammar_card_is_tagged_with_its_essay_and_fix(anki, gateway):
    fake = anki()
    res = anki_service.add_grammar_card(GrammarCardRequest(
        sentence="I agree.", answer="agree", mistake="agrees", essay_id="e1f2", fix_id="ab12cd34"))
    assert res.success and res.note_id == 123
    [tags] = fake.params_of("addTags")
    assert tags["notes"] == [123]
    assert set(tags["tags"].split()) == {"daily-english-essay", "de-essay::e1f2", "de-fix::ab12cd34"}


def test_without_ids_only_the_app_tag_is_added(anki, gateway):
    fake = anki()
    anki_service.add_grammar_card(GrammarCardRequest(sentence="I agree.", answer="agree", mistake="agrees"))
    assert fake.params_of("addTags")[0]["tags"].split() == ["daily-english-essay"]


@pytest.mark.parametrize("bad", ["a b", "x::y", "a\nb", "é", "", "x" * 80])
def test_ids_that_could_break_a_tag_are_rejected(bad):
    with pytest.raises(ValueError):
        GrammarCardRequest(sentence="s", answer="a", essay_id=bad)
    with pytest.raises(ValueError):
        GrammarCardRequest(sentence="s", answer="a", fix_id=bad)


# --- reading back ---------------------------------------------------------------

def test_registered_fix_ids_come_from_the_tags_of_that_essays_grammar_notes(anki):
    fake = anki({
        1: {"modelName": "English Grammar", "tags": ["daily-english-essay", "de-essay::e1", "de-fix::aaaa1111"]},
        2: {"modelName": "English Grammar", "tags": ["de-essay::e1", "de-fix::bbbb2222", "other"]},
        3: {"modelName": "English Grammar", "tags": ["de-essay::e1"]},                       # old card: no fix tag
    })
    assert anki_service.grammar_registered("e1") == ["aaaa1111", "bbbb2222"]
    [q] = fake.params_of("findNotes")
    assert "tag:de-essay::e1" in q["query"] and "English Grammar" in q["query"]


def test_no_cards_means_nothing_registered_and_no_second_call(anki):
    fake = anki({})
    assert anki_service.grammar_registered("e1") == []
    assert fake.params_of("notesInfo") == []


def test_anki_being_down_means_nothing_registered_not_an_error(monkeypatch):
    def down(action, **params):
        raise ConnectionError("tunnel down")
    monkeypatch.setattr(anki_service, "invoke", down)
    assert anki_service.grammar_registered("e1") == []


def test_a_duplicate_list_of_the_same_fix_is_returned_once(anki):
    anki({1: {"modelName": "English Grammar", "tags": ["de-fix::aaaa1111"]},
          2: {"modelName": "English Grammar", "tags": ["de-fix::aaaa1111"]}})
    assert anki_service.grammar_registered("e1") == ["aaaa1111"]


# --- HTTP -----------------------------------------------------------------------

@pytest.mark.anyio
async def test_endpoint_lists_the_registered_fix_ids(client, anki):
    anki({1: {"modelName": "English Grammar", "tags": ["de-essay::e1", "de-fix::aaaa1111"]}})
    res = await client.get("/api/anki/grammar-registered/e1")
    assert res.status_code == 200 and res.json() == {"fix_ids": ["aaaa1111"]}


@pytest.mark.anyio
async def test_endpoint_rejects_an_id_that_is_not_tag_safe(client, anki):
    fake = anki()
    res = await client.get("/api/anki/grammar-registered/a b")
    assert res.status_code == 422 and fake.calls == []
