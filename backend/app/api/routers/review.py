import logging
from fastapi import APIRouter, HTTPException, status

from app.schemas.review import ReviewRequest, ReviewResponse
from app.services.essay_service import essay_service
from app.services.gemini_service import GeminiError, gemini_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/review", tags=["Review"])


@router.post("", response_model=ReviewResponse)
async def review_essay(req: ReviewRequest):
    """AI review of an essay. The result is stored on the essay only when the review succeeds."""
    essay = await essay_service.get(req.essay_id)
    if not essay:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="에세이를 찾을 수 없습니다.")
    if not req.content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="에세이 본문이 비어 있습니다.")

    try:
        result = await gemini_service.review_essay(
            essay_id=essay.id,
            prompt_text=essay.prompt,
            essay_type=essay.essay_type,
            content=req.content,
        )
    except GeminiError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI 첨삭에 실패했습니다. 잠시 후 다시 시도해주세요: {str(e)}",
        )

    await essay_service.save_review(essay.id, req.content, result)
    return result
