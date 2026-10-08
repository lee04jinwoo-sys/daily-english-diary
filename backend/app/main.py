import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.api.routers import diaries, review, anki, stats, dict as dict_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("daily-english-diary")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Daily English Diary Backend...")
    await init_db()
    yield
    logger.info("Shutting down Daily English Diary Backend...")

app = FastAPI(
    title="Daily English Diary API",
    description="AI-powered English Diary review with Grammarly-style inline feedback and Anki export",
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
app.include_router(diaries.router)
app.include_router(review.router)
app.include_router(dict_router.router)
app.include_router(anki.router)
app.include_router(stats.router)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "daily-english-diary", "version": "1.0.0"}
