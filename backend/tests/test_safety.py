"""Phase 0 safety tests: things that could destroy Anki data or corrupt the record."""
import pytest

from app.schemas.review import SuggestionItem
from app.services import anki_service as anki_module
from app.services.anki_service import anki_service
from app.services.essay_service import essay_service
from app.services.gemini_service import gemini_service


@pytest.mark.anyio
async def test_delete_card_endpoint_is_gone(client, monkeypatch):
    # The old endpoint deleted any note whose text matched, including years-old cards.
    # Stub it out so this test can never reach a real Anki even on the old code.
    monkeypatch.setattr(anki_service, "delete_card", lambda *a, **k: None, raising=False)
    res = await client.post("/api/anki/delete-card", json={"card_type": "vocab", "text": "zzz"})
    assert res.status_code in (404, 405)


def test_anki_service_has_no_delete_capability():
    assert not hasattr(anki_service, "delete_card")


@pytest.mark.anyio
async def test_fresh_db_can_store_suggestions(fresh_db):
    item = SuggestionItem(
        id="s1",
        original_phrase="I seen",
        suggested_phrase="I saw",
        category="Grammar",
        subcategory="시제(Tense)",
        tier="accuracy",
        explanation="과거형",
        start_idx=0,
        end_idx=6,
    )
    await essay_service.save_suggestions("essay-1", [item])
    saved = await essay_service.get_suggestions("essay-1")
    assert len(saved) == 1
    assert saved[0].tier == "accuracy"
    assert saved[0].subcategory == "시제(Tense)"


@pytest.mark.anyio
async def test_no_route_opens_the_mac_anki_app(client):
    # Anki runs on the Oracle server; the Mac's Anki would be a second client
    # editing the same AnkiWeb collection.
    res = await client.post("/api/anki/launch")
    assert res.status_code in (404, 405)
    assert not hasattr(anki_service, "launch_anki")


class _FailingModels:
    def generate_content(self, *a, **k):
        raise RuntimeError("gemini down")


class _FailingAioModels:
    async def generate_content(self, *a, **k):
        raise RuntimeError("gemini down")


class _FailingClient:
    models = _FailingModels()

    class aio:
        models = _FailingAioModels()


@pytest.mark.anyio
async def test_review_failure_is_reported_not_faked(client, monkeypatch):
    # Previously a Gemini failure came back as a normal review with score 80,
    # which the frontend then saved as if it were real feedback.
    monkeypatch.setattr(gemini_service, "_client", _FailingClient())
    e = (await client.post("/api/essays", json={"prompt": "Is chess a sport?", "essay_type": "free"})).json()
    res = await client.post("/api/review", json={"essay_id": e["id"], "content": "I went to school."})
    assert res.status_code == 502
