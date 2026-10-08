import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status
from app.schemas.diary import DiarySaveRequest, DiaryResponse, DiaryListResponse
from app.schemas.review import SuggestionItem
from app.services.diary_service import diary_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/diaries", tags=["Diaries"])

@router.get("", response_model=DiaryListResponse)
async def list_diaries():
    """Retrieve all diaries with summary and streak."""
    return await diary_service.list_diaries()

@router.get("/{date}", response_model=DiaryResponse)
async def get_diary(date: str):
    """Get diary by date (YYYY-MM-DD)."""
    diary = await diary_service.get_diary_by_date(date)
    if not diary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"해당 날짜({date})의 일기가 존재하지 않습니다."
        )
    return diary

@router.post("", response_model=DiaryResponse)
async def save_diary(req: DiarySaveRequest):
    """Save or auto-save a diary entry."""
    return await diary_service.save_diary(req)

@router.delete("/{date}")
async def delete_diary(date: str):
    """Delete diary entry by date."""
    deleted = await diary_service.delete_diary(date)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"해당 날짜({date})의 일기를 찾을 수 없습니다."
        )
    return {"success": True, "date": date, "message": "일기가 삭제되었습니다."}

@router.patch("/{date}/toggle-complete", response_model=DiaryResponse)
async def toggle_complete(date: str):
    """Toggle completion status of diary entry."""
    diary = await diary_service.toggle_complete(date)
    if not diary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"해당 날짜({date})의 일기를 찾을 수 없습니다."
        )
    return diary

@router.get("/{date}/suggestions", response_model=List[SuggestionItem])
async def get_diary_suggestions(date: str):
    """Get saved Grammarly suggestions for a specific diary date."""
    return await diary_service.get_suggestions(date)
