import logging
from fastapi import APIRouter
from app.schemas.stats import StatsResponse
from app.services.stats_service import stats_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stats", tags=["Stats"])

@router.get("", response_model=StatsResponse)
async def get_stats():
    """Retrieves learning statistics, streak, and grammar category breakdown."""
    return await stats_service.get_stats()
