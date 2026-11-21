import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import settings
from app.core.database import init_db
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def fresh_db(tmp_path, monkeypatch):
    """Point the app at an empty temporary database so tests never touch data/essay.db."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(settings, "DATABASE_PATH", db_path)
    monkeypatch.setattr(settings, "REVIEW_METRICS_PATH", tmp_path / "review_metrics.jsonl")
    await init_db()
    return db_path


@pytest.fixture
async def client(fresh_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def no_free_llm_keys(monkeypatch):
    """Free-route keys in .env must never make a test call the network."""
    for key in ("GEMINI_FREE_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def review_on_gemini_by_default(monkeypatch):
    """Existing tests fake the Gemini client; tests of the Claude CLI backend switch it on themselves."""
    monkeypatch.setattr(settings, "REVIEW_BACKEND", "gemini")
