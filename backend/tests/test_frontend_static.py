"""The backend serves the built frontend (server deploy has no Vite dev server)."""
import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.main import mount_frontend


@pytest.fixture
def dist(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>diary</html>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    return tmp_path


def _app(dist_dir):
    app = FastAPI()

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    mount_frontend(app, dist_dir)
    return app


@pytest.mark.anyio
async def test_serves_index_assets_and_spa_routes(dist):
    async with AsyncClient(transport=ASGITransport(app=_app(dist)), base_url="http://t") as c:
        assert (await c.get("/")).text == "<html>diary</html>"
        assert (await c.get("/assets/app.js")).text == "console.log(1)"
        assert (await c.get("/essays/abc")).text == "<html>diary</html>"  # client-side route
        assert (await c.get("/api/health")).json() == {"status": "ok"}


@pytest.mark.anyio
async def test_unknown_api_path_is_404_not_index(dist):
    async with AsyncClient(transport=ASGITransport(app=_app(dist)), base_url="http://t") as c:
        r = await c.get("/api/nope")
        assert r.status_code == 404


@pytest.mark.anyio
async def test_no_path_escape(dist):
    (dist.parent / "secret.txt").write_text("x")
    async with AsyncClient(transport=ASGITransport(app=_app(dist)), base_url="http://t") as c:
        r = await c.get("/..%2Fsecret.txt")
        assert "x" != r.text


def test_missing_dist_mounts_nothing(tmp_path):
    app = FastAPI()
    mount_frontend(app, tmp_path / "nope")
    assert len(app.routes) == len(FastAPI().routes)
