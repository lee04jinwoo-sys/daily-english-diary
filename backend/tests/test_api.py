import pytest

@pytest.mark.anyio
async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@pytest.mark.anyio
async def test_diary_crud_and_stats(client):
    ac = client
    if True:
        # 1. Save dummy test diary on isolated future date
        date_str = "2099-12-31"
        payload = {
            "date": date_str,
            "title": "Automated Test Diary",
            "content": "Today I went to the park and I seen many beautiful birds.",
            "is_draft": False,
            "grammar_score": 92
        }
        res = await ac.post("/api/diaries", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["date"] == date_str
        assert data["word_count"] > 0

        # 2. Get diary
        res_get = await ac.get(f"/api/diaries/{date_str}")
        assert res_get.status_code == 200
        assert res_get.json()["title"] == "Automated Test Diary"

        # 3. List diaries
        res_list = await ac.get("/api/diaries")
        assert res_list.status_code == 200
        assert res_list.json()["total_count"] >= 1

        # 4. Get stats
        res_stats = await ac.get("/api/stats")
        assert res_stats.status_code == 200
        stats_data = res_stats.json()
        assert stats_data["total_diaries"] >= 1
        assert stats_data["total_words"] > 0
