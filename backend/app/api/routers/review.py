import logging
from fastapi import APIRouter, HTTPException, status
from app.schemas.review import ReviewRequest, ReviewResponse
from app.services.gemini_service import gemini_service, GeminiError
from app.services.diary_service import diary_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/review", tags=["Review"])

@router.post("", response_model=ReviewResponse)
async def review_diary(req: ReviewRequest):
    """
    Performs AI English review on diary content with Grammarly-style inline suggestions,
    grammar fixes, natural paraphrasing, and Korean explanations.
    """
    if not req.content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="일기 본문 내용이 비어 있습니다."
        )

    try:
        # 1. Run Gemini AI Review
        review_result = await gemini_service.review_diary(
            date=req.date,
            content=req.content,
            title=req.title or ""
        )

        # 2. Persist suggestions for statistics & history
        if review_result.suggestions:
            await diary_service.save_suggestions(req.date, review_result.suggestions)

        return review_result

    except GeminiError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI 첨삭에 실패했습니다. 잠시 후 다시 시도해주세요: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error reviewing diary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 첨삭 처리 중 오류가 발생했습니다: {str(e)}"
        )
