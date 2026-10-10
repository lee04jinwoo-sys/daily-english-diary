"""Writing timer: active writing seconds stored per essay."""
import aiosqlite
import pytest

from app.core.config import settings
from app.core.database import init_db


async def _new_essay(client):
    return (await client.post("/api/essays", json={"prompt": "Is chess a sport?", "essay_type": "free"})).json()


@pytest.mark.anyio
async def test_new_essay_starts_at_zero(client):
    e = await _new_essay(client)
    assert e["writing_seconds"] == 0


@pytest.mark.anyio
async def test_writing_seconds_persist_and_never_go_backwards(client):
    e = await _new_essay(client)
    r = await client.patch(f"/api/essays/{e['id']}", json={"writing_seconds": 300})
    assert r.json()["writing_seconds"] == 300
    # A stale tab sending a smaller value must not erase time.
    r = await client.patch(f"/api/essays/{e['id']}", json={"writing_seconds": 120})
    assert r.json()["writing_seconds"] == 300
    lst = (await client.get("/api/essays")).json()["essays"]
    assert lst[0]["writing_seconds"] == 300


@pytest.mark.anyio
async def test_negative_seconds_rejected(client):
    e = await _new_essay(client)
    r = await client.patch(f"/api/essays/{e['id']}", json={"writing_seconds": -5})
    assert r.status_code == 422


@pytest.mark.anyio
async def test_timer_patch_does_not_touch_content(client):
    e = await _new_essay(client)
    await client.patch(f"/api/essays/{e['id']}", json={"content": "New text here."})
    r = await client.patch(f"/api/essays/{e['id']}", json={"writing_seconds": 60})
    assert r.json()["content"] == "New text here."
    assert r.json()["word_count"] == 3


@pytest.mark.anyio
async def test_content_patch_does_not_touch_timer(client):
    e = await _new_essay(client)
    await client.patch(f"/api/essays/{e['id']}", json={"writing_seconds": 90})
    r = await client.patch(f"/api/essays/{e['id']}", json={"content": "More text."})
    assert r.json()["writing_seconds"] == 90


@pytest.mark.anyio
async def test_revision_starts_its_own_timer(client):
    e = await _new_essay(client)
    await client.patch(f"/api/essays/{e['id']}", json={"content": "Draft.", "writing_seconds": 500})
    r = (await client.post(f"/api/essays/{e['id']}/revise")).json()
    assert r["writing_seconds"] == 0


@pytest.mark.anyio
async def test_existing_db_without_column_is_migrated(tmp_path, monkeypatch):
    db_path = tmp_path / "old.db"
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""CREATE TABLE essays (
            id TEXT PRIMARY KEY, date TEXT NOT NULL, topic_id TEXT, prompt TEXT NOT NULL,
            essay_type TEXT NOT NULL, category TEXT NOT NULL, content TEXT NOT NULL DEFAULT '',
            word_count INTEGER NOT NULL DEFAULT 0, revision_of TEXT, is_completed INTEGER NOT NULL DEFAULT 0,
            overall_band REAL, review_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        await db.execute("INSERT INTO essays (id, date, prompt, essay_type, category, content, created_at, updated_at) "
                         "VALUES ('old1', '2026-10-10', 'p', 'free', 'free', 'kept text', 't', 't')")
        await db.commit()
    monkeypatch.setattr(settings, "DATABASE_PATH", db_path)
    await init_db()
    async with aiosqlite.connect(db_path) as db:
        row = await (await db.execute("SELECT content, writing_seconds FROM essays WHERE id='old1'")).fetchone()
    assert row == ("kept text", 0)
