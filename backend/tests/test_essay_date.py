"""An essay's date can be corrected (e.g. written offline, entered later). Only the date changes:
the writing order that stats number essays by is the creation order, so it stays."""
import datetime

import pytest

TODAY = datetime.date.today()


async def new_essay(client, content="One two three."):
    e = (await client.post("/api/essays", json={"prompt": "Work?", "essay_type": "free"})).json()
    await client.patch(f"/api/essays/{e['id']}", json={"content": content})
    return e["id"]


def days_ago(n):
    return (TODAY - datetime.timedelta(days=n)).isoformat()


@pytest.mark.anyio
async def test_date_can_be_changed_and_nothing_else_does(client):
    essay_id = await new_essay(client, "Keep this text.")
    before = (await client.get(f"/api/essays/{essay_id}")).json()
    res = await client.patch(f"/api/essays/{essay_id}", json={"date": days_ago(3)})
    assert res.status_code == 200
    after = res.json()
    assert after["date"] == days_ago(3)
    for key in ("content", "prompt", "word_count", "writing_seconds", "essay_type", "category"):
        assert after[key] == before[key]
    assert (await client.get(f"/api/essays/{essay_id}")).json()["date"] == days_ago(3)


@pytest.mark.anyio
async def test_date_and_content_can_be_sent_together(client):
    essay_id = await new_essay(client)
    res = await client.patch(f"/api/essays/{essay_id}", json={"date": days_ago(1), "content": "New text here."})
    assert res.json()["date"] == days_ago(1) and res.json()["content"] == "New text here."


@pytest.mark.anyio
async def test_other_updates_do_not_touch_the_date(client):
    essay_id = await new_essay(client)
    await client.patch(f"/api/essays/{essay_id}", json={"date": days_ago(5)})
    await client.patch(f"/api/essays/{essay_id}", json={"content": "Edited later."})
    assert (await client.get(f"/api/essays/{essay_id}")).json()["date"] == days_ago(5)


@pytest.mark.anyio
@pytest.mark.parametrize("bad", ["", "yesterday", "2026-13-01", "2026-02-30", "26-1-1", "2026/11/21", "2026-11-21T10:00"])
async def test_a_malformed_or_impossible_date_is_rejected(client, bad):
    essay_id = await new_essay(client)
    res = await client.patch(f"/api/essays/{essay_id}", json={"date": bad})
    assert res.status_code == 422
    assert (await client.get(f"/api/essays/{essay_id}")).json()["date"] == TODAY.isoformat()


@pytest.mark.anyio
async def test_today_is_allowed_and_tomorrow_is_not(client):
    essay_id = await new_essay(client)
    assert (await client.patch(f"/api/essays/{essay_id}", json={"date": TODAY.isoformat()})).status_code == 200
    tomorrow = (TODAY + datetime.timedelta(days=1)).isoformat()
    assert (await client.patch(f"/api/essays/{essay_id}", json={"date": tomorrow})).status_code == 422


@pytest.mark.anyio
async def test_unknown_essay_is_404(client):
    assert (await client.patch("/api/essays/nope", json={"date": days_ago(1)})).status_code == 404


@pytest.mark.anyio
async def test_the_streak_follows_the_new_date(client):
    essay_id = await new_essay(client)
    assert (await client.get("/api/essays")).json()["streak"] == 1
    await client.patch(f"/api/essays/{essay_id}", json={"date": days_ago(4)})
    assert (await client.get("/api/essays")).json()["streak"] == 0      # nothing today or yesterday any more
    await client.patch(f"/api/essays/{essay_id}", json={"date": days_ago(1)})
    assert (await client.get("/api/essays")).json()["streak"] == 1


@pytest.mark.anyio
async def test_the_stats_calendar_moves_the_day_but_not_the_essay_number(client):
    a = await new_essay(client, "First essay text.")
    b = await new_essay(client, "Second essay text.")
    await client.patch(f"/api/essays/{a}", json={"date": days_ago(2)})
    stats = (await client.get("/api/stats")).json()
    days = {d: v["essay_count"] for d, v in stats["daily_activity"].items()}
    assert days.get(days_ago(2)) == 1 and days.get(TODAY.isoformat()) == 1
    # the creation order is untouched: moving the first essay's day does not make it "later"
    ids_in_order = [e["id"] for e in (await client.get("/api/essays")).json()["essays"]][::-1]
    assert ids_in_order == [a, b]
