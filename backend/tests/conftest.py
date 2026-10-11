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
    await init_db()
    return db_path


@pytest.fixture
async def client(fresh_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
