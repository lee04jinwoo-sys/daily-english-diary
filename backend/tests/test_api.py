import pytest


@pytest.mark.anyio
async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.anyio
async def test_old_diary_api_is_gone(client):
    assert (await client.get("/api/diaries")).status_code == 404
