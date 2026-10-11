import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
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
