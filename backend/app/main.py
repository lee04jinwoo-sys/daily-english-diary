import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.api.routers import essays, topics, review, anki, stats, dict as dict_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("daily-english-essay")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Daily English Essay backend...")
    await init_db()
    yield
    logger.info("Shutting down Daily English Essay backend...")

app = FastAPI(
    title="Daily English Essay API",
    description="Argumentative essay practice with AI review, inline feedback and Anki export",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(essays.router)
app.include_router(topics.router)
app.include_router(review.router)
app.include_router(dict_router.router)
app.include_router(anki.router)
app.include_router(stats.router)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "daily-english-essay", "version": "1.0.0"}


def mount_frontend(app: FastAPI, dist_dir: Path) -> None:
    """Serve the built frontend (frontend/dist) so the server needs no Vite dev server.

    Files are served as-is; any other non-API path gets index.html for client-side routes.
    """
    dist_dir = Path(dist_dir).resolve()
    index = dist_dir / "index.html"
    if not index.is_file():
        return

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        target = (dist_dir / path).resolve()
        if path and target.is_file() and target.is_relative_to(dist_dir):
            return FileResponse(target)
        return FileResponse(index)


mount_frontend(app, Path(os.getenv("FRONTEND_DIST") or Path(__file__).resolve().parents[2] / "frontend" / "dist"))
