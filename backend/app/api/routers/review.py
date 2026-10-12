import json
import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from app.schemas.review import ReviewRequest, ReviewResponse
from app.services.essay_service import essay_service
from app.services.gemini_service import GeminiError, gemini_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/review", tags=["Review"])


async def _essay_for(req: ReviewRequest):
    essay = await essay_service.get(req.essay_id)
    if not essay:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="에세이를 찾을 수 없습니다.")
    if not req.content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="에세이 본문이 비어 있습니다.")
    return essay


@router.post("", response_model=ReviewResponse)
async def review_essay(req: ReviewRequest):
    """AI review of an essay. The result is stored on the essay only when the review succeeds."""
    essay = await _essay_for(req)

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


@router.post("/stream")
async def review_essay_stream(req: ReviewRequest):
    """Same review, sent as NDJSON lines as each part finishes:
    {"event": "content_scores" | "feedback" | "corrections" | "language_scores", "data": ...},
    then {"event": "done", "data": review} after it is saved, or {"event": "error", "detail": ...}.
    """
    essay = await _essay_for(req)

    async def lines():
        try:
            async for event, data in gemini_service.review_essay_events(
                    essay.id, essay.prompt, essay.essay_type, req.content):
                if event == "done":
                    await essay_service.save_review(essay.id, req.content, data)
                yield json.dumps({"event": event, "data": jsonable_encoder(data)}, ensure_ascii=False) + "\n"
        except GeminiError as e:
            detail = f"AI 첨삭에 실패했습니다. 잠시 후 다시 시도해주세요: {e}"
            yield json.dumps({"event": "error", "detail": detail}, ensure_ascii=False) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson")
