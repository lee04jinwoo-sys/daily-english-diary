"""Undo of a card the app just created. It deletes one note by id and only when it is safe:
an app-made note (model + tag) whose cards were never reviewed. Anything else is refused untouched."""
import pytest

from app.services.anki_service import anki_service


class FakeAnki:
    """AnkiConnect fake holding one note; records every call so tests can assert nothing was deleted."""

    def __init__(self, model="English Sentence", tags=("daily-english-essay",), cards=({"reps": 0, "type": 0},),
                 exists=True):
        self.exists, self.model, self.tags = exists, model, list(tags)
        self.cards = [dict(c, cardId=100 + i) for i, c in enumerate(cards)]
        self.calls = []

    def __call__(self, action, **params):
        self.calls.append((action, params))
        if action == "version":
            return 6
        if action == "notesInfo":
            if not self.exists:
                return [{}]  # AnkiConnect answers an unknown id with an empty object
            return [{"noteId": params["notes"][0], "modelName": self.model, "tags": self.tags,
                     "cards": [c["cardId"] for c in self.cards]}]
        if action == "cardsInfo":
            return self.cards
        if action == "deleteNotes":
            return None
        raise AssertionError(f"unexpected AnkiConnect call: {action}")

    def deleted(self):
        return [p["notes"] for a, p in self.calls if a == "deleteNotes"]


@pytest.fixture
def anki(monkeypatch):
    def install(**kw):
        fake = FakeAnki(**kw)
        monkeypatch.setattr(anki_service, "invoke", fake)
        return fake
    return install


@pytest.mark.parametrize("model", ["English Sentence", "English Vocabulary", "English Grammar"])
def test_app_made_unreviewed_note_is_deleted_by_id(anki, model):
    fake = anki(model=model)
    res = anki_service.undo_card(555)
    assert res.success and res.error is None
    assert fake.deleted() == [[555]]


def test_note_without_the_app_tag_is_refused(anki):
    fake = anki(tags=["other"])
    res = anki_service.undo_card(555)
    assert not res.success and "앱이 만든" in res.error
    assert fake.deleted() == []


@pytest.mark.parametrize("model", ["Basic", "English Speaking", ""])
def test_note_of_another_model_is_refused(anki, model):
    fake = anki(model=model)
    assert not anki_service.undo_card(555).success
    assert fake.deleted() == []


@pytest.mark.parametrize("card", [{"reps": 1, "type": 2}, {"reps": 0, "type": 1}, {"reps": 3, "type": 0}])
def test_note_with_a_studied_card_is_refused(anki, card):
    fake = anki(cards=({"reps": 0, "type": 0}, card))  # one clean card does not make the note safe
    res = anki_service.undo_card(555)
    assert not res.success and "복습" in res.error
    assert fake.deleted() == []


def test_missing_note_is_refused_without_deleting(anki):
    fake = anki(exists=False)
    res = anki_service.undo_card(555)
    assert not res.success and "찾을 수 없" in res.error
    assert fake.deleted() == []


def test_nothing_is_deleted_when_anki_is_unreachable(monkeypatch):
    def down(action, **params):
        raise ConnectionError("tunnel down")
    monkeypatch.setattr(anki_service, "invoke", down)
    res = anki_service.undo_card(555)
    assert not res.success and res.error


# --- HTTP ---------------------------------------------------------------------

@pytest.mark.anyio
async def test_endpoint_deletes_a_safe_note(client, anki):
    fake = anki()
    res = await client.post("/api/anki/undo-card", json={"note_id": 555})
    assert res.status_code == 200 and res.json()["success"] is True
    assert fake.deleted() == [[555]]


@pytest.mark.anyio
async def test_endpoint_refuses_with_400_and_the_reason(client, anki):
    fake = anki(tags=[])
    res = await client.post("/api/anki/undo-card", json={"note_id": 555})
    assert res.status_code == 400 and "앱이 만든" in res.json()["detail"]
    assert fake.deleted() == []


@pytest.mark.anyio
async def test_endpoint_needs_a_note_id(client):
    assert (await client.post("/api/anki/undo-card", json={})).status_code == 422
