"""A slow Anki round trip (SSH tunnel to the server) must not hold up other requests.

Opening an essay fires several Anki duplicate checks; switching to another essay right
after used to wait for all of them because the Anki calls blocked the event loop.
"""
import asyncio
import time

import pytest

from app.services.anki_service import anki_service

pytestmark = pytest.mark.anyio

ANKI_DELAY = 0.6


@pytest.fixture
def slow_anki(monkeypatch):
    def invoke(action, **params):
        time.sleep(ANKI_DELAY)
        if action == "multi":
            return [[] for _ in params["actions"]]
        if action == "deckNames":
            return []
        return 6

    monkeypatch.setattr(anki_service, "invoke", invoke)


@pytest.mark.parametrize("anki_call", ["status", "check"])
async def test_essay_list_does_not_wait_for_anki(client, slow_anki, anki_call):
    start = time.perf_counter()
    anki = asyncio.create_task(
        client.get("/api/anki/status") if anki_call == "status"
        else client.post("/api/anki/check-existing", json={"sentences": ["I agree."], "words": []}))
    await asyncio.sleep(0.05)  # the Anki request is in flight
    res = await client.get("/api/essays")
    elapsed = time.perf_counter() - start  # measured from when the Anki request went out
    await anki
    assert res.status_code == 200
    assert elapsed < ANKI_DELAY / 2, f"/api/essays finished {elapsed:.2f}s after the Anki request started"


async def test_existing_check_is_a_single_round_trip(client, monkeypatch):
    calls = []

    def invoke(action, **params):
        calls.append(action)
        return [[] for _ in params.get("actions", [])]

    monkeypatch.setattr(anki_service, "invoke", invoke)
    res = await client.post("/api/anki/check-existing", json={"sentences": ["I agree."], "words": ["cope with"]})
    assert res.status_code == 200
    assert calls == ["multi"]
